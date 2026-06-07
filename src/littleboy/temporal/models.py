"""Typed models for the LittleBoy temporal & consequence module.

Core thesis: **an action cannot be ethically judged only at the instant it
occurs.** Coercion can be immediate, delayed, cumulative, reversible,
irreversible, visible, hidden, temporary, or self-amplifying, so an action must
be judged across time.

These models are pure data structures depending only on :mod:`littleboy.core.enums`
(so ``core.models`` can embed them without an import cycle). All numbers are
*operational estimates*, not metaphysical truths or certain predictions. A
consequence refers to affected agents by name (strings); the fully-typed agents
live on the surrounding ``ActionCase``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import EpistemicStatus, TimeHorizon


class _TempBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConsequenceEstimate(_TempBase):
    """One estimated consequence of an action at some time horizon.

    ``coercion_delta`` is signed: negative reduces coercion, positive increases
    it, 0 is neutral/unknown. The estimate is only as good as ``probability``,
    ``confidence`` and ``evidence_quality`` say it is.
    """

    description: str
    horizon: TimeHorizon = TimeHorizon.UNKNOWN
    affected_agents: list[str] = Field(default_factory=list)
    coercion_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    probability: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reversibility: float = Field(default=1.0, ge=0.0, le=1.0)
    duration: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = ""


class ConsequenceSet(_TempBase):
    """A set of estimated consequences across time horizons."""

    consequences: list[ConsequenceEstimate] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.consequences


class TemporalPhase(_TempBase):
    """A coarse, directly-supplied coercion estimate for one time horizon."""

    horizon: TimeHorizon
    coercion_estimate: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str = ""
    notes: str = ""


class TemporalProfile(_TempBase):
    """Optional, directly-supplied per-horizon coercion estimates."""

    phases: list[TemporalPhase] = Field(default_factory=list)
    notes: str = ""


class ReversibilityProfile(_TempBase):
    """How (and at what cost) an action's effects could be undone over time."""

    is_reversible: EpistemicStatus = EpistemicStatus.UNKNOWN
    reversibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    time_to_reverse: str | None = None
    cost_to_reverse: float = Field(default=0.0, ge=0.0, le=1.0)
    residual_harm_after_reversal: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_consent_to_reverse: EpistemicStatus = EpistemicStatus.UNKNOWN
    notes: str = ""


class CumulativeCoercionProfile(_TempBase):
    """How a single small coercion can become ethically serious over time.

    A small coercion matters more if it repeats, normalises a pattern, creates
    dependency, becomes policy, expands to more agents, becomes harder to stop,
    trains agents to accept coercion, or sets institutional precedent.
    """

    single_action_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    repetition_likelihood: float = Field(default=0.0, ge=0.0, le=1.0)
    normalization_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    precedent_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    dependency_creation_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    institutionalization_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    escalation_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    affected_population_growth: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str = ""


class TemporalConsequenceReport(_TempBase):
    """A transparent summary of a consequence set."""

    count: int = 0
    expected_coercion_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    worst_plausible_increase: float = Field(default=0.0, ge=0.0, le=1.0)
    best_plausible_reduction: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_level: float = Field(default=0.0, ge=0.0, le=1.0)
    high_impact_low_confidence: list[str] = Field(default_factory=list)
    irreversible_consequences: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)


class TemporalProjectionResult(_TempBase):
    """The full, auditable projection of coercion across time.

    All values are operational estimates under uncertainty, never certain
    predictions.
    """

    has_temporal_data: bool = False
    immediate_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    short_term_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    medium_term_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    long_term_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    cumulative_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_total_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_coercion_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    trend: str = "unknown"  # rising | falling | stable | unknown

    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    stable: bool = True
    reversibility_score: float | None = None

    prevents_greater_future_coercion: bool = False
    creates_long_term_dependency: bool = False
    reversible_now_irreversible_later: bool = False

    high_risk_unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    consequence_report: TemporalConsequenceReport | None = None
