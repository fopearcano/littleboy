"""Trade-off analysis: making unresolved tensions explicit rather than hiding them.

When one option is less coercive but rests on weaker evidence, or reversible but
less effective, or carries present consent on manipulative language, there is no
clean winner. The comparison engine surfaces these as :class:`TradeoffAnalysis`
items so the reader sees the tension instead of a false certainty.
"""

from __future__ import annotations

from littleboy.comparison.dominance import PARTIAL
from littleboy.comparison.models import (
    ActionOption,
    ActionRankingEntry,
    DominanceResult,
    TradeoffAnalysis,
)

_TOL = 0.05


def _pair_contrasts(
    a: ActionRankingEntry, b: ActionRankingEntry, a_opt: ActionOption, b_opt: ActionOption
) -> list[str]:
    """Concrete phrases describing how A and B trade off."""
    out: list[str] = []
    if a.coercion_score < b.coercion_score - _TOL:
        if (
            a.evidence_score < b.evidence_score - _TOL
            or a.data_quality_score < b.data_quality_score - _TOL
        ):
            out.append(f"'{a.title}' is less coercive but rests on weaker data/evidence")
        if a.confidence < b.confidence - _TOL:
            out.append(f"'{a.title}' is less coercive but the judgment is less certain")
    if b.coercion_score < a.coercion_score - _TOL:
        if (
            b.evidence_score < a.evidence_score - _TOL
            or b.data_quality_score < a.data_quality_score - _TOL
        ):
            out.append(f"'{b.title}' is less coercive but rests on weaker data/evidence")
    ai, bi = (a.irreversibility or 0.0), (b.irreversibility or 0.0)
    if ai < bi - _TOL:
        out.append(f"'{a.title}' is more reversible than '{b.title}'")
    elif bi < ai - _TOL:
        out.append(f"'{b.title}' is more reversible than '{a.title}'")
    if a_opt.feasibility < b_opt.feasibility - _TOL:
        out.append(f"'{a.title}' is less feasible than '{b.title}'")
    elif b_opt.feasibility < a_opt.feasibility - _TOL:
        out.append(f"'{b.title}' is less feasible than '{a.title}'")
    av, bv = (a.vulnerability_risk or 0.0), (b.vulnerability_risk or 0.0)
    if abs(av - bv) > 0.2:
        worse = a.title if av > bv else b.title
        out.append(f"the affected agents are more vulnerable in '{worse}'")
    return out


def analyze_tradeoffs(
    entries: list[ActionRankingEntry],
    dominance_results: list[DominanceResult],
    options: dict[str, ActionOption],
) -> list[TradeoffAnalysis]:
    """Derive explicit trade-offs from partial-dominance pairs and intrinsic tensions."""
    by_id = {e.option_id: e for e in entries}
    tradeoffs: list[TradeoffAnalysis] = []

    for dr in dominance_results:
        if dr.relation != PARTIAL:
            continue
        a, b = by_id[dr.option_a_id], by_id[dr.option_b_id]
        contrasts = _pair_contrasts(a, b, options[a.option_id], options[b.option_id])
        if not contrasts:
            contrasts = ["each option is better on some dimension and worse on another"]
        tradeoffs.append(
            TradeoffAnalysis(
                option_a_id=a.option_id,
                option_b_id=b.option_id,
                dimension="partial dominance",
                description=f"'{a.title}' vs '{b.title}': " + "; ".join(contrasts) + ".",
            )
        )

    # Intrinsic, single-option tensions.
    for e in entries:
        status = (e.consent_status or "").upper()
        if status == "GIVEN" and e.linguistic_coercion_score >= 0.3:
            tradeoffs.append(
                TradeoffAnalysis(
                    option_a_id=e.option_id,
                    option_b_id=e.option_id,
                    dimension="consent vs language",
                    description=f"'{e.title}': consent is present but the language appears "
                    "manipulative, so the quality of that consent is in doubt.",
                )
            )
        if (e.irreversibility or 0.0) >= 0.5 and e.confidence < 0.6:
            tradeoffs.append(
                TradeoffAnalysis(
                    option_a_id=e.option_id,
                    option_b_id=e.option_id,
                    dimension="irreversibility vs certainty",
                    description=f"'{e.title}': the action is largely irreversible yet the "
                    "judgment is uncertain.",
                )
            )

    return tradeoffs
