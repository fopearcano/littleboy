"""Summarising a set of estimated consequences (transparently, under uncertainty)."""

from __future__ import annotations

from littleboy.temporal.models import ConsequenceSet, TemporalConsequenceReport

# A consequence counts toward "worst/best plausible" only above this probability.
_PLAUSIBLE = 0.2
# "High impact" consequence threshold (absolute coercion delta).
_HIGH_IMPACT = 0.5
_LOW_CONFIDENCE = 0.5
_IRREVERSIBLE = 0.3


def assess_consequences(consequence_set: ConsequenceSet | None) -> TemporalConsequenceReport:
    """Summarise a consequence set: expected delta, worst/best plausible, uncertainty."""
    if consequence_set is None or consequence_set.is_empty:
        return TemporalConsequenceReport(
            count=0, reasoning=["no consequence estimates were supplied"]
        )

    cons = consequence_set.consequences
    expected = sum(c.coercion_delta * c.probability for c in cons)
    expected = max(-1.0, min(1.0, expected))

    increases = [
        c.coercion_delta for c in cons if c.coercion_delta > 0 and c.probability >= _PLAUSIBLE
    ]
    reductions = [
        c.coercion_delta for c in cons if c.coercion_delta < 0 and c.probability >= _PLAUSIBLE
    ]
    worst_increase = max(increases) if increases else 0.0
    best_reduction = -min(reductions) if reductions else 0.0

    uncertainty = 1.0 - (sum(c.confidence for c in cons) / len(cons))

    high_impact_low_conf = [
        c.description
        for c in cons
        if abs(c.coercion_delta) >= _HIGH_IMPACT and c.confidence < _LOW_CONFIDENCE
    ]
    irreversible = [
        c.description for c in cons if c.reversibility <= _IRREVERSIBLE and c.coercion_delta > 0
    ]

    reasoning = [
        "consequence estimates are operational, not certain predictions",
        f"expected coercion delta = sum(delta x probability) = {expected:+.2f}",
        f"worst plausible increase = {worst_increase:.2f}; "
        f"best plausible reduction = {best_reduction:.2f}",
        f"mean confidence = {1.0 - uncertainty:.2f} (uncertainty {uncertainty:.2f})",
    ]

    return TemporalConsequenceReport(
        count=len(cons),
        expected_coercion_delta=round(expected, 4),
        worst_plausible_increase=round(worst_increase, 4),
        best_plausible_reduction=round(best_reduction, 4),
        uncertainty_level=round(max(0.0, min(1.0, uncertainty)), 4),
        high_impact_low_confidence=high_impact_low_conf,
        irreversible_consequences=irreversible,
        reasoning=reasoning,
    )
