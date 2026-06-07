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
from littleboy.case_builder import (
    CaseBuilder,
    build_case_from_answers,
    get_template,
    list_templates,
    wizard_prompts,
)
from littleboy.case_builder.templates import ScenarioTemplate
from littleboy.core.enums import PolicyMode
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase
from littleboy.reasoning.experiment import EthicalExperiment
from littleboy.reasoning.report import (
    render_completeness_json,
    render_completeness_text,
    render_json,
    render_text,
)

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
    report = EthicalEvaluator(policy_mode).evaluate(case)
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
) -> None:
    """Show what a case is missing and which questions to answer before judging it."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    policy_mode = _resolve_policy(policy)
    tpl = _resolve_template(template)

    case = _load_case(case_path)
    builder = CaseBuilder(policy_mode)
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
) -> None:
    """Interactively build an ActionCase, then show its completeness (and optionally evaluate)."""
    policy_mode = _resolve_policy(policy)
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
