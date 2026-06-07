"""Scoring a :class:`ReversibilityProfile`.

Reversibility is not just "can it be undone?" but "how fully, at what cost, and
with what residual harm?". A reversible action is *not* automatically good: a
severe but reversible coercion is still coercion while it lasts.
"""

from __future__ import annotations

from littleboy.core.enums import EpistemicStatus
from littleboy.temporal.models import ReversibilityProfile


def score_reversibility(profile: ReversibilityProfile) -> float:
    """Return an effective reversibility score in ``[0, 1]`` (higher = more reversible).

    Starts from ``reversibility_score``, reduced by the cost to reverse and by
    any residual harm that remains even after reversal. If reversibility is
    epistemically unresolved, the score is pulled toward the cautious middle.
    """
    base = profile.reversibility_score
    if profile.is_reversible == EpistemicStatus.CONFIRMED:
        pass
    elif profile.is_reversible == EpistemicStatus.LIKELY:
        base *= 0.9
    elif profile.is_reversible.is_unresolved:
        base = min(base, 0.5)  # do not credit unverified reversibility
    elif profile.is_reversible == EpistemicStatus.DISPUTED:
        base *= 0.6

    effective = (
        base
        * (1.0 - 0.3 * profile.cost_to_reverse)
        * (1.0 - 0.5 * profile.residual_harm_after_reversal)
    )
    return max(0.0, min(1.0, effective))
