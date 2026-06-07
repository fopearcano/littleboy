"""The comparison engine.

It evaluates every option with the existing :class:`EthicalEvaluator` (it does
not replace it), then derives moral viability, dominance, a layered ranking, and
explicit trade-offs. The result preserves every individual evaluation report and
never collapses the comparison into a single hidden score.
"""

from __future__ import annotations

from littleboy.comparison.dominance import INCOMPARABLE, dominance_matrix
from littleboy.comparison.models import (
    ActionComparisonResult,
    ActionComparisonSet,
    ActionOption,
    ActionRankingEntry,
)
from littleboy.comparison.ranking import is_data_sensitive, rank_options
from littleboy.comparison.report import build_comparison_explanation
from littleboy.comparison.tradeoffs import analyze_tradeoffs
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase, EvaluationReport
from littleboy.rules.policy import PolicyProfile, get_policy

# Below this reversibility an action is treated as substantially irreversible.
_IRREVERSIBLE_THRESHOLD = 0.30


def _irreversibility(case: ActionCase) -> float | None:
    """Return 1 - reversibility for the case (lower reversibility wins), or None."""
    rev: float | None = None
    if case.coercion_profile is not None and case.coercion_profile.reversibility_is_known:
        rev = case.coercion_profile.reversibility
    if case.language_act is not None and case.language_act.context is not None:
        lrev = case.language_act.context.reversibility
        rev = lrev if rev is None else min(rev, lrev)
    return None if rev is None else round(1.0 - rev, 4)


def _vulnerability(case: ActionCase) -> float | None:
    if case.agency_profile is not None:
        return case.agency_profile.vulnerability_level
    return None


def _viability(report: EvaluationReport) -> tuple[bool, bool, list[str]]:
    """Return ``(is_viable, with_reservations, reasons)`` for one option's report."""
    verdict = report.verdict
    if verdict == Verdict.NOT_ACCEPTABLE:
        return False, False, ["the verdict is NOT_ACCEPTABLE"]
    if verdict == Verdict.INSUFFICIENT_DATA:
        return False, False, ["blocked by insufficient or missing critical data"]
    trace = report.reasoning_trace
    if trace is not None and trace.contradictions:
        return False, False, ["an unresolved contradiction remains in the rule trace"]

    reservations = verdict in {Verdict.ACCEPTABLE_WITH_RESERVATIONS, Verdict.ETHICALLY_SUSPICIOUS}
    if trace is not None and trace.blockers:
        reservations = True
    if (
        report.alternatives_analysis is not None
        and report.alternatives_analysis.has_feasible_less_coercive
    ):
        reservations = True
    if report.confidence < 0.5:
        reservations = True
    return True, reservations, []


def _build_entry(option: ActionOption, report: EvaluationReport) -> ActionRankingEntry:
    is_viable, reservations, _reasons = _viability(report)
    linguistic = (
        report.language_analysis.linguistic_coercion_score
        if report.language_analysis is not None
        else 0.0
    )
    has_feasible_alt = bool(
        report.alternatives_analysis is not None
        and report.alternatives_analysis.has_feasible_less_coercive
    )
    return ActionRankingEntry(
        option_id=option.option_id,
        title=option.title or option.option_id,
        verdict=report.verdict,
        is_morally_viable=is_viable,
        viable_with_reservations=reservations,
        coercion_score=report.coercion_score,
        data_quality_score=report.data_quality_score,
        evidence_score=report.evidence_score,
        confidence=report.confidence,
        irreversibility=_irreversibility(option.case),
        vulnerability_risk=_vulnerability(option.case),
        linguistic_coercion_score=linguistic,
        consent_status=option.case.effective_consent_status().value,
        has_feasible_less_coercive=has_feasible_alt,
        main_reasons=list(report.main_reasons),
        blockers=list(report.reasoning_trace.blockers) if report.reasoning_trace else [],
        missing_data=list(report.missing_data),
    )


class ComparisonEngine:
    """Compare a set of candidate actions under a policy profile."""

    def __init__(self, policy_mode: PolicyMode | str | None = None) -> None:
        self.policy_mode = policy_mode

    def compare(self, comparison_set: ActionComparisonSet) -> ActionComparisonResult:
        mode = self.policy_mode or comparison_set.policy_mode
        policy: PolicyProfile = get_policy(mode)
        evaluator = EthicalEvaluator(policy)

        reports: dict[str, EvaluationReport] = {}
        entries: list[ActionRankingEntry] = []
        options_by_id: dict[str, ActionOption] = {}
        for option in comparison_set.options:
            report = evaluator.evaluate(option.case)
            reports[option.option_id] = report
            entries.append(_build_entry(option, report))
            options_by_id[option.option_id] = option

        dominance_results, dominated, non_dominated = dominance_matrix(entries, options_by_id)
        ranked = rank_options(entries, policy)
        tradeoffs = analyze_tradeoffs(ranked, dominance_results, options_by_id)

        # Attach trade-off notes to each entry for convenience.
        for entry in ranked:
            entry.tradeoff_notes = [
                t.description
                for t in tradeoffs
                if entry.option_id in (t.option_a_id, t.option_b_id)
            ]

        top = ranked[0] if ranked else None
        best_id = top.option_id if (top and top.is_morally_viable) else None
        best_title = top.title if (top and top.is_morally_viable) else None

        data_sensitive = (
            is_data_sensitive(ranked, policy)
            or any(e.verdict == Verdict.INSUFFICIENT_DATA for e in ranked)
            or any(r.relation == INCOMPARABLE for r in dominance_results)
        )

        what_could_change = self._what_could_change(ranked, data_sensitive)
        warnings = self._uncertainty_warnings(ranked, data_sensitive, best_id)
        missing_summary = _unique(m for e in ranked for m in e.missing_data)

        result = ActionComparisonResult(
            best_option_id=best_id,
            best_option_title=best_title,
            policy_mode=policy.mode,
            ranking=ranked,
            dominated_options=dominated,
            non_dominated_options=non_dominated,
            dominance_results=dominance_results,
            tradeoffs=tradeoffs,
            ranking_stable=not data_sensitive,
            data_sensitive=data_sensitive,
            what_could_change_ranking=what_could_change,
            uncertainty_warnings=warnings,
            missing_data_summary=missing_summary,
            individual_reports=reports,
        )
        result.comparison_explanation = build_comparison_explanation(result)
        return result

    def _what_could_change(
        self, ranked: list[ActionRankingEntry], data_sensitive: bool
    ) -> list[str]:
        if not ranked:
            return []
        items: list[str] = []
        for entry in ranked[:2]:
            items.extend(entry.missing_data)
        if data_sensitive and not items:
            items.append(
                "the top options are close on coercion/viability; resolving any missing data "
                "could reorder them"
            )
        return _unique(items)

    def _uncertainty_warnings(
        self, ranked: list[ActionRankingEntry], data_sensitive: bool, best_id: str | None
    ) -> list[str]:
        warnings: list[str] = []
        if best_id is None:
            warnings.append(
                "no option is morally viable under this policy; the top-ranked option is the "
                "least-bad, not an endorsement"
            )
        if data_sensitive:
            warnings.append(
                "this ranking is provisional: missing data or a close call between the top "
                "options could change it"
            )
        for entry in ranked:
            if entry.verdict == Verdict.INSUFFICIENT_DATA:
                warnings.append(f"'{entry.title}' could not be judged (insufficient data)")
        return _unique(warnings)


def compare(
    comparison_set: ActionComparisonSet, policy_mode: PolicyMode | str | None = None
) -> ActionComparisonResult:
    """Convenience wrapper: compare a set under an optional policy override."""
    return ComparisonEngine(policy_mode).compare(comparison_set)


def _unique(items) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
