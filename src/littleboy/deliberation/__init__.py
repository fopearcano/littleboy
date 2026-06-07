"""LittleBoy deliberation & value-of-information layer (v0.9).

Two capabilities built *on top of* the evaluator and comparison engine:

1. **Narration** — order the factors that drove a verdict (or put one option on
   top): which were decisive, which merely supporting, which context.
2. **Value of information** — among the things LittleBoy does not know, which
   single one, if resolved, would most change the verdict or reorder the
   comparison? Computed deterministically by re-running the evaluator under
   explicit, auditable counterfactual resolutions; no probabilities are invented.
"""

from __future__ import annotations

from littleboy.deliberation.engine import Deliberator
from littleboy.deliberation.intake import (
    apply_intake_answer,
    run_minimal_intake,
)
from littleboy.deliberation.minimal_case import (
    DEFAULT_QUESTION_COSTS,
    plan_minimal_questions,
    question_cost,
)
from littleboy.deliberation.models import (
    ComparisonDeliberationReport,
    ComparisonInformationValue,
    ComparisonResolutionOutcome,
    DeliberationReport,
    DeliberationStep,
    FactResolution,
    InformationValue,
    IntakeStep,
    IntakeTranscript,
    MinimalFlipSet,
    MinimalQuestionPlan,
    PlannedQuestion,
    ResolutionOutcome,
)
from littleboy.deliberation.narrate import narrate_comparison, narrate_evaluation
from littleboy.deliberation.report import (
    render_comparison_deliberation_json,
    render_comparison_deliberation_text,
    render_deliberation_json,
    render_deliberation_text,
    render_intake_json,
    render_intake_text,
    render_question_plan_json,
    render_question_plan_text,
)
from littleboy.deliberation.voi import (
    apply_field_answer,
    cheapest_flip_set,
    comparison_value_of_information,
    effective_costs,
    expected_cost_first_question,
    expected_questionnaire_cost,
    minimal_flip_sets,
    value_of_information,
    verdict_distance,
)

__all__ = [
    "DEFAULT_QUESTION_COSTS",
    "ComparisonDeliberationReport",
    "ComparisonInformationValue",
    "ComparisonResolutionOutcome",
    "Deliberator",
    "DeliberationReport",
    "DeliberationStep",
    "FactResolution",
    "InformationValue",
    "IntakeStep",
    "IntakeTranscript",
    "MinimalFlipSet",
    "MinimalQuestionPlan",
    "PlannedQuestion",
    "ResolutionOutcome",
    "apply_field_answer",
    "apply_intake_answer",
    "cheapest_flip_set",
    "comparison_value_of_information",
    "effective_costs",
    "expected_cost_first_question",
    "expected_questionnaire_cost",
    "minimal_flip_sets",
    "narrate_comparison",
    "narrate_evaluation",
    "plan_minimal_questions",
    "question_cost",
    "render_comparison_deliberation_json",
    "render_comparison_deliberation_text",
    "render_deliberation_json",
    "render_deliberation_text",
    "render_intake_json",
    "render_intake_text",
    "render_question_plan_json",
    "render_question_plan_text",
    "run_minimal_intake",
    "value_of_information",
    "verdict_distance",
]
