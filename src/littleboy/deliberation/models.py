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


class FactResolution(_DelibBase):
    """One unknown resolved to one concrete value, as part of a joint resolution."""

    field: str
    question: str
    label: str = Field(description="The resolution that contributes to the flip.")


class MinimalFlipSet(_DelibBase):
    """A minimal set of unknowns whose joint resolution would change the verdict.

    *Minimal* means no proper subset of these fields, resolved alone, changes the
    verdict -- it takes all of them together. The ``resolution`` records the
    specific joint counterfactual that achieves the flip.
    """

    fields: list[str]
    size: int
    resolution: list[FactResolution] = Field(default_factory=list)
    resulting_verdict: Verdict
    verdict_distance: float = Field(default=0.0, ge=0.0, le=1.0)
    note: str = ""


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
        description="True if no resolvable combination of unknowns (up to the search size) "
        "would change the verdict.",
    )

    # Multi-fact value of information (v0.10).
    minimal_flip_sets: list[MinimalFlipSet] = Field(default_factory=list)
    smallest_flip_size: int | None = Field(
        default=None,
        description="Size of the smallest combination of unknowns that flips the verdict; "
        "None if no combination up to the search size does.",
    )
    verdict_robust_to_combinations: bool = True
    searched_max_size: int = 0

    notes: list[str] = Field(default_factory=list)


class PlannedQuestion(_DelibBase):
    """A single question worth asking because it could change the verdict."""

    field: str
    question: str
    why_it_matters: str = ""
    category: str = ""
    priority: str = Field(default="medium", description="critical | high | medium")
    value: float = Field(default=0.0, ge=0.0, le=1.0)
    cost: float = Field(default=1.0, ge=0.0, description="Relative cost of obtaining this answer.")
    alone_changes_verdict: bool = False
    in_minimal_set: bool = False
    in_cheapest_set: bool = False
    related_axioms: list[str] = Field(default_factory=list)


class MinimalQuestionPlan(_DelibBase):
    """The smallest, priority-ordered set of questions that could change the verdict.

    Questions that can only lower confidence -- never change the verdict, alone or
    in any minimal combination -- are deliberately omitted: answering them cannot
    settle the case.
    """

    target: str = "evaluation"
    verdict: Verdict | None = None
    confidence: float | None = None
    questions: list[PlannedQuestion] = Field(default_factory=list)
    smallest_flip_size: int | None = None
    cheapest_set: list[str] = Field(
        default_factory=list,
        description="Fields of the lowest-total-cost set whose joint resolution flips the verdict.",
    )
    cheapest_set_cost: float | None = None
    verdict_robust: bool = Field(
        default=True,
        description="True if no resolvable combination of unknowns would change the verdict.",
    )
    notes: list[str] = Field(default_factory=list)


class IntakeStep(_DelibBase):
    """One question asked, and the verdict after the answer was applied."""

    field: str
    question: str
    answer: str
    verdict_after: Verdict | None = None
    confidence_after: float | None = None
    verdict_changed: bool = False


class IntakeTranscript(_DelibBase):
    """The record of an interactive minimal-intake session.

    The loop asks the cheapest verdict-relevant question, applies the answer,
    re-plans, and repeats until the verdict is settled (no remaining unknown could
    change it) or the question budget is exhausted.
    """

    initial_verdict: Verdict | None = None
    final_verdict: Verdict | None = None
    final_confidence: float | None = None
    steps: list[IntakeStep] = Field(default_factory=list)
    settled: bool = Field(
        default=False,
        description="True if it stopped because no remaining unknown could change the verdict.",
    )
    questions_asked: int = 0
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
