"""Time-horizon helpers: ordering, aggregation weights, and a soft-OR.

Horizons are semantic, not fixed durations (see :class:`TimeHorizon`). The
weights below say how much each horizon contributes to an aggregate expected
coercion; they are deliberate operational parameters, not moral constants.
"""

from __future__ import annotations

from littleboy.core.enums import TimeHorizon

# Future horizons in order (UNKNOWN/IMMEDIATE handled separately).
FUTURE_HORIZONS = (
    TimeHorizon.SHORT_TERM,
    TimeHorizon.MEDIUM_TERM,
    TimeHorizon.LONG_TERM,
)

# Weights for aggregating per-horizon coercion into an expected total.
HORIZON_WEIGHTS: dict[TimeHorizon, float] = {
    TimeHorizon.IMMEDIATE: 0.30,
    TimeHorizon.SHORT_TERM: 0.25,
    TimeHorizon.MEDIUM_TERM: 0.20,
    TimeHorizon.LONG_TERM: 0.25,
}


def soft_or(values: list[float]) -> float:
    """Combine independent 0..1 signals as a probabilistic OR (``1 - prod(1 - v)``)."""
    product_complement = 1.0
    for v in values:
        product_complement *= 1.0 - v
    return 1.0 - product_complement
