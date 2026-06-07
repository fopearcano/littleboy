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
    """Render the report as an indented JSON string."""
    return json.dumps(report_to_dict(report), indent=indent, ensure_ascii=False)


def render_text(report: EvaluationReport) -> str:
    """Render the report as a readable, sectioned text block."""
    lines: list[str] = []
    lines.append(f"VERDICT: {report.verdict.value}")
    lines.append(
        f"  coercion_score={report.coercion_score:.2f}  "
        f"data_quality_score={report.data_quality_score:.2f}  "
        f"confidence={report.confidence:.2f}  "
        f"uncertainty={report.uncertainty_level.value}"
    )

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
    _section("Missing data", report.missing_data)
    _section("Less coercive alternatives", report.less_coercive_alternatives)
    _section("Warnings", report.warnings)
    return "\n".join(lines)
