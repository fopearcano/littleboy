"""A minimal command-line interface for LittleBoy.

Usage::

    littleboy evaluate examples/high_coercion_missing_consent.json
    littleboy evaluate examples/simple_case.json --format text
    littleboy experiment examples/manipulative_language_case.json
    littleboy version

It loads a JSON :class:`~littleboy.core.models.ActionCase`, runs the evaluator
(or the ethical-experiment runner), and prints the result. The CLI is
intentionally thin: all reasoning lives in the library, so the engine can be
used without it. Malformed input fails gracefully with an explanation.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from littleboy import __version__
from littleboy.audit.report import render_audit_json, render_audit_text
from littleboy.calibration import (
    default_corpus,
    default_labelled_outcome_corpus,
    default_outcome_corpus,
    default_scoring_corpus,
    fit_threshold_policy,
    generate_scoring_corpus,
    load_corpus,
    outcome_corpus_from_csv,
    recommend_policy_for_stakeholder,
    run_corpus,
    run_reliability,
    run_scoring_corpus,
)
from littleboy.case_builder import (
    CaseBuilder,
    build_case_from_answers,
    get_template,
    list_templates,
    wizard_prompts,
)
from littleboy.case_builder.templates import ScenarioTemplate
from littleboy.comparison import ComparisonEngine
from littleboy.comparison.models import ActionComparisonSet
from littleboy.comparison.report import render_comparison_json, render_comparison_text
from littleboy.core.enums import PolicyMode
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase
from littleboy.deliberation import Deliberator, run_minimal_intake
from littleboy.deliberation.report import (
    render_comparison_deliberation_json,
    render_comparison_deliberation_text,
    render_deliberation_json,
    render_deliberation_text,
    render_intake_text,
    render_question_plan_json,
    render_question_plan_text,
)
from littleboy.language import analyze_language
from littleboy.reasoning.experiment import EthicalExperiment
from littleboy.reasoning.report import (
    render_completeness_json,
    render_completeness_text,
    render_json,
    render_language_json,
    render_language_text,
    render_text,
)
from littleboy.temporal.report import render_temporal_json, render_temporal_text

_POLICY_CHOICES = ", ".join(m.value for m in PolicyMode)
_TEMPLATE_CHOICES = ", ".join(list_templates())

app = typer.Typer(
    add_completion=False,
    help="LittleBoy: a transparent ethical evaluation engine (evil = coercion).",
)


def _load_case(case_path: Path) -> ActionCase:
    """Load and validate an ActionCase from JSON, exiting gracefully on error."""
    try:
        raw = json.loads(case_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON in {case_path}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    try:
        return ActionCase.model_validate(raw)
    except ValidationError as exc:
        typer.echo(f"Invalid ActionCase in {case_path}:\n{exc}", err=True)
        raise typer.Exit(code=2) from exc


def _resolve_policy(policy: str) -> PolicyMode:
    try:
        return PolicyMode(policy)
    except ValueError as exc:
        typer.echo(f"Unknown policy '{policy}'; use one of: {_POLICY_CHOICES}.", err=True)
        raise typer.Exit(code=2) from exc


def _resolve_template(template: str | None) -> ScenarioTemplate | None:
    if template is None:
        return None
    resolved = get_template(template)
    if resolved is None:
        typer.echo(f"Unknown template '{template}'; use one of: {_TEMPLATE_CHOICES}.", err=True)
        raise typer.Exit(code=2)
    return resolved


@app.command()
def evaluate(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file describing the ActionCase.",
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
    audit: bool = typer.Option(
        False, "--audit", help="Also run the adversarial audit of the description/framing."
    ),
) -> None:
    """Evaluate a single action case from a JSON file under a policy profile."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    try:
        policy_mode = PolicyMode(policy)
    except ValueError as exc:
        typer.echo(f"Unknown policy '{policy}'; use one of: {_POLICY_CHOICES}.", err=True)
        raise typer.Exit(code=2) from exc

    case = _load_case(case_path)
    report = EthicalEvaluator(policy_mode).evaluate(case, audit=audit)
    typer.echo(render_text(report) if output_format == "text" else render_json(report))


@app.command()
def experiment(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file describing the ActionCase.",
    ),
) -> None:
    """Run an ethical experiment (falsificatory + heuristic) over a case."""
    case = _load_case(case_path)
    result = EthicalExperiment().run(case)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@app.command()
def questions(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file describing a (possibly partial) ActionCase.",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
    template: str | None = typer.Option(
        None, "--template", "-t", help=f"Scenario template: {_TEMPLATE_CHOICES}."
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        "-m",
        help="Ask only the questions that could change the verdict, in priority order.",
    ),
) -> None:
    """Show what a case is missing and which questions to answer before judging it."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    policy_mode = _resolve_policy(policy)
    tpl = _resolve_template(template)

    case = _load_case(case_path)
    builder = CaseBuilder(policy_mode)
    if minimal:
        plan = builder.minimal_questions(case)
        if output_format == "json":
            typer.echo(render_question_plan_json(plan))
        else:
            typer.echo(render_question_plan_text(plan))
        return
    question_set = builder.generate_questions(case, template=tpl)
    report = builder.completeness_report(case, template=tpl)
    if output_format == "json":
        typer.echo(render_completeness_json(report, question_set))
    else:
        typer.echo(render_completeness_text(report, question_set))


@app.command(name="build-case")
def build_case(
    template: str | None = typer.Option(
        None, "--template", "-t", help=f"Scenario template: {_TEMPLATE_CHOICES}."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the constructed case to this JSON file."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
    run_evaluation: bool = typer.Option(
        True, "--evaluate/--no-evaluate", help="Evaluate the case if enough data exist."
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        "-m",
        help="Interactively ask only the questions that could change the verdict, "
        "re-planning after each answer (requires --from).",
    ),
    seed: Path | None = typer.Option(
        None, "--from", help="Seed the minimal-intake loop from this JSON ActionCase."
    ),
    strategy: str = typer.Option(
        "greedy",
        "--strategy",
        help="Intake strategy: 'greedy' (cheapest-first) or 'lookahead' (min expected cost).",
    ),
) -> None:
    """Interactively build an ActionCase, then show its completeness (and optionally evaluate)."""
    policy_mode = _resolve_policy(policy)

    if minimal:
        if seed is None:
            typer.echo("--minimal requires --from <case.json> to seed the loop.", err=True)
            raise typer.Exit(code=2)
        if strategy not in {"greedy", "lookahead"}:
            typer.echo(f"Unknown strategy '{strategy}'; use 'greedy' or 'lookahead'.", err=True)
            raise typer.Exit(code=2)
        case = _load_case(seed)
        typer.echo(
            "LittleBoy minimal intake: answering only what could change the verdict.\n",
            err=True,
        )

        def _answer(question) -> str:
            label = f"[{question.priority}, cost {question.cost:g}] {question.question}"
            return typer.prompt(label, default="", show_default=False)

        transcript, final_case = run_minimal_intake(
            case, _answer, policy=policy_mode, strategy=strategy
        )
        typer.echo("\n" + render_intake_text(transcript))
        if output is not None:
            payload = final_case.model_dump(mode="json", exclude_none=True)
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            typer.echo(f"\nWrote case to {output}")
        if run_evaluation:
            typer.echo("\n" + render_text(EthicalEvaluator(policy_mode).evaluate(final_case)))
        return

    tpl = _resolve_template(template)
    typer.echo("LittleBoy case builder. Press Enter to skip any question.\n", err=True)
    answers: dict[str, str] = {}
    for prompt in wizard_prompts(tpl):
        label = prompt.text
        if prompt.choices:
            label += f" [{'/'.join(prompt.choices)}]"
        answers[prompt.key] = typer.prompt(label, default="", show_default=False)

    case = build_case_from_answers(answers, template=tpl)

    if output is not None:
        payload = case.model_dump(mode="json", exclude_none=True)
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"\nWrote case to {output}")

    builder = CaseBuilder(policy_mode)
    report = builder.completeness_report(case, template=tpl)
    typer.echo("\n" + render_completeness_text(report))

    if run_evaluation and report.can_evaluate:
        evaluation = EthicalEvaluator(policy_mode).evaluate(case)
        typer.echo("\n" + render_text(evaluation))
    elif run_evaluation:
        typer.echo(
            "\nNot enough information to evaluate yet; answer the critical questions above first."
        )


@app.command()
def compare(
    set_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON ActionComparisonSet (a set of candidate options).",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str | None = typer.Option(
        None, "--policy", "-p", help=f"Override policy: {_POLICY_CHOICES} (default: the set's)."
    ),
    audit: bool = typer.Option(
        False, "--audit", help="Also run the adversarial audit across the comparison."
    ),
) -> None:
    """Compare candidate actions and rank the least-coercive morally viable path."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    policy_mode = _resolve_policy(policy) if policy is not None else None

    try:
        raw = json.loads(set_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON in {set_path}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    try:
        comparison_set = ActionComparisonSet.model_validate(raw)
    except ValidationError as exc:
        typer.echo(f"Invalid ActionComparisonSet in {set_path}:\n{exc}", err=True)
        raise typer.Exit(code=2) from exc

    result = ComparisonEngine(policy_mode).compare(comparison_set, audit=audit)
    if output_format == "json":
        typer.echo(render_comparison_json(result))
    else:
        typer.echo(render_comparison_text(result))


@app.command(name="analyze-language")
def analyze_language_cmd(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON ActionCase that contains a `language_act`.",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
) -> None:
    """Analyse the linguistic coercion and constructiveness of a case's language act."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    case = _load_case(case_path)
    if case.language_act is None:
        typer.echo("This case contains no `language_act`; there is nothing to analyse.", err=True)
        raise typer.Exit(code=2)
    analysis = analyze_language(case.language_act)
    if output_format == "json":
        typer.echo(render_language_json(analysis))
    else:
        typer.echo(render_language_text(analysis))


@app.command()
def temporal(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON ActionCase (ideally with temporal fields).",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
) -> None:
    """Show the temporal coercion projection for a case (trend, reversibility, cumulative)."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    policy_mode = _resolve_policy(policy)
    case = _load_case(case_path)
    report = EthicalEvaluator(policy_mode).evaluate(case)
    projection = report.temporal_projection
    if output_format == "json":
        typer.echo(render_temporal_json(projection))
    else:
        typer.echo(render_temporal_text(projection))


@app.command()
def audit(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file describing the ActionCase.",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
) -> None:
    """Adversarially audit how a case is described: red flags, bias, and stress tests."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    policy_mode = _resolve_policy(policy)
    case = _load_case(case_path)
    report = EthicalEvaluator(policy_mode).evaluate(case, audit=True)
    audit_report = report.audit_report
    if output_format == "json":
        typer.echo(render_audit_json(audit_report))
    else:
        typer.echo(render_audit_text(audit_report))


@app.command()
def deliberate(
    path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON ActionCase, or an ActionComparisonSet with --compare.",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
    compare_set: bool = typer.Option(
        False, "--compare", "-c", help="Treat the input as an ActionComparisonSet."
    ),
) -> None:
    """Narrate why the verdict (or top option) holds, and the fact that would most change it."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    policy_mode = _resolve_policy(policy)
    deliberator = Deliberator(policy_mode)

    if compare_set:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            comparison_set = ActionComparisonSet.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            typer.echo(f"Invalid ActionComparisonSet in {path}:\n{exc}", err=True)
            raise typer.Exit(code=2) from exc
        report = deliberator.deliberate_comparison(comparison_set)
        if output_format == "json":
            typer.echo(render_comparison_deliberation_json(report))
        else:
            typer.echo(render_comparison_deliberation_text(report))
        return

    case = _load_case(path)
    report = deliberator.deliberate(case)
    if output_format == "json":
        typer.echo(render_deliberation_json(report))
    else:
        typer.echo(render_deliberation_text(report))


@app.command()
def calibrate(
    corpus_path: Path | None = typer.Argument(
        None,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to an audit corpus JSON (defaults to the packaged corpus).",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    scope: str = typer.Option(
        "all",
        "--scope",
        "-s",
        help="Which to run: 'audit', 'scoring', 'reliability', or 'all'.",
    ),
    generated: bool = typer.Option(
        False,
        "--generated",
        "-g",
        help="Use the large generated (independently-labelled) corpus for the scoring scope.",
    ),
    labelled: bool = typer.Option(
        False,
        "--labelled",
        "-l",
        help="Use the large multi-labeller outcome corpus (with inter-rater agreement).",
    ),
    n: int = typer.Option(120, "--n", help="Number of generated cases (with --generated)."),
    seed: int = typer.Option(0, "--seed", help="Seed for the generated corpus (with --generated)."),
) -> None:
    """Run the calibration corpora and report per-layer miss / false-alarm rates."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    if scope not in {"audit", "scoring", "reliability", "all"}:
        typer.echo(
            f"Unknown scope '{scope}'; use 'audit', 'scoring', 'reliability', or 'all'.", err=True
        )
        raise typer.Exit(code=2)

    audit_report = None
    scoring_report = None
    reliability_report = None
    if scope in {"audit", "all"}:
        corpus = load_corpus(corpus_path) if corpus_path is not None else default_corpus()
        audit_report = run_corpus(corpus)
    if scope in {"scoring", "all"}:
        scoring_corpus = (
            generate_scoring_corpus(n=n, seed=seed) if generated else default_scoring_corpus()
        )
        scoring_report = run_scoring_corpus(scoring_corpus)
    if scope in {"reliability", "all"}:
        outcome_corpus = default_labelled_outcome_corpus() if labelled else default_outcome_corpus()
        reliability_report = run_reliability(outcome_corpus)

    if output_format == "json":
        payload: dict = {}
        if audit_report is not None:
            payload["audit"] = audit_report.model_dump(mode="json")
        if scoring_report is not None:
            payload["scoring"] = scoring_report.model_dump(mode="json")
        if reliability_report is not None:
            payload["reliability"] = reliability_report.model_dump(mode="json")
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if audit_report is not None:
        r = audit_report
        typer.echo(
            f"CALIBRATION (audit): {r.n_passed}/{r.n_cases} entries passed   "
            f"miss_rate={r.miss_rate:.2f}  false_alarm_rate={r.false_alarm_rate:.2f}"
        )
        typer.echo(f"  adversarial={r.n_adversarial}  clean={r.n_clean}")
        for o in r.outcomes:
            status = "PASS" if o.passed else "FAIL"
            typer.echo(f"  [{status}] {o.id} ({o.label})")
            if o.missing_expected:
                typer.echo(f"      missed: {', '.join(o.missing_expected)}")
            if o.false_alarms:
                typer.echo(f"      false alarm: {', '.join(o.false_alarms)}")
            if not o.stability_ok:
                typer.echo("      stability mismatch")

    if scoring_report is not None:
        s = scoring_report
        if audit_report is not None:
            typer.echo("")
        typer.echo(
            f"CALIBRATION (scoring): verdict_accuracy={s.verdict_accuracy:.2f} "
            f"({s.verdict_correct}/{s.verdict_labelled})"
        )
        for layer in s.layers:
            typer.echo(
                f"  {layer.layer}: miss_rate={layer.miss_rate:.2f}  "
                f"false_alarm_rate={layer.false_alarm_rate:.2f}  (n={layer.n_labelled})"
            )
        for mismatch in s.verdict_mismatches:
            typer.echo(f"  verdict mismatch: {mismatch}")

    if reliability_report is not None:
        if audit_report is not None or scoring_report is not None:
            typer.echo("")
        typer.echo("CALIBRATION (reliability vs held-out human labels):")
        for split in reliability_report.splits:
            ceiling = ""
            if split.inter_rater is not None:
                ir = split.inter_rater
                ceiling = (
                    f"  inter-rater ceiling: agreement={ir.percent_agreement:.2f} "
                    f"kappa={ir.fleiss_kappa:.2f}"
                )
            typer.echo(f"  [{split.split}] n={split.n}{ceiling}")
            for p in split.policies:
                lo, hi = p.exact_accuracy_ci.low, p.exact_accuracy_ci.high
                typer.echo(
                    f"    {p.policy:14s} exact={p.exact_accuracy:.2f} CI[{lo:.2f},{hi:.2f}]  "
                    f"disposition={p.disposition_accuracy:.2f}"
                )


@app.command(name="recommend-policy")
def recommend_policy_cmd(
    stakeholder: str | None = typer.Option(
        None,
        "--stakeholder",
        help="Match this labeler's held-out judgments (default: the panel consensus).",
    ),
    metric: str = typer.Option(
        "disposition", "--metric", help="Rank by 'disposition' or 'exact' agreement."
    ),
    fit: bool = typer.Option(
        False,
        "--fit",
        help="Also fit a custom threshold policy (dev fit, holdout score) vs the nearest built-in.",
    ),
    labels_csv: Path | None = typer.Option(
        None,
        "--labels-csv",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Overlay real labels (case_id,labeler,verdict[,split]) onto the corpus cases.",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
) -> None:
    """Recommend the policy whose verdicts best match a stakeholder's held-out judgments."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    if metric not in {"disposition", "exact"}:
        typer.echo(f"Unknown metric '{metric}'; use 'disposition' or 'exact'.", err=True)
        raise typer.Exit(code=2)

    base = default_labelled_outcome_corpus()
    try:
        corpus = outcome_corpus_from_csv(base, labels_csv) if labels_csv is not None else base
    except ValueError as exc:
        typer.echo(f"Could not apply labels from {labels_csv}: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    rec = recommend_policy_for_stakeholder(corpus, stakeholder, metric=metric)
    fitted = fit_threshold_policy(corpus, stakeholder, metric=metric) if fit else None

    if output_format == "json":
        payload: dict = {"recommendation": rec.model_dump(mode="json")}
        if fitted is not None:
            payload["fitted"] = fitted.model_dump(mode="json")
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    typer.echo(
        f"RECOMMENDED POLICY for '{rec.target}': {rec.recommended_policy}  "
        f"({rec.metric} agreement {rec.recommended_accuracy:.2f} on the {rec.split} split)"
    )
    if rec.agreement_ceiling is not None:
        typer.echo(f"  inter-labeller agreement ceiling: {rec.agreement_ceiling:.2f}")
    typer.echo("  ranking (with trade-offs):")
    for p in rec.ranked:
        acc = p.disposition_accuracy if metric == "disposition" else p.exact_accuracy
        ci = p.disposition_accuracy_ci if metric == "disposition" else p.exact_accuracy_ci
        tie = "  (tied with the leader)" if p.policy in rec.indistinguishable else ""
        typer.echo(f"    {p.policy:14s} {acc:.2f} CI[{ci.low:.2f},{ci.high:.2f}]{tie}")
    for note in rec.notes:
        typer.echo(f"  - {note}")

    if fitted is not None:
        ts = fitted.thresholds
        fci = fitted.report_accuracy_ci
        nci = fitted.nearest_builtin_accuracy_ci
        typer.echo("")
        typer.echo(
            f"FITTED POLICY for '{fitted.target}' "
            f"(fitted on {fitted.fit_split}, scored on {fitted.report_split}):"
        )
        typer.echo(
            f"  thresholds: coercion_moderate={ts.coercion_moderate} "
            f"max_coercion_for_acceptable={ts.max_coercion_for_acceptable} "
            f"(base: {ts.base_mode})"
        )
        typer.echo(
            f"  fitted   {fitted.report_accuracy:.2f} CI[{fci.low:.2f},{fci.high:.2f}]   "
            f"(dev fit {fitted.fit_accuracy:.2f})"
        )
        typer.echo(
            f"  nearest  {fitted.nearest_builtin:14s} {fitted.nearest_builtin_accuracy:.2f} "
            f"CI[{nci.low:.2f},{nci.high:.2f}]   gain={fitted.gain_over_nearest:+.2f}"
        )
        for note in fitted.notes:
            typer.echo(f"  - {note}")


@app.command()
def templates() -> None:
    """List the available scenario templates."""
    for name in list_templates():
        tpl = get_template(name)
        typer.echo(f"{name}: {tpl.summary}")


@app.command()
def version() -> None:
    """Print the LittleBoy version."""
    typer.echo(__version__)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
