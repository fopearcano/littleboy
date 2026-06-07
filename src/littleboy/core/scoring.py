"""Coercion scoring for LittleBoy.

This module turns a :class:`~littleboy.core.models.CoercionProfile` into a single
``coercion_score`` in ``[0.0, 1.0]``, together with a transparent explanation of
how that number was produced.

    IMPORTANT: this score is a HEURISTIC, not a moral measurement.

It exists to make cases comparable and to drive a first-pass decision rule. It
does not claim that coercion is a real-valued quantity, nor that two acts with
the same score are morally equivalent. Every assumption it makes is recorded in
the returned reasoning so the number is never a black box.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from littleboy.core.models import CoercionProfile

# Human-readable labels for the seven coercion *channels* (the means of coercion).
_CHANNEL_LABELS: tuple[tuple[str, str], ...] = (
    ("physical_force", "physical force"),
    ("threat", "threat"),
    ("economic_pressure", "economic pressure"),
    ("psychological_pressure", "psychological pressure"),
    ("informational_manipulation", "informational manipulation"),
    ("legal_constraint", "legal constraint"),
    ("social_pressure", "social pressure"),
)

# When reversibility is unknown we must assume *something* to produce a number.
# We assume a neutral midpoint and say so loudly in the reasoning.
_ASSUMED_IRREVERSIBILITY_WHEN_UNKNOWN = 0.5

HEURISTIC_DISCLAIMER = "coercion_score is a transparent heuristic, not an absolute moral truth"


@dataclass
class CoercionAssessment:
    """The result of scoring a coercion profile."""

    score: float
    means_intensity: float
    aggravation: float
    dominant_channels: list[str]
    reasoning: list[str] = field(default_factory=list)
    reversibility_known: bool = True


def _soft_or(values: list[float]) -> float:
    """Combine independent 0..1 signals as a probabilistic OR.

    ``1 - prod(1 - v)``. Any single strong signal pushes the result up, and
    multiple signals compound, but the result stays within ``[0, 1]``. This is
    order-independent and fully transparent: each channel's marginal effect is
    easy to see.
    """
    product_complement = 1.0
    for v in values:
        product_complement *= 1.0 - v
    return 1.0 - product_complement


def _scope_factor(number_of_agents: int) -> float:
    """Map a count of affected agents to a 0..1 breadth factor (log-saturating).

    1 agent -> 0.0, 10 -> ~0.33, 1000 -> ~1.0. Coercing more agents is worse,
    but with diminishing marginal effect on the score.
    """
    if number_of_agents <= 1:
        return 0.0
    return min(1.0, math.log10(number_of_agents) / 3.0)


def score_coercion(profile: CoercionProfile) -> CoercionAssessment:
    """Compute a provisional coercion score for a profile.

    The model, in words:

    1. ``means_intensity`` = soft-OR of the seven channels. This captures *how*
       coercion is exerted. If no channel is present it is 0 and the whole score
       is 0 -- aggravating factors cannot manufacture coercion out of nothing.
    2. ``aggravation`` = mean of [duration, irreversibility, scope, severity].
       This captures how *serious* the coercion is.
    3. ``score`` = ``min(1, means_intensity * (1 + aggravation))``. Aggravation
       scales the means by up to 2x, saturating at 1.0.
    """
    reasoning: list[str] = [HEURISTIC_DISCLAIMER]

    channel_values = [getattr(profile, name) for name, _ in _CHANNEL_LABELS]
    means_intensity = _soft_or(channel_values)

    # Identify the channels doing most of the work, for the explanation.
    dominant = sorted(
        ((label, getattr(profile, name)) for name, label in _CHANNEL_LABELS),
        key=lambda pair: pair[1],
        reverse=True,
    )
    dominant_channels = [label for label, value in dominant if value > 0.0]

    if dominant_channels:
        top = ", ".join(f"{label} ({value:.2f})" for label, value in dominant if value > 0.0)
        reasoning.append(f"coercion channels present: {top}")
        reasoning.append(f"combined means intensity (soft-OR) = {means_intensity:.2f}")
    else:
        reasoning.append("no coercion channels are present; means intensity = 0.00")

    # Aggravating factors.
    if profile.reversibility_is_known:
        irreversibility = 1.0 - float(profile.reversibility)  # type: ignore[arg-type]
        reasoning.append(
            f"irreversibility = {irreversibility:.2f} (reversibility = {profile.reversibility:.2f})"
        )
        reversibility_known = True
    else:
        irreversibility = _ASSUMED_IRREVERSIBILITY_WHEN_UNKNOWN
        reasoning.append(
            f"reversibility UNKNOWN; assuming neutral irreversibility = {irreversibility:.2f}"
        )
        reversibility_known = False

    scope = _scope_factor(profile.scope_number_of_agents)
    aggravation = (profile.duration + irreversibility + scope + profile.severity) / 4.0
    reasoning.append(
        f"aggravation = mean(duration={profile.duration:.2f}, "
        f"irreversibility={irreversibility:.2f}, "
        f"scope={scope:.2f} [{profile.scope_number_of_agents} agents], "
        f"severity={profile.severity:.2f}) = {aggravation:.2f}"
    )

    score = min(1.0, means_intensity * (1.0 + aggravation))
    reasoning.append(
        f"score = min(1, means_intensity * (1 + aggravation)) = "
        f"min(1, {means_intensity:.2f} * {1.0 + aggravation:.2f}) = {score:.2f}"
    )

    return CoercionAssessment(
        score=score,
        means_intensity=means_intensity,
        aggravation=aggravation,
        dominant_channels=dominant_channels,
        reasoning=reasoning,
        reversibility_known=reversibility_known,
    )
