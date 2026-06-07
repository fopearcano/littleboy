"""Typed domain models for the LittleBoy ethical evaluation engine.

This module holds the *pure data structures* of the system: the things a case
is made of and the shape of the report that comes out. It deliberately contains
no scoring or decision logic -- that lives in :mod:`littleboy.core.scoring`,
:mod:`littleboy.data.quality`, and :mod:`littleboy.core.evaluator`.

All models are Pydantic v2 models so that input (typically JSON) is validated
and normalised before any reasoning happens.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import (
    AgentType,
    ConsentStatus,
    UncertaintyLevel,
    Verdict,
)


class _Base(BaseModel):
    """Shared configuration for every model in LittleBoy.

    ``extra="forbid"`` makes malformed input (e.g. a misspelled JSON key) fail
    loudly rather than being silently ignored -- important for a system whose
    whole point is to be transparent about what it does and does not know.
    """

    model_config = ConfigDict(extra="forbid")


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


class Alternative(_Base):
    """A candidate alternative course of action, used to test Axiom 3.

    Axiom 2 says we should act so the world contains the *least possible*
    coercion. To know whether a coercive act is justified we must know whether a
    less coercive alternative exists. An alternative may carry its own
    ``coercion_profile``; if it does, LittleBoy can compare it to the main action.
    """

    description: str
    coercion_profile: CoercionProfile | None = Field(
        default=None,
        description="The coercion this alternative would itself involve, if known.",
    )
    feasibility: float = Field(
        default=1.0, ge=0.0, le=1.0, description="How feasible the alternative is (1.0 = fully)."
    )
    notes: str = ""


class CoercionJustification(_Base):
    """A structured claim that a coercive act is justified, per Axiom 3.

    Coercion is ethically justified *only if all five* conditions hold. This
    model records the claim; :mod:`littleboy.core.axioms` checks it. A claim is
    not proof -- LittleBoy still weighs it against the available evidence (e.g.
    whether alternatives were actually analysed).
    """

    responds_to_existing_coercion: bool = Field(
        description="The act responds to existing or imminent coercion."
    )
    no_less_coercive_alternative: bool = Field(
        description="There is no less coercive available alternative."
    )
    necessary_for_lower_total_coercion: bool = Field(
        description="The act is necessary to obtain lower total coercion in the system."
    )
    proportional: bool = Field(description="The coercion is proportional.")
    stops_when_neutralized: bool = Field(
        description="The coercion stops once the original coercion is neutralized."
    )
    rationale: str = Field(default="", description="Free-text justification narrative.")


class ActionCase(_Base):
    """The input to an ethical evaluation: a single action to be judged.

    Optional fields that are left as ``None`` mean *genuinely unknown*, and
    LittleBoy will lower its confidence and report the gap. This is deliberate:
    ``None`` ("we don't know") is not the same as a present-but-low value.
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
    available_alternatives: list[Alternative] | None = Field(
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
    context_notes: str = ""

    # --- Additional signals consumed by the axioms and confidence logic ------
    consent: ConsentStatus = Field(
        default=ConsentStatus.UNKNOWN,
        description="Whether affected agents consented.",
    )
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
        default=None, description="A structured Axiom 3 justification, if one is offered."
    )


class EvaluationReport(_Base):
    """The output of an ethical evaluation.

    The report is intentionally verbose. LittleBoy must never be a black box:
    every verdict exposes the axioms it invoked, how it reasoned about coercion
    and data quality, what was missing, and which alternatives it considered.
    """

    verdict: Verdict
    coercion_score: float = Field(ge=0.0, le=1.0)
    data_quality_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(
        ge=0.0, le=1.0, description="How much LittleBoy trusts this verdict, given the inputs."
    )
    uncertainty_level: UncertaintyLevel

    main_reasons: list[str] = Field(default_factory=list)
    coercion_reasoning: list[str] = Field(default_factory=list)
    data_quality_reasoning: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    less_coercive_alternatives: list[str] = Field(default_factory=list)
    axioms_invoked: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
