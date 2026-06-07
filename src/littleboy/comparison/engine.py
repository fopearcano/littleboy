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
    t = report.temporal_projection
    has_temporal = bool(t is not None and t.has_temporal_data)
    expected_total = t.expected_total_coercion if has_temporal else report.coercion_score
    long_term = t.long_term_coercion if has_temporal else report.coercion_score
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
        expected_total_coercion=round(expected_total, 4),
        long_term_coercion=round(long_term, 4),
        cumulative_coercion=(t.cumulative_coercion if has_temporal else 0.0),
        temporal_trend=(t.trend if has_temporal else "unknown"),
        temporal_present=has_temporal,
        temporal_stable=(t.stable if has_temporal else True),
    )


def _immediate_key(entry: ActionRankingEntry) -> tuple:
    # Immediate view: order by the coercion right now (not the temporal-laden verdict),
    # so a genuine immediate-vs-long-term conflict can surface.
    return (round(entry.coercion_score * 10), round(1 - entry.confidence, 4), entry.option_id)


def _long_term_key(entry: ActionRankingEntry) -> tuple:
    return (
        round(entry.expected_total_coercion * 10),
        round(entry.cumulative_coercion * 5),
        round(1 - entry.confidence, 4),
        entry.option_id,
    )


class ComparisonEngine:
    """Compare a set of candidate actions under a policy profile."""

    def __init__(self, policy_mode: PolicyMode | str | None = None) -> None:
        self.policy_mode = policy_mode

    def compare(
        self, comparison_set: ActionComparisonSet, *, audit: bool = False
    ) -> ActionComparisonResult:
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

        # Immediate vs long-term views, and whether they conflict (v0.7).
        immediate_ranking = [e.option_id for e in sorted(entries, key=_immediate_key)]
        long_term_ranking = [e.option_id for e in sorted(entries, key=_long_term_key)]
        rankings_conflict = immediate_ranking != long_term_ranking
        temporal_missing = _unique(
            f"{oid}: {m}"
            for oid, rep in reports.items()
            if rep.temporal_projection is not None and rep.temporal_projection.has_temporal_data
            for m in rep.temporal_projection.missing_data
        )

        warnings = self._uncertainty_warnings(ranked, data_sensitive, best_id)
        if rankings_conflict:
            warnings.append(
                "the immediate-term and long-term rankings disagree; the choice depends on the "
                "time horizon that matters most"
            )
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
            uncertainty_warnings=_unique(warnings),
            missing_data_summary=missing_summary,
            immediate_ranking=immediate_ranking,
            long_term_ranking=long_term_ranking,
            rankings_conflict=rankings_conflict,
            temporal_missing_data=temporal_missing,
            individual_reports=reports,
        )

        if audit:
            self._attach_audit(comparison_set, result)

        result.comparison_explanation = build_comparison_explanation(result)
        return result

    def _attach_audit(
        self, comparison_set: ActionComparisonSet, result: ActionComparisonResult
    ) -> None:
        """Run the adversarial audit over the comparison and fold its findings in.

        If the best option wins mostly because data about its competitors are
        missing, the ranking is marked unstable (the audit is opt-in, so default
        comparisons are unchanged).
        """
        from littleboy.audit.stress import AdversarialStressTester

        tester = AdversarialStressTester(self.policy_mode or comparison_set.policy_mode)
        audit_report = tester.audit_comparison(comparison_set, result)
        result.audit = audit_report
        if audit_report.ranking_unstable_due_to_missing_data:
            result.data_sensitive = True
            result.ranking_stable = False
            result.uncertainty_warnings = _unique(
                [*result.uncertainty_warnings, *audit_report.warnings]
            )
        elif audit_report.warnings:
            result.uncertainty_warnings = _unique(
                [*result.uncertainty_warnings, *(f"[audit] {w}" for w in audit_report.warnings)]
            )

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
