"""Data-quality scoring and uncertainty for LittleBoy.

LittleBoy treats epistemics as an ethical matter (Axiom 5): producing a
confident verdict from poor information is itself a failure. This module turns a
:class:`~littleboy.core.models.DataQualityProfile` into a ``data_quality_score``,
and combines it with the number of *structural unknowns* in a case to produce a
``confidence`` value and a coarse :class:`~littleboy.core.enums.UncertaintyLevel`.

As with coercion scoring, every number here is a transparent heuristic and the
reasoning is always returned alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from littleboy.core.enums import UncertaintyLevel
from littleboy.core.models import DataQualityProfile

# Each named missing critical fact reduces the score by this much (capped).
_MISSING_FACT_PENALTY = 0.2

# Each structural unknown (e.g. consent unknown, agent type unknown) multiplies
# confidence by this factor. Several unknowns compound multiplicatively.
_UNKNOWN_CONFIDENCE_FACTOR = 0.85

# Positive axes that are averaged into the base score (higher = better).
_POSITIVE_AXES: tuple[str, ...] = (
    "completeness",
    "source_reliability",
    "specificity",
    "recency",
    "corroboration",
)


@dataclass
class DataQualityAssessment:
    """The result of scoring a data-quality profile."""

    score: float
    reasoning: list[str] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)


def assess_data_quality(profile: DataQualityProfile | None) -> DataQualityAssessment:
    """Compute a data-quality score in ``[0, 1]`` with an explanation.

    The model, in words::

        base    = mean(completeness, source_reliability, specificity,
                       recency, corroboration)
        score   = base * (1 - ambiguity) * (1 - missing_penalty)

    where ``missing_penalty`` grows with the number of named missing critical
    facts. A missing profile entirely yields a score of 0 with a loud note.
    """
    if profile is None:
        return DataQualityAssessment(
            score=0.0,
            reasoning=["no data-quality profile was supplied; treating quality as 0.00"],
            missing_facts=[],
        )

    reasoning: list[str] = []

    base = sum(getattr(profile, axis) for axis in _POSITIVE_AXES) / len(_POSITIVE_AXES)
    reasoning.append(
        "base = mean({}) = {:.2f}".format(
            ", ".join(f"{axis}={getattr(profile, axis):.2f}" for axis in _POSITIVE_AXES),
            base,
        )
    )

    ambiguity_multiplier = 1.0 - profile.ambiguity
    reasoning.append(
        f"ambiguity penalty: x(1 - {profile.ambiguity:.2f}) = x{ambiguity_multiplier:.2f}"
    )

    missing_penalty = min(1.0, _MISSING_FACT_PENALTY * len(profile.missing_critical_facts))
    missing_multiplier = 1.0 - missing_penalty
    if profile.missing_critical_facts:
        reasoning.append(
            f"{len(profile.missing_critical_facts)} missing critical fact(s): "
            f"x{missing_multiplier:.2f}"
        )

    score = base * ambiguity_multiplier * missing_multiplier
    reasoning.append(f"data_quality_score = {score:.2f}")

    return DataQualityAssessment(
        score=score,
        reasoning=reasoning,
        missing_facts=list(profile.missing_critical_facts),
    )


def compute_confidence(data_quality_score: float, n_structural_unknowns: int) -> float:
    """Combine data quality with structural unknowns into a confidence in ``[0, 1]``.

    Confidence starts at the data-quality score and is reduced multiplicatively
    for each structural unknown (consent unknown, agent type unknown, etc.).
    """
    factor = _UNKNOWN_CONFIDENCE_FACTOR ** max(0, n_structural_unknowns)
    return max(0.0, min(1.0, data_quality_score * factor))


def classify_uncertainty(confidence: float) -> UncertaintyLevel:
    """Map a confidence value to a coarse, human-readable uncertainty level."""
    if confidence >= 0.75:
        return UncertaintyLevel.LOW
    if confidence >= 0.50:
        return UncertaintyLevel.MODERATE
    if confidence >= 0.30:
        return UncertaintyLevel.HIGH
    return UncertaintyLevel.CRITICAL
