"""Deterministic dominance analysis between options.

Option A *strictly dominates* B when A is better on coercion and no worse on
every other ethically relevant dimension (data quality, evidence, confidence,
verdict, blockers, feasibility), for the same (or morally equivalent) goal.
When A is better on some dimensions but worse on others, that is *partial*
dominance -- a trade-off, which the engine surfaces rather than resolves
silently. Options are *incomparable* when either rests on insufficient data.
"""

from __future__ import annotations

from littleboy.comparison.models import ActionOption, ActionRankingEntry, DominanceResult
from littleboy.core.enums import Verdict

# Lower rank = more permissible / better verdict.
_VERDICT_RANK = {
    Verdict.ACCEPTABLE: 0,
    Verdict.ACCEPTABLE_WITH_RESERVATIONS: 1,
    Verdict.ETHICALLY_SUSPICIOUS: 2,
    Verdict.NOT_ACCEPTABLE: 3,
}

# Dominance relation strings (also used in the report).
STRICT_A = "strict_a_over_b"
STRICT_B = "strict_b_over_a"
PARTIAL = "partial"
NONE = "none"
INCOMPARABLE = "incomparable_insufficient_data"

_TOL = 0.05


def _goal_equivalent(a: ActionOption, b: ActionOption) -> bool:
    """Two options share a goal if their declared goals match, or one is unstated."""
    ga = (a.declared_goal or "").strip().lower()
    gb = (b.declared_goal or "").strip().lower()
    return ga == gb or ga == "" or gb == ""


def _lower_better(av: float, bv: float, tol: float = _TOL) -> str:
    if av < bv - tol:
        return "a"
    if av > bv + tol:
        return "b"
    return "="


def _higher_better(av: float, bv: float, tol: float = _TOL) -> str:
    return _lower_better(bv, av, tol)


def compare_dominance(
    a_entry: ActionRankingEntry,
    b_entry: ActionRankingEntry,
    a_opt: ActionOption,
    b_opt: ActionOption,
) -> DominanceResult:
    """Return the dominance relation of A relative to B."""
    if Verdict.INSUFFICIENT_DATA in (a_entry.verdict, b_entry.verdict):
        return DominanceResult(
            option_a_id=a_entry.option_id,
            option_b_id=b_entry.option_id,
            relation=INCOMPARABLE,
            reasons=["one or both options rest on insufficient data"],
        )

    # Per-dimension comparison: which option is better on each axis.
    dims: dict[str, str] = {
        "coercion": _lower_better(a_entry.coercion_score, b_entry.coercion_score),
        "data_quality": _higher_better(a_entry.data_quality_score, b_entry.data_quality_score),
        "evidence": _higher_better(a_entry.evidence_score, b_entry.evidence_score),
        "confidence": _higher_better(a_entry.confidence, b_entry.confidence),
        "feasibility": _higher_better(a_opt.feasibility, b_opt.feasibility),
    }
    va, vb = _VERDICT_RANK[a_entry.verdict], _VERDICT_RANK[b_entry.verdict]
    dims["verdict"] = "a" if va < vb else "b" if vb < va else "="

    a_blockers, b_blockers = set(a_entry.blockers), set(b_entry.blockers)
    if a_blockers < b_blockers:
        dims["blockers"] = "a"
    elif b_blockers < a_blockers:
        dims["blockers"] = "b"
    elif a_blockers != b_blockers:
        dims["blockers"] = "x"  # each has blockers the other lacks
    else:
        dims["blockers"] = "="

    a_better = {d for d, w in dims.items() if w == "a"}
    b_better = {d for d, w in dims.items() if w == "b"}
    crossed_blockers = dims["blockers"] == "x"
    goal_ok = _goal_equivalent(a_opt, b_opt)

    def _strict(better: set[str], worse: set[str], lead: str) -> bool:
        # Strict dominance: strictly less coercive, no worse anywhere, no extra blockers.
        return goal_ok and "coercion" in better and not worse and not crossed_blockers

    reasons: list[str] = []
    if not goal_ok:
        reasons.append(
            f"different declared goals ('{a_opt.declared_goal}' vs '{b_opt.declared_goal}'); "
            "dominance not asserted"
        )
        return DominanceResult(
            option_a_id=a_entry.option_id,
            option_b_id=b_entry.option_id,
            relation=NONE,
            reasons=reasons,
        )

    if _strict(a_better, b_better, "a"):
        reasons.append("A is strictly less coercive and no worse on any other dimension")
        reasons += [f"A better on: {d}" for d in sorted(a_better)]
        relation = STRICT_A
    elif _strict(b_better, a_better, "b"):
        reasons.append("B is strictly less coercive and no worse on any other dimension")
        reasons += [f"B better on: {d}" for d in sorted(b_better)]
        relation = STRICT_B
    elif a_better and b_better or crossed_blockers:
        relation = PARTIAL
        reasons.append("trade-off: each option is better on some dimensions")
        if a_better:
            reasons.append("A better on: " + ", ".join(sorted(a_better)))
        if b_better:
            reasons.append("B better on: " + ", ".join(sorted(b_better)))
        if crossed_blockers:
            reasons.append("each option carries a blocker the other lacks")
    elif a_better and not b_better:
        relation = PARTIAL
        reasons.append(
            "A is better or equal everywhere (weak advantage): " + ", ".join(sorted(a_better))
        )
    elif b_better and not a_better:
        relation = PARTIAL
        reasons.append(
            "B is better or equal everywhere (weak advantage): " + ", ".join(sorted(b_better))
        )
    else:
        relation = NONE
        reasons.append("the options are effectively equivalent on the compared dimensions")

    return DominanceResult(
        option_a_id=a_entry.option_id,
        option_b_id=b_entry.option_id,
        relation=relation,
        reasons=reasons,
    )


def dominance_matrix(
    entries: list[ActionRankingEntry], options: dict[str, ActionOption]
) -> tuple[list[DominanceResult], list[str], list[str]]:
    """Compute all ordered pairwise dominance relations and the dominated set.

    Returns ``(results, dominated_ids, non_dominated_ids)``. ``dominated_ids`` are
    options strictly dominated by at least one other; the rest form the
    non-dominated frontier.
    """
    results: list[DominanceResult] = []
    dominated: set[str] = set()
    for i, a in enumerate(entries):
        for j, b in enumerate(entries):
            if i >= j:
                continue
            res = compare_dominance(a, b, options[a.option_id], options[b.option_id])
            results.append(res)
            if res.relation == STRICT_A:
                dominated.add(b.option_id)
            elif res.relation == STRICT_B:
                dominated.add(a.option_id)
    non_dominated = [e.option_id for e in entries if e.option_id not in dominated]
    return results, sorted(dominated), non_dominated
