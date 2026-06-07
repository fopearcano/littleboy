"""Typed domain models for the LittleBoy ethical evaluation engine.

This module holds the *pure data structures* of the system: the things a case
is made of and the shape of the report that comes out. It deliberately contains
no scoring or decision logic -- that lives in :mod:`littleboy.core.scoring`,
:mod:`littleboy.core.axioms`, :mod:`littleboy.core.alternatives`,
:mod:`littleboy.core.agency`, :mod:`littleboy.data.quality`,
:mod:`littleboy.data.evidence`, and :mod:`littleboy.core.evaluator`.

All models are Pydantic v2 models so that input (typically JSON) is validated
and normalised before any reasoning happens.

Backward compatibility (v0.1 -> v0.2): the simple ``consent`` enum field, the
boolean-era ``Alternative`` name, and the original ``CoercionProfile`` /
``DataQualityProfile`` all still work. New, richer structures are *added*
alongside them and take precedence when supplied.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import (
    AgentType,
    ConsentStatus,
    EpistemicStatus,
    UncertaintyLevel,
    Verdict,
)
from littleboy.data.evidence import EvidenceSet


class _Base(BaseModel):
    """Shared configuration for every model in LittleBoy.

    ``extra="forbid"`` makes malformed input (e.g. a misspelled JSON key) fail
    loudly rather than being silently ignored -- important for a system whose
    whole point is to be transparent about what it does and does not know.
    """

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Agents
# =============================================================================


class MoralAgent(_Base):
    """Any entity or collective capable of action.

    Whether an agent can be *bound by duties* depends solely on its type
    (Axiom 4): only ``TYPE_II`` agents can. A ``TYPE_I`` agent can still cause
    or suffer coercion, and so still matters to the evaluation -- it simply
    cannot be the bearer of an obligation.
    """

    name: str = Field(description="A short identifier for the agent.")
    agent_type: AgentType | None = Field(
        default=None,
        description="TYPE_I, TYPE_II, or None when the type is unknown.",
    )
    description: str = Field(default="", description="Free-text description of the agent.")
    is_collective: bool = Field(
        default=False,
        description="True if the agent is a group/institution rather than an individual.",
    )

    @property
    def can_bear_duties(self) -> bool:
        """Return True iff this agent can be morally bound by duties (Axiom 4)."""
        return self.agent_type == AgentType.TYPE_II

    @property
    def type_is_known(self) -> bool:
        return self.agent_type is not None


class AgencyProfile(_Base):
    """A richer description of the agency of the agent under scrutiny.

    Where :class:`MoralAgent` records a bare type, this records *how confident*
    we are in that classification and in the agent's capacities, plus a
    vulnerability level. High vulnerability raises scrutiny of consent and
    coercion; an unknown agent type lowers confidence.

    Conceptually this describes the agent whose agency is most decision-relevant
    in the case (typically the affected/at-risk party for ``vulnerability_level``).
    """

    agent_type: AgentType | None = Field(
        default=None, description="TYPE_I, TYPE_II, or None when unknown."
    )
    capacity_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence in the capacity assessment."
    )
    metacognition_evidence: list[str] = Field(
        default_factory=list, description="Evidence of symbolic metacognition, if any."
    )
    language_symbolic_capacity: EpistemicStatus = EpistemicStatus.UNKNOWN
    decision_capacity: EpistemicStatus = EpistemicStatus.UNKNOWN
    vulnerability_level: float = Field(
        default=0.0, ge=0.0, le=1.0, description="How vulnerable the subject is (0..1)."
    )
    notes: str = ""

    @property
    def type_is_known(self) -> bool:
        return self.agent_type is not None

    @property
    def can_bear_duties(self) -> bool:
        return self.agent_type == AgentType.TYPE_II


# =============================================================================
# Coercion
# =============================================================================


class CoercionProfile(_Base):
    """A transparent, multi-axis description of the coercion involved in an action.

    Every axis is a number in ``[0.0, 1.0]`` (with the documented exception of
    ``scope_number_of_agents``, which is a count). The axes are intentionally
    crude: this profile is the *input* to a heuristic score, not a claim of
    precise measurement.

    Channels (the *means* of coercion -- how it is exerted)::

        physical_force, threat, economic_pressure, psychological_pressure,
        informational_manipulation, legal_constraint, social_pressure

    Aggravating factors (how *serious* the coercion is)::

        duration, reversibility, scope_number_of_agents, severity
    """

    # --- Channels: the means by which coercion is exerted (0 = none) ---------
    physical_force: float = Field(default=0.0, ge=0.0, le=1.0)
    threat: float = Field(default=0.0, ge=0.0, le=1.0)
    economic_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    psychological_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    informational_manipulation: float = Field(default=0.0, ge=0.0, le=1.0)
    legal_constraint: float = Field(default=0.0, ge=0.0, le=1.0)
    social_pressure: float = Field(default=0.0, ge=0.0, le=1.0)

    # --- Aggravating factors -------------------------------------------------
    duration: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0.0 = momentary, 1.0 = permanent/ongoing.",
    )
    reversibility: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "How reversible the coercion is: 1.0 = fully reversible, "
            "0.0 = irreversible. None means unknown (this lowers confidence)."
        ),
    )
    scope_number_of_agents: int = Field(
        default=1,
        ge=1,
        description="How many agents are affected. A count, not a 0..1 scale.",
    )
    severity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall severity/harm of the coercion, all-things-considered.",
    )

    @property
    def reversibility_is_known(self) -> bool:
        return self.reversibility is not None

    @property
    def informational_manipulation_present(self) -> bool:
        return self.informational_manipulation > 0.0


class CoercionJustification(_Base):
    """A formal, epistemically-honest claim that a coercive act is justified (Axiom 3).

    v0.2 upgrade: each condition now carries an :class:`EpistemicStatus` rather
    than a bare boolean, so the model can distinguish "this condition is met"
    from "we do not know whether this condition is met". Coercion can be
    *justified* only if every condition is affirmatively established; if
    conditions are merely unknown, LittleBoy must not output confident approval.

    Note on naming: ``no_less_coercive_alternative_available`` is phrased so that
    an affirmative status (CONFIRMED/LIKELY) *supports* justification, keeping
    the polarity consistent across all conditions.
    """

    responds_to_existing_or_imminent_coercion: EpistemicStatus = EpistemicStatus.UNKNOWN
    no_less_coercive_alternative_available: EpistemicStatus = EpistemicStatus.UNKNOWN
    necessity: EpistemicStatus = EpistemicStatus.UNKNOWN
    proportionality: EpistemicStatus = EpistemicStatus.UNKNOWN
    expected_total_coercion_reduction: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description=(
            "Net expected reduction in total system coercion (-1..1). "
            "> 0 supports justification; <= 0 refutes it; None = unknown."
        ),
    )
    cessation_condition_defined: EpistemicStatus = EpistemicStatus.UNKNOWN
    reversibility: EpistemicStatus = EpistemicStatus.UNKNOWN
    justification_notes: str = ""


# =============================================================================
# Data quality, consent
# =============================================================================


class DataQualityProfile(_Base):
    """A description of how trustworthy the information about a case is.

    LittleBoy treats epistemics as first-class: a confident-looking verdict
    built on poor data is itself an ethical failure (Axiom 5). These axes feed
    a data-quality score and an uncertainty level.

    Most axes are in ``[0.0, 1.0]`` where higher is *better* -- except
    ``ambiguity``, where higher is *worse*. ``missing_critical_facts`` is a list
    of named gaps; each named gap both lowers the score and is surfaced to the
    user as missing data.
    """

    completeness: float = Field(
        default=0.5, ge=0.0, le=1.0, description="How complete the available information is."
    )
    source_reliability: float = Field(
        default=0.5, ge=0.0, le=1.0, description="How trustworthy the sources are."
    )
    specificity: float = Field(
        default=0.5, ge=0.0, le=1.0, description="How specific (vs vague) the information is."
    )
    recency: float = Field(
        default=0.5, ge=0.0, le=1.0, description="How current the information is."
    )
    corroboration: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Degree of independent corroboration."
    )
    ambiguity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How ambiguous the information is. HIGHER IS WORSE.",
    )
    missing_critical_facts: list[str] = Field(
        default_factory=list,
        description="Named critical facts that are absent. Each is reported as missing data.",
    )


class ConsentProfile(_Base):
    """A structured model of consent.

    Consent is not a single bit. Valid consent is *informed*, *voluntary*,
    *specific*, and *revocable*. Consent that is coerced or contested is not
    valid consent, and unknown consent must lower confidence. Each dimension
    carries an :class:`EpistemicStatus`.
    """

    status: ConsentStatus = Field(
        default=ConsentStatus.UNKNOWN, description="The headline consent status."
    )
    informed: EpistemicStatus = EpistemicStatus.UNKNOWN
    voluntary: EpistemicStatus = EpistemicStatus.UNKNOWN
    specific: EpistemicStatus = EpistemicStatus.UNKNOWN
    revocable: EpistemicStatus = EpistemicStatus.UNKNOWN
    communicated_by_agent: bool | None = Field(
        default=None, description="Whether consent was communicated by the agent themselves."
    )
    notes: str = ""


# =============================================================================
# Alternatives
# =============================================================================


class AlternativeAction(_Base):
    """A candidate alternative course of action, used to test Axioms 2 and 3.

    Axiom 2 says we should act so the world contains the *least possible*
    coercion. To know whether a coercive act is justified we must know whether a
    less coercive *and feasible* alternative exists. An alternative may carry a
    full ``coercion_profile`` (preferred) or a direct ``estimated_coercion_score``.
    A less coercive option that is not feasible does not, on its own, defeat the
    proposed action.
    """

    title: str = ""
    description: str = ""
    coercion_profile: CoercionProfile | None = Field(
        default=None, description="The coercion this alternative would involve, if characterised."
    )
    estimated_coercion_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="A direct 0..1 coercion estimate, used if no coercion_profile is given.",
    )
    feasibility: float = Field(
        default=1.0, ge=0.0, le=1.0, description="How feasible the alternative is (1.0 = fully)."
    )
    data_quality: DataQualityProfile | None = Field(
        default=None, description="How trustworthy the information about this alternative is."
    )
    expected_risk: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Expected residual risk/harm of the alternative."
    )
    notes: str = ""

    @property
    def label(self) -> str:
        """A human-friendly label (title if present, else description)."""
        return self.title or self.description or "(unnamed alternative)"


# Backward-compatible alias: v0.1 called this ``Alternative``.
Alternative = AlternativeAction


class AlternativeSet(_Base):
    """A collection of candidate alternatives.

    The comparison logic lives in :mod:`littleboy.core.alternatives`; this is the
    transparent container it operates on.
    """

    alternatives: list[AlternativeAction] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.alternatives

    def feasible(self, floor: float) -> list[AlternativeAction]:
        return [a for a in self.alternatives if a.feasibility >= floor]


# =============================================================================
# Structured results embedded in the report
# =============================================================================


class JustificationResult(_Base):
    """The outcome of applying Axiom 3 to a :class:`CoercionJustification`.

    ``is_justified`` is deliberately tri-state: ``True`` (every condition
    affirmatively established), ``False`` (a condition is refuted), or ``None``
    (some condition is unknown -- LittleBoy must not feign approval).
    """

    is_justified: bool | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    satisfied_conditions: list[str] = Field(default_factory=list)
    failed_conditions: list[str] = Field(default_factory=list)
    unknown_conditions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def axiom_id(self) -> str:
        return "A3"


class AlternativeAnalysis(_Base):
    """The outcome of comparing a proposed action against its alternatives."""

    evaluated: bool = Field(description="False if no alternatives were analysed (unknown).")
    count: int = 0
    proposed_coercion_score: float = Field(default=0.0, ge=0.0, le=1.0)
    feasible_less_coercive: list[str] = Field(default_factory=list)
    infeasible_less_coercive: list[str] = Field(default_factory=list)
    unquantified: list[str] = Field(default_factory=list)
    best_feasible_alternative_score: float | None = None
    reasoning: list[str] = Field(default_factory=list)

    @property
    def has_feasible_less_coercive(self) -> bool:
        return bool(self.feasible_less_coercive)


class ExperimentSummary(_Base):
    """A compact summary of the built-in ethical experiment for a single case.

    The full, standalone runner lives in :mod:`littleboy.reasoning.experiment`;
    this is the digest embedded in every report.
    """

    can_be_judged: bool
    provisional_verdict: Verdict
    tested_axioms: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# =============================================================================
# Case input and report output
# =============================================================================


class ActionCase(_Base):
    """The input to an ethical evaluation: a single action to be judged.

    Optional fields that are left as ``None`` mean *genuinely unknown*, and
    LittleBoy will lower its confidence and report the gap. This is deliberate:
    ``None`` ("we don't know") is not the same as a present-but-low value.

    v0.2 adds ``consent_profile``, ``agency_profile``, and ``evidence``. When a
    richer field is supplied it takes precedence over its v0.1 counterpart
    (e.g. ``consent_profile.status`` over ``consent``).
    """

    title: str
    description: str = ""
    acting_agent: MoralAgent | None = Field(
        default=None, description="The agent performing the action. None = unknown."
    )
    affected_agents: list[MoralAgent] = Field(default_factory=list)
    intended_goal: str | None = Field(
        default=None, description="What the acting agent is trying to achieve."
    )
    coercion_profile: CoercionProfile | None = Field(
        default=None, description="The coercion involved in the action. None = not characterised."
    )
    available_alternatives: list[AlternativeAction] | None = Field(
        default=None,
        description=(
            "Alternatives that were considered. None = not analysed (unknown); "
            "an empty list = analysed and none found."
        ),
    )
    data_quality: DataQualityProfile | None = Field(
        default=None,
        description="How trustworthy the case information is. None = not characterised.",
    )
    evidence: EvidenceSet | None = Field(
        default=None, description="Structured evidence backing the case's claims."
    )
    context_notes: str = ""

    # --- Consent and agency --------------------------------------------------
    consent: ConsentStatus = Field(
        default=ConsentStatus.UNKNOWN,
        description="v0.1 headline consent. Superseded by consent_profile when present.",
    )
    consent_profile: ConsentProfile | None = Field(
        default=None, description="Structured consent model (takes precedence over `consent`)."
    )
    agency_profile: AgencyProfile | None = Field(
        default=None, description="Structured agency/vulnerability model for the subject."
    )

    # --- Signals consumed by the axioms and confidence logic -----------------
    responds_to_existing_coercion: bool | None = Field(
        default=None,
        description=(
            "Whether the action is a response to prior/imminent coercion. "
            "None = the coercion source is unknown."
        ),
    )
    prior_coercion_description: str | None = Field(
        default=None, description="Description of the coercion being responded to, if any."
    )
    expected_consequences: str | None = Field(
        default=None, description="Expected consequences of the action. None = unknown."
    )
    justification: CoercionJustification | None = Field(
        default=None, description="A formal Axiom 3 justification, if one is offered."
    )

    def effective_consent_status(self) -> ConsentStatus:
        """The consent status actually in force (profile wins over the bare field)."""
        if self.consent_profile is not None:
            return self.consent_profile.status
        return self.consent

    def effective_agent_type(self) -> AgentType | None:
        """The acting agent's type, preferring the agency profile when it adds info."""
        if self.agency_profile is not None and self.agency_profile.type_is_known:
            return self.agency_profile.agent_type
        if self.acting_agent is not None:
            return self.acting_agent.agent_type
        return None


class EvaluationReport(_Base):
    """The output of an ethical evaluation.

    The report is intentionally verbose. LittleBoy must never be a black box:
    every verdict exposes the axioms it invoked, how it reasoned about coercion,
    evidence and data quality, what was missing, which alternatives it
    considered, and a plain-language explanation.
    """

    verdict: Verdict
    coercion_score: float = Field(ge=0.0, le=1.0)
    data_quality_score: float = Field(ge=0.0, le=1.0)
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(
        ge=0.0, le=1.0, description="How much LittleBoy trusts this verdict, given the inputs."
    )
    uncertainty_level: UncertaintyLevel

    consent_status: str | None = None
    agency_status: str | None = None

    main_reasons: list[str] = Field(default_factory=list)
    coercion_reasoning: list[str] = Field(default_factory=list)
    data_quality_reasoning: list[str] = Field(default_factory=list)
    evidence_reasoning: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    less_coercive_alternatives: list[str] = Field(default_factory=list)
    axioms_invoked: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    justification_result: JustificationResult | None = None
    alternatives_analysis: AlternativeAnalysis | None = None
    ethical_experiment: ExperimentSummary | None = None

    explanation: str = Field(
        default="", description="A clear, non-rhetorical plain-language summary."
    )
