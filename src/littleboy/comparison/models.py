"""Typed models for the LittleBoy comparison engine.

LittleBoy should not only judge one action in isolation; it should compare
several candidate actions and identify the **least coercive morally viable path
under the available evidence**, while exposing uncertainty, missing data,
trade-offs, and contradictions.

These models are pure data structures. The comparison logic lives in
:mod:`littleboy.comparison.engine`, :mod:`littleboy.comparison.dominance`,
:mod:`littleboy.comparison.ranking`, and :mod:`littleboy.comparison.tradeoffs`.
Every comparison preserves the individual :class:`EvaluationReport` for each
option, so nothing is hidden behind a single number.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.models import ActionCase, EvaluationReport


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionOption(_Base):
    """One candidate action in a comparison."""

    option_id: str
    title: str = ""
    description: str = ""
    case: ActionCase
    declared_goal: str | None = Field(
        default=None,
        description="What this option is trying to achieve (used for goal-equivalence).",
    )
    feasibility: float = Field(
        default=1.0, ge=0.0, le=1.0, description="How feasible this option is (1.0 = fully)."
    )
    notes: str = ""


class ActionComparisonSet(_Base):
    """A set of candidate actions to compare, for one situation."""

    title: str
    description: str = ""
    options: list[ActionOption] = Field(default_factory=list)
    policy_mode: PolicyMode = PolicyMode.STANDARD
    context_notes: str = ""


class ActionRankingEntry(_Base):
    """One option's place in the ranking, with the facts that put it there."""

    option_id: str
    title: str
    verdict: Verdict
    rank: int = 0
    is_morally_viable: bool = False
    viable_with_reservations: bool = False

    coercion_score: float = Field(ge=0.0, le=1.0)
    data_quality_score: float = Field(ge=0.0, le=1.0)
    evidence_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    irreversibility: float | None = Field(
        default=None, description="1 - reversibility, or None if reversibility is unknown."
    )
    vulnerability_risk: float | None = Field(
        default=None, description="Vulnerability of the affected agents, or None if unknown."
    )
    linguistic_coercion_score: float = Field(default=0.0, ge=0.0, le=1.0)
    consent_status: str | None = None
    has_feasible_less_coercive: bool = False

    primary_reason: str = ""
    downgrade_reason: str | None = None
    main_reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    tradeoff_notes: list[str] = Field(default_factory=list)


class DominanceResult(_Base):
    """The dominance relation between two options."""

    option_a_id: str
    option_b_id: str
    relation: str = Field(
        description="one of: strict_a_over_b, strict_b_over_a, partial, none, "
        "incomparable_insufficient_data"
    )
    reasons: list[str] = Field(default_factory=list)


class TradeoffAnalysis(_Base):
    """One unresolved trade-off between two options, made explicit."""

    option_a_id: str
    option_b_id: str
    dimension: str
    description: str


class ActionComparisonResult(_Base):
    """The full, auditable result of comparing a set of options."""

    best_option_id: str | None = None
    best_option_title: str | None = None
    policy_mode: PolicyMode

    ranking: list[ActionRankingEntry] = Field(default_factory=list)
    dominated_options: list[str] = Field(default_factory=list)
    non_dominated_options: list[str] = Field(default_factory=list)
    dominance_results: list[DominanceResult] = Field(default_factory=list)
    tradeoffs: list[TradeoffAnalysis] = Field(default_factory=list)

    ranking_stable: bool = True
    data_sensitive: bool = False
    what_could_change_ranking: list[str] = Field(default_factory=list)
    uncertainty_warnings: list[str] = Field(default_factory=list)
    missing_data_summary: list[str] = Field(default_factory=list)

    comparison_explanation: str = ""
    individual_reports: dict[str, EvaluationReport] = Field(default_factory=dict)
