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
from littleboy.deliberation.models import (
    ComparisonDeliberationReport,
    DeliberationReport,
)
from littleboy.deliberation.narrate import narrate_comparison, narrate_evaluation
from littleboy.deliberation.voi import (
    comparison_value_of_information,
    value_of_information,
)
from littleboy.rules.policy import PolicyMode, PolicyProfile


class Deliberator:
    """Deliberate over an evaluation or a comparison: narration plus value of information."""

    def __init__(self, policy: PolicyMode | PolicyProfile | str | None = None) -> None:
        self.policy = policy

    def deliberate(self, case: ActionCase) -> DeliberationReport:
        """Narrate a single case's verdict and rank its unknowns by value of information."""
        report = EthicalEvaluator(self.policy).evaluate(case)
        # A lighter evaluator for the many counterfactual re-runs (no completeness pass).
        probe_evaluator = EthicalEvaluator(self.policy, include_completeness=False)
        ivs = value_of_information(case, probe_evaluator)

        headline, steps, decisive = narrate_evaluation(report)
        most = ivs[0] if ivs else None
        stable = not (most is not None and most.changes_verdict)

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
                "no single resolvable unknown would change the verdict "
                "(but several lower confidence)"
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
            notes=notes,
        )

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
