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
from littleboy.deliberation.models import (
    ComparisonDeliberationReport,
    ComparisonInformationValue,
    ComparisonResolutionOutcome,
    DeliberationReport,
    DeliberationStep,
    InformationValue,
    ResolutionOutcome,
)
from littleboy.deliberation.narrate import narrate_comparison, narrate_evaluation
from littleboy.deliberation.report import (
    render_comparison_deliberation_json,
    render_comparison_deliberation_text,
    render_deliberation_json,
    render_deliberation_text,
)
from littleboy.deliberation.voi import (
    comparison_value_of_information,
    value_of_information,
    verdict_distance,
)

__all__ = [
    "ComparisonDeliberationReport",
    "ComparisonInformationValue",
    "ComparisonResolutionOutcome",
    "Deliberator",
    "DeliberationReport",
    "DeliberationStep",
    "InformationValue",
    "ResolutionOutcome",
    "comparison_value_of_information",
    "narrate_comparison",
    "narrate_evaluation",
    "render_comparison_deliberation_json",
    "render_comparison_deliberation_text",
    "render_deliberation_json",
    "render_deliberation_text",
    "value_of_information",
    "verdict_distance",
]
