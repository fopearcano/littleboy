"""Rendering of a :class:`TemporalProjectionResult` (for the ``temporal`` command)."""

from __future__ import annotations

import json

from littleboy.temporal.models import TemporalProjectionResult


def temporal_to_dict(result: TemporalProjectionResult) -> dict:
    return result.model_dump(mode="json")


def render_temporal_json(result: TemporalProjectionResult, *, indent: int = 2) -> str:
    return json.dumps(temporal_to_dict(result), indent=indent, ensure_ascii=False)


def render_temporal_text(result: TemporalProjectionResult) -> str:
    """Render the temporal projection as a readable, sectioned text block."""
    lines = [
        f"TEMPORAL PROJECTION (trend: {result.trend}, stable: {result.stable})",
        f"  immediate={result.immediate_coercion:.2f}  short={result.short_term_coercion:.2f}  "
        f"medium={result.medium_term_coercion:.2f}  long={result.long_term_coercion:.2f}",
        f"  cumulative={result.cumulative_coercion:.2f}  "
        f"expected_total={result.expected_total_coercion:.2f}  "
        f"expected_delta={result.expected_coercion_delta:+.2f}  "
        f"uncertainty={result.uncertainty:.2f}",
    ]
    rev = "unknown" if result.reversibility_score is None else f"{result.reversibility_score:.2f}"
    lines.append(f"  reversibility={rev}")
    lines.append(
        f"  prevents_greater_future_coercion={result.prevents_greater_future_coercion}  "
        f"creates_long_term_dependency={result.creates_long_term_dependency}  "
        f"reversible_now_irreversible_later={result.reversible_now_irreversible_later}"
    )

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section("High-risk unknowns", result.high_risk_unknowns)
    _section("Warnings", result.warnings)
    _section("Missing temporal data", result.missing_data)
    _section("Reasoning", result.reasoning)
    if result.consequence_report is not None:
        cr = result.consequence_report
        _section(
            "Consequence summary",
            [
                f"{cr.count} consequence(s); expected delta {cr.expected_coercion_delta:+.2f}",
                f"worst plausible increase {cr.worst_plausible_increase:.2f}; "
                f"best plausible reduction {cr.best_plausible_reduction:.2f}",
                *(f"high-impact / low-confidence: {d}" for d in cr.high_impact_low_confidence),
                *(f"irreversible: {d}" for d in cr.irreversible_consequences),
            ],
        )
    return "\n".join(lines)
