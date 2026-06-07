"""Typed models for the LittleBoy deliberation & value-of-information layer (v0.9).

Deliberation answers two questions a bare verdict does not:

1. **Why** did the verdict (or the top-ranked option) come out the way it did --
   which factors were decisive, and which merely contributed?
2. **What single missing fact would most change it?** -- the *value of
   information*: among the things LittleBoy does not know, which one, if
   resolved, would most move the verdict or reorder the comparison?

These are pure data structures. The logic that fills them (counterfactual
probing, narration) lives in :mod:`littleboy.deliberation.voi`,
:mod:`littleboy.deliberation.narrate`, and :mod:`littleboy.deliberation.engine`.
Nothing here predicts the future or calls a model; the value of information is
computed by *actually re-running the deterministic evaluator* under explicit,
auditable counterfactual resolutions.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import Verdict


class _DelibBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResolutionOutcome(_DelibBase):
    """The result of resolving one unknown to one concrete value (a counterfactual)."""

    label: str = Field(description="The resolution tried, e.g. 'consent = REFUSED'.")
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    verdict_changed: bool = Field(description="True if this differs from the baseline verdict.")
    note: str = ""


class InformationValue(_DelibBase):
    """How much resolving one currently-unknown fact could change the verdict.

    The ``value`` is a 0..1 score derived by re-evaluating the case under each
    plausible resolution and measuring the swing in verdict and confidence. It is
    an *operational* measure of decision-relevance, not a probability.
    """

    field: str = Field(description="The probe/field, e.g. 'consent' or 'coercion.reversibility'.")
    question: str = Field(description="A plain question that would resolve this unknown.")
    why_it_matters: str = ""
    value: float = Field(default=0.0, ge=0.0, le=1.0)
    changes_verdict: bool = False
    swing: str = Field(default="", description="A one-line summary of the verdict swing.")
    resolutions: list[ResolutionOutcome] = Field(default_factory=list)
    related_axioms: list[str] = Field(default_factory=list)


class DeliberationStep(_DelibBase):
    """One step in the explanation of why the verdict came out as it did."""

    claim: str
    basis: str = Field(default="", description="The rule id, score, or axiom behind the claim.")
    kind: str = Field(default="supporting", description="decisive | supporting | context")


class DeliberationReport(_DelibBase):
    """A full, auditable deliberation over a single evaluation."""

    target: str = "evaluation"
    headline: str = ""
    verdict: Verdict | None = None
    confidence: float | None = None

    steps: list[DeliberationStep] = Field(default_factory=list)
    decisive_factors: list[str] = Field(default_factory=list)

    information_values: list[InformationValue] = Field(default_factory=list)
    most_informative: InformationValue | None = None
    stable_under_information: bool = Field(
        default=True,
        description="True if no single resolvable unknown would change the verdict.",
    )

    notes: list[str] = Field(default_factory=list)


class ComparisonResolutionOutcome(_DelibBase):
    """The result of resolving one unknown of one option, for a comparison."""

    label: str
    best_option_id: str | None = None
    best_option_changed: bool = False
    note: str = ""


class ComparisonInformationValue(_DelibBase):
    """How much resolving one option's unknown could change the comparison's winner."""

    option_id: str
    field: str
    question: str
    why_it_matters: str = ""
    value: float = Field(default=0.0, ge=0.0, le=1.0)
    changes_best_option: bool = False
    swing: str = ""
    resolutions: list[ComparisonResolutionOutcome] = Field(default_factory=list)


class ComparisonDeliberationReport(_DelibBase):
    """A full, auditable deliberation over a comparison."""

    target: str = "comparison"
    headline: str = ""
    best_option_id: str | None = None
    best_option_title: str | None = None
    runner_up_id: str | None = None
    decisive_layer: str = Field(
        default="",
        description="The first lexicographic layer on which the runner-up lost to the winner.",
    )
    why_top_wins: list[str] = Field(default_factory=list)

    information_values: list[ComparisonInformationValue] = Field(default_factory=list)
    most_informative: ComparisonInformationValue | None = None
    ranking_robust: bool = Field(
        default=True,
        description="True if no single resolvable unknown would change the winner.",
    )

    notes: list[str] = Field(default_factory=list)
