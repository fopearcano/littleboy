"""Rendering helpers for an :class:`~littleboy.core.models.EvaluationReport`.

These functions turn a structured report into something a human can read --
either pretty JSON (for machines and logs) or an indented text block (for a
terminal). They add no judgment of their own; they only present what the
evaluator already decided.
"""

from __future__ import annotations

import json

from littleboy.core.models import EvaluationReport


def report_to_dict(report: EvaluationReport) -> dict:
    """Return the report as a plain ``dict`` (enums rendered as their values)."""
    return report.model_dump(mode="json")


def render_json(report: EvaluationReport, *, indent: int = 2) -> str:
    """Render the report as an indented JSON string (the machine-readable form)."""
    return json.dumps(report_to_dict(report), indent=indent, ensure_ascii=False)


def render_text(report: EvaluationReport) -> str:
    """Render the report as a readable, sectioned text block."""
    lines: list[str] = []
    lines.append(f"VERDICT: {report.verdict.value}   [policy: {report.policy_mode.value}]")
    lines.append(
        f"  coercion={report.coercion_score:.2f}  "
        f"data_quality={report.data_quality_score:.2f}  "
        f"evidence={report.evidence_score:.2f}  "
        f"confidence={report.confidence:.2f}  "
        f"uncertainty={report.uncertainty_level.value}"
    )
    if report.explanation:
        lines.append("")
        lines.append(report.explanation)
    if report.consent_status:
        lines.append("")
        lines.append(f"Consent: {report.consent_status}")
    if report.agency_status:
        lines.append(f"Agency:  {report.agency_status}")

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section("Main reasons", report.main_reasons)
    _section("Axioms invoked", report.axioms_invoked)
    _section("Coercion reasoning", report.coercion_reasoning)
    _section("Data-quality reasoning", report.data_quality_reasoning)
    _section("Evidence reasoning", report.evidence_reasoning)

    if report.justification_result is not None:
        jr = report.justification_result
        _section(
            "Coercion justification (Axiom 3)",
            [
                f"is_justified = {jr.is_justified} (confidence {jr.confidence:.2f})",
                *(f"satisfied: {c}" for c in jr.satisfied_conditions),
                *(f"failed: {c}" for c in jr.failed_conditions),
                *(f"unknown: {c}" for c in jr.unknown_conditions),
            ],
        )

    if report.alternatives_analysis is not None:
        aa = report.alternatives_analysis
        _section(
            "Alternatives analysis (Axiom 2)",
            [
                f"evaluated = {aa.evaluated}, count = {aa.count}",
                *(f"feasible less coercive: {a}" for a in aa.feasible_less_coercive),
                *(f"less coercive but infeasible: {a}" for a in aa.infeasible_less_coercive),
                *(f"unquantified: {a}" for a in aa.unquantified),
            ],
        )

    _section("Missing data", report.missing_data)

    if report.reasoning_trace is not None:
        tr = report.reasoning_trace
        applied = [f"{r.rule_id} {r.name}: {r.status.value}/{r.severity.value}" for r in tr.applied]
        _section(f"Applied rules ({tr.policy_mode.value})", applied)
        _section("Blockers", tr.blockers)
        _section("Contradictions", tr.contradictions)
        _section("Confidence adjustments", tr.confidence_adjustments)

    _section("Warnings", report.warnings)

    if report.ethical_experiment is not None:
        ex = report.ethical_experiment
        _section("Recommended next questions", ex.open_questions)

    return "\n".join(lines)
