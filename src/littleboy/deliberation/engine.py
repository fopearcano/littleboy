"""The :class:`Deliberator`: narrate the verdict and compute the value of information.

It builds on the existing :class:`EthicalEvaluator` and :class:`ComparisonEngine`
(it does not replace them): it evaluates normally, narrates *why* the verdict (or
the top-ranked option) came out as it did, and then probes every genuine unknown
by re-evaluating under explicit counterfactual resolutions to find the single
fact that would most change the outcome.
"""

from __future__ import annotations

from littleboy.comparison.engine import ComparisonEngine
from littleboy.comparison.models import ActionComparisonSet
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase
from littleboy.deliberation.minimal_case import plan_minimal_questions
from littleboy.deliberation.models import (
    ComparisonDeliberationReport,
    DeliberationReport,
    MinimalQuestionPlan,
)
from littleboy.deliberation.narrate import narrate_comparison, narrate_evaluation
from littleboy.deliberation.voi import (
    comparison_value_of_information,
    minimal_flip_sets,
    value_of_information,
)
from littleboy.rules.policy import PolicyMode, PolicyProfile

# How many unknowns to combine when searching for a verdict flip (kept small: the
# search is exhaustive over subsets and their joint resolutions).
_MAX_FLIP_SET_SIZE = 3


class Deliberator:
    """Deliberate over an evaluation or a comparison: narration plus value of information."""

    def __init__(self, policy: PolicyMode | PolicyProfile | str | None = None) -> None:
        self.policy = policy

    def _probe_evaluator(self) -> EthicalEvaluator:
        # A lighter evaluator for the many counterfactual re-runs (no completeness pass).
        return EthicalEvaluator(self.policy, include_completeness=False)

    def deliberate(self, case: ActionCase) -> DeliberationReport:
        """Narrate a verdict, rank unknowns by value of information, and find minimal flip sets."""
        report = EthicalEvaluator(self.policy).evaluate(case)
        probe_evaluator = self._probe_evaluator()
        ivs = value_of_information(case, probe_evaluator)
        flip_sets, smallest = minimal_flip_sets(case, probe_evaluator, max_size=_MAX_FLIP_SET_SIZE)

        headline, steps, decisive = narrate_evaluation(report)
        most = ivs[0] if ivs else None
        stable = smallest is None

        notes = [
            "value of information is measured by re-running the deterministic evaluator under "
            "explicit counterfactual resolutions -- no probabilities are invented",
        ]
        if not ivs:
            notes.append(
                "the case has no material unknowns to probe; its verdict is information-stable"
            )
        elif stable:
            notes.append(
                "no resolvable combination of unknowns (searched up to "
                f"{_MAX_FLIP_SET_SIZE}) would change the verdict (some lower confidence)"
            )
        elif smallest is not None and smallest >= 2:
            notes.append(
                "no single unknown changes the verdict; the smallest sufficient combination has "
                f"{smallest} facts"
            )

        return DeliberationReport(
            target="evaluation",
            headline=headline,
            verdict=report.verdict,
            confidence=report.confidence,
            steps=steps,
            decisive_factors=decisive,
            information_values=ivs,
            most_informative=most,
            stable_under_information=stable,
            minimal_flip_sets=flip_sets,
            smallest_flip_size=smallest,
            verdict_robust_to_combinations=stable,
            searched_max_size=_MAX_FLIP_SET_SIZE,
            notes=notes,
        )

    def question_plan(self, case: ActionCase) -> MinimalQuestionPlan:
        """Return only the questions that could change the verdict, in priority order."""
        return plan_minimal_questions(case, self._probe_evaluator(), max_size=_MAX_FLIP_SET_SIZE)

    def deliberate_comparison(
        self, comparison_set: ActionComparisonSet
    ) -> ComparisonDeliberationReport:
        """Narrate why the top option wins and find the fact that would most change the winner."""
        engine = ComparisonEngine(self.policy)
        result = engine.compare(comparison_set)
        ivs = comparison_value_of_information(comparison_set, engine)

        headline, why_top_wins, runner_up_id, decisive_layer = narrate_comparison(result)
        most = ivs[0] if ivs else None
        robust = not (most is not None and most.changes_best_option)

        notes = [
            "value of information is measured by re-running the comparison with one option's "
            "unknown resolved -- no probabilities are invented",
        ]
        if robust and result.best_option_id is not None:
            notes.append("no single resolvable unknown would change the winner")

        return ComparisonDeliberationReport(
            target="comparison",
            headline=headline,
            best_option_id=result.best_option_id,
            best_option_title=result.best_option_title,
            runner_up_id=runner_up_id,
            decisive_layer=decisive_layer,
            why_top_wins=why_top_wins,
            information_values=ivs,
            most_informative=most,
            ranking_robust=robust,
            notes=notes,
        )
