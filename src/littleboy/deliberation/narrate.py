"""Narration: turn a verdict (or a ranking) into an ordered explanation of *why*.

The narrator adds no judgment of its own. It reads the report (or comparison
result) the engine already produced and orders the factors that drove it:
*decisive* (blockers, verdict caps, downgrades), *supporting* (coercion level,
consent, justification, alternatives), and *context* (confidence). For a
comparison it names the first lexicographic layer on which the runner-up lost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.core.enums import RuleResultStatus, RuleSeverity, Verdict
from littleboy.deliberation.models import DeliberationStep

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.comparison.models import ActionComparisonResult
    from littleboy.core.models import EvaluationReport


def narrate_evaluation(report: EvaluationReport) -> tuple[str, list[DeliberationStep], list[str]]:
    """Return ``(headline, steps, decisive_factors)`` explaining a single verdict."""
    steps: list[DeliberationStep] = []
    decisive: list[str] = []

    trace = report.reasoning_trace
    if trace is not None:
        for r in trace.applied:
            if r.status != RuleResultStatus.FAILED:
                continue
            if (
                r.severity in (RuleSeverity.BLOCKER, RuleSeverity.DOWNGRADE)
                or r.verdict_cap is not None
            ):
                steps.append(
                    DeliberationStep(
                        claim=r.message, basis=f"{r.rule_id} ({r.name})", kind="decisive"
                    )
                )
                decisive.append(f"[{r.rule_id}] {r.message}")

    steps.append(
        DeliberationStep(
            claim=f"measured coercion is {report.coercion_score:.2f}",
            basis="coercion scoring (A0/A2)",
            kind="supporting",
        )
    )
    if report.consent_status:
        steps.append(
            DeliberationStep(
                claim=f"consent: {report.consent_status}", basis="A2", kind="supporting"
            )
        )
    jr = report.justification_result
    if jr is not None:
        steps.append(
            DeliberationStep(
                claim=f"Axiom 3 justification: is_justified = {jr.is_justified}",
                basis="A3",
                kind="supporting",
            )
        )
    aa = report.alternatives_analysis
    if aa is not None and aa.has_feasible_less_coercive:
        steps.append(
            DeliberationStep(
                claim="a feasible, less-coercive alternative was identified",
                basis="A2",
                kind="supporting",
            )
        )
    confidence_claim = (
        f"confidence {report.confidence:.2f} ({report.uncertainty_level.value} uncertainty)"
    )
    steps.append(DeliberationStep(claim=confidence_claim, basis="A5", kind="context"))

    verdict = report.verdict
    if verdict == Verdict.INSUFFICIENT_DATA:
        data_reason = next(
            (
                d
                for d in decisive
                if any(k in d.lower() for k in ("basis", "data", "evidence", "insufficient"))
            ),
            decisive[0] if decisive else "",
        )
        tail = (
            data_reason.split("] ", 1)[-1]
            if data_reason
            else (
                report.main_reasons[0]
                if report.main_reasons
                else "insufficient trustworthy information"
            )
        )
        headline = f"{verdict.value}: LittleBoy declines to judge — {tail}"
    elif decisive:
        headline = f"{verdict.value} because {decisive[0].split('] ', 1)[-1]}"
    else:
        tail = (
            report.main_reasons[0] if report.main_reasons else "low coercion on an adequate basis"
        )
        headline = f"{verdict.value}: {tail}"

    return headline, steps, decisive


def narrate_comparison(
    result: ActionComparisonResult,
) -> tuple[str, list[str], str | None, str]:
    """Return ``(headline, why_top_wins, runner_up_id, decisive_layer)`` for a comparison."""
    ranking = result.ranking
    if not ranking:
        return ("No options were compared.", [], None, "")

    top = ranking[0]
    runner = ranking[1] if len(ranking) > 1 else None
    why: list[str] = []

    if result.best_option_id is not None:
        why.append(f"'{top.title}' ranks first because it is {top.primary_reason}.")
    else:
        why.append(
            "No option is morally viable under this policy; the top-ranked option is the "
            "least-bad available, not an endorsement."
        )

    decisive_layer = ""
    if runner is not None:
        if runner.downgrade_reason:
            why.append(f"It is preferred over '{runner.title}' on: {runner.downgrade_reason}.")
            decisive_layer = runner.downgrade_reason
        else:
            why.append(f"'{runner.title}' is close behind on the same factors.")
    if result.rankings_conflict:
        why.append(
            "Note: the immediate-term and long-term rankings disagree, so the choice depends on "
            "the horizon that matters most."
        )

    best_title = result.best_option_title or "(none morally viable)"
    headline = f"Best: {best_title} — {top.primary_reason}"
    return headline, why, (runner.option_id if runner is not None else None), decisive_layer
