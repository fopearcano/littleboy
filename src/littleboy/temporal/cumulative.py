"""Scoring cumulative coercion.

A small single-action coercion can become ethically serious if it repeats,
normalises, creates dependency, becomes institutional precedent, escalates, or
expands to more agents. ``score_cumulative_coercion`` makes that escalation
explicit and transparent.
"""

from __future__ import annotations

from littleboy.temporal.horizon import soft_or
from littleboy.temporal.models import CumulativeCoercionProfile

# The systemic amplifiers (excluding repetition, which gates how strongly they act).
_AMPLIFIER_FIELDS = (
    "normalization_risk",
    "precedent_risk",
    "dependency_creation_risk",
    "institutionalization_risk",
    "escalation_risk",
    "affected_population_growth",
)


def score_cumulative_coercion(profile: CumulativeCoercionProfile) -> float:
    """Return a 0..1 cumulative-coercion score.

    A single small coercion is amplified toward seriousness by the soft-OR of the
    systemic risk factors, gated by how likely the action is to repeat:
    ``single + (1 - single) * amplifiers * (0.5 + 0.5 * repetition)``.
    """
    single = profile.single_action_coercion
    amplifiers = soft_or([getattr(profile, f) for f in _AMPLIFIER_FIELDS])
    repetition_gate = 0.5 + 0.5 * profile.repetition_likelihood
    score = single + (1.0 - single) * amplifiers * repetition_gate
    return max(0.0, min(1.0, score))
