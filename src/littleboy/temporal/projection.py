"""Projecting coercion across time.

``project_temporal`` combines the supplied consequence estimates, optional
per-horizon profile, reversibility profile, and cumulative-coercion profile with
the action's immediate coercion into a transparent
:class:`TemporalProjectionResult`. It distinguishes the ethically important
temporal patterns (low now / high later, high now / prevents worse, reversible
now / irreversible later, inaction that permits coercion to continue) and never
presents an estimate as a certain prediction.

It takes the temporal sub-models and a ``base_coercion`` float rather than the
whole ``ActionCase``, so this module depends only on the temporal models and
``core.enums`` -- no import cycle with ``core.models``.
"""

from __future__ import annotations

from littleboy.core.enums import TimeHorizon
from littleboy.temporal.consequences import assess_consequences
from littleboy.temporal.cumulative import score_cumulative_coercion
from littleboy.temporal.horizon import HORIZON_WEIGHTS
from littleboy.temporal.models import (
    ConsequenceSet,
    CumulativeCoercionProfile,
    ReversibilityProfile,
    TemporalProfile,
    TemporalProjectionResult,
)
from littleboy.temporal.reversibility import score_reversibility

_RISING = 0.10  # long-term must exceed immediate by this to count as "rising"
_CREDIBLE_PROB = 0.3
_CREDIBLE_CONF = 0.4
_IRREVERSIBLE = 0.3


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _horizon_coercion(
    base: float,
    horizon: TimeHorizon,
    consequences: list,
    temporal_profile: TemporalProfile | None,
) -> float:
    """Coercion at one horizon = base + summed consequence deltas, raised by any phase."""
    delta = sum(c.coercion_delta * c.probability for c in consequences if c.horizon == horizon)
    value = _clamp(base + delta)
    if temporal_profile is not None:
        for phase in temporal_profile.phases:
            if phase.horizon == horizon:
                value = max(value, phase.coercion_estimate)
    return value


def project_temporal(
    *,
    base_coercion: float,
    consequences: ConsequenceSet | None = None,
    temporal_profile: TemporalProfile | None = None,
    reversibility_profile: ReversibilityProfile | None = None,
    cumulative_profile: CumulativeCoercionProfile | None = None,
    is_inaction: bool = False,
) -> TemporalProjectionResult:
    """Project coercion across time horizons from the supplied temporal inputs."""
    cons = consequences.consequences if consequences is not None else []
    has_data = bool(
        cons
        or (temporal_profile is not None and temporal_profile.phases)
        or reversibility_profile is not None
        or cumulative_profile is not None
    )

    if not has_data:
        return TemporalProjectionResult(
            has_temporal_data=False,
            immediate_coercion=round(base_coercion, 4),
            short_term_coercion=round(base_coercion, 4),
            medium_term_coercion=round(base_coercion, 4),
            long_term_coercion=round(base_coercion, 4),
            expected_total_coercion=round(base_coercion, 4),
            trend="unknown",
            uncertainty=0.0,
            missing_data=[
                "temporal consequences not characterised",
                "reversibility over time not characterised",
                "cumulative/repetition risk not assessed",
            ],
            reasoning=["no temporal data supplied; only the immediate action was assessed"],
        )

    report = assess_consequences(consequences) if cons else None

    immediate = _horizon_coercion(base_coercion, TimeHorizon.IMMEDIATE, cons, temporal_profile)
    short = _horizon_coercion(base_coercion, TimeHorizon.SHORT_TERM, cons, temporal_profile)
    medium = _horizon_coercion(base_coercion, TimeHorizon.MEDIUM_TERM, cons, temporal_profile)
    long_term = _horizon_coercion(base_coercion, TimeHorizon.LONG_TERM, cons, temporal_profile)

    cumulative = score_cumulative_coercion(cumulative_profile) if cumulative_profile else 0.0

    weighted = (
        HORIZON_WEIGHTS[TimeHorizon.IMMEDIATE] * immediate
        + HORIZON_WEIGHTS[TimeHorizon.SHORT_TERM] * short
        + HORIZON_WEIGHTS[TimeHorizon.MEDIUM_TERM] * medium
        + HORIZON_WEIGHTS[TimeHorizon.LONG_TERM] * long_term
    )
    expected_total = _clamp(weighted + (1.0 - weighted) * 0.5 * cumulative)

    if long_term > immediate + _RISING:
        trend = "rising"
    elif long_term < immediate - _RISING:
        trend = "falling"
    else:
        trend = "stable"

    reversibility_score = (
        score_reversibility(reversibility_profile) if reversibility_profile is not None else None
    )

    prevents_future = any(
        c.coercion_delta <= -0.3
        and c.probability >= _CREDIBLE_PROB
        and c.confidence >= _CREDIBLE_CONF
        and c.horizon in (TimeHorizon.SHORT_TERM, TimeHorizon.MEDIUM_TERM, TimeHorizon.LONG_TERM)
        for c in cons
    )
    creates_dependency = (
        cumulative_profile is not None and cumulative_profile.dependency_creation_risk >= 0.5
    )
    reversible_now = reversibility_score is not None and reversibility_score >= 0.6
    irreversible_later = any(
        c.reversibility <= _IRREVERSIBLE
        and c.horizon in (TimeHorizon.MEDIUM_TERM, TimeHorizon.LONG_TERM)
        for c in cons
    )
    reversible_now_irreversible_later = reversible_now and irreversible_later

    # Uncertainty from the available signals.
    unc_signals: list[float] = []
    if report is not None:
        unc_signals.append(report.uncertainty_level)
    if reversibility_profile is not None and reversibility_profile.is_reversible.is_unresolved:
        unc_signals.append(0.6)
    if not cons and (temporal_profile is None or not temporal_profile.phases):
        unc_signals.append(0.6)
    uncertainty = sum(unc_signals) / len(unc_signals) if unc_signals else 0.3

    high_risk_unknowns: list[str] = []
    if report is not None:
        high_risk_unknowns.extend(report.high_impact_low_confidence)
    if any(
        c.horizon == TimeHorizon.LONG_TERM
        and c.evidence_quality < 0.4
        and abs(c.coercion_delta) >= 0.3
        for c in cons
    ):
        high_risk_unknowns.append("long-term consequences are weakly evidenced")

    stable = uncertainty < 0.5 and not high_risk_unknowns

    warnings: list[str] = []
    if trend == "rising":
        warnings.append(
            "the action reduces visible coercion now while plausibly increasing coercion later "
            "(temporally unstable)"
            if immediate < long_term
            else "coercion plausibly increases over time"
        )
    if reversible_now_irreversible_later:
        warnings.append("the action is reversible now but may become irreversible later")
    if creates_dependency:
        warnings.append("the action risks creating long-term dependency")
    if report is not None and report.irreversible_consequences:
        warnings.append(
            "irreversible consequence(s): " + "; ".join(report.irreversible_consequences)
        )
    if is_inaction and (expected_total >= 0.3 or (report and report.expected_coercion_delta > 0)):
        warnings.append(
            "inaction is not neutral here: it permits existing coercion to continue or grow"
        )

    missing_data: list[str] = []
    if not cons and (temporal_profile is None or not temporal_profile.phases):
        missing_data.append("no per-horizon consequence estimates were supplied")
    if reversibility_profile is None:
        missing_data.append("reversibility over time not characterised")
    if cumulative_profile is None:
        missing_data.append("cumulative/repetition risk not assessed")

    reasoning = [
        "temporal estimates are operational, not certain predictions",
        f"per-horizon coercion: immediate {immediate:.2f}, short {short:.2f}, "
        f"medium {medium:.2f}, long {long_term:.2f}",
        f"cumulative coercion {cumulative:.2f}; expected total across time "
        f"{expected_total:.2f}; trend {trend}",
    ]

    return TemporalProjectionResult(
        has_temporal_data=True,
        immediate_coercion=round(immediate, 4),
        short_term_coercion=round(short, 4),
        medium_term_coercion=round(medium, 4),
        long_term_coercion=round(long_term, 4),
        cumulative_coercion=round(cumulative, 4),
        expected_total_coercion=round(expected_total, 4),
        expected_coercion_delta=(report.expected_coercion_delta if report else 0.0),
        trend=trend,
        uncertainty=round(_clamp(uncertainty), 4),
        stable=stable,
        reversibility_score=(
            round(reversibility_score, 4) if reversibility_score is not None else None
        ),
        prevents_greater_future_coercion=prevents_future,
        creates_long_term_dependency=creates_dependency,
        reversible_now_irreversible_later=reversible_now_irreversible_later,
        high_risk_unknowns=high_risk_unknowns,
        warnings=warnings,
        missing_data=missing_data,
        reasoning=reasoning,
        consequence_report=report,
    )


class TemporalProjection:
    """Thin, reusable wrapper around :func:`project_temporal`."""

    def project(self, **kwargs) -> TemporalProjectionResult:
        return project_temporal(**kwargs)
