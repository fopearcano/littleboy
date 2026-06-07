"""LittleBoy's comparison engine (v0.6).

LittleBoy should not only judge one action in isolation; it should compare
several candidate actions and identify the **least coercive morally viable path
under the available evidence**, while exposing uncertainty, missing data,
trade-offs, and contradictions. It builds on the existing ``EthicalEvaluator``
and preserves every individual report.
"""

from __future__ import annotations

from littleboy.comparison.dominance import compare_dominance, dominance_matrix
from littleboy.comparison.engine import ComparisonEngine, compare
from littleboy.comparison.models import (
    ActionComparisonResult,
    ActionComparisonSet,
    ActionOption,
    ActionRankingEntry,
    DominanceResult,
    TradeoffAnalysis,
)
from littleboy.comparison.ranking import rank_options, ranking_key
from littleboy.comparison.report import (
    build_comparison_explanation,
    render_comparison_json,
    render_comparison_text,
)
from littleboy.comparison.tradeoffs import analyze_tradeoffs

__all__ = [
    "ActionComparisonResult",
    "ActionComparisonSet",
    "ActionOption",
    "ActionRankingEntry",
    "ComparisonEngine",
    "DominanceResult",
    "TradeoffAnalysis",
    "analyze_tradeoffs",
    "build_comparison_explanation",
    "compare",
    "compare_dominance",
    "dominance_matrix",
    "rank_options",
    "ranking_key",
    "render_comparison_json",
    "render_comparison_text",
]
