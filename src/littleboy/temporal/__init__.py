"""LittleBoy's temporal & consequence module (v0.7).

An action cannot be judged only at the instant it occurs. Coercion can be
immediate, delayed, cumulative, reversible, irreversible, visible, hidden,
temporary, or self-amplifying. This module projects coercion across time
horizons -- deterministically, transparently, and without presenting estimates
as certain predictions.

> An action is ethically unstable if it reduces visible coercion now while
> creating hidden, cumulative, irreversible, or delayed coercion later.
"""

from __future__ import annotations

from littleboy.temporal.consequences import assess_consequences
from littleboy.temporal.cumulative import score_cumulative_coercion
from littleboy.temporal.models import (
    ConsequenceEstimate,
    ConsequenceSet,
    CumulativeCoercionProfile,
    ReversibilityProfile,
    TemporalConsequenceReport,
    TemporalPhase,
    TemporalProfile,
    TemporalProjectionResult,
)
from littleboy.temporal.projection import TemporalProjection, project_temporal
from littleboy.temporal.reversibility import score_reversibility

__all__ = [
    "ConsequenceEstimate",
    "ConsequenceSet",
    "CumulativeCoercionProfile",
    "ReversibilityProfile",
    "TemporalConsequenceReport",
    "TemporalPhase",
    "TemporalProfile",
    "TemporalProjection",
    "TemporalProjectionResult",
    "assess_consequences",
    "project_temporal",
    "score_cumulative_coercion",
    "score_reversibility",
]
