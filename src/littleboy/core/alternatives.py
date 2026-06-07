"""Comparison of a proposed action against its alternatives (Axiom 2).

Axiom 2 directs us toward the *least coercive* feasible course of action. This
module compares the proposed action's coercion score against each supplied
alternative and reports which feasible alternatives are meaningfully less
coercive. A less coercive option that is not feasible is recorded but does not,
on its own, defeat the proposed action -- a fantasy-level alternative is not a
real alternative.
"""

from __future__ import annotations

from littleboy.core.models import AlternativeAction, AlternativeAnalysis
from littleboy.core.scoring import score_coercion

# An alternative must be at least this much less coercive to "count" as better.
_MEANINGFUL_MARGIN = 0.05

# Default feasibility below which an alternative is treated as impractical.
DEFAULT_FEASIBILITY_FLOOR = 0.30


def effective_coercion_score(alternative: AlternativeAction) -> float | None:
    """Return an alternative's 0..1 coercion score, or None if unquantified.

    A full ``coercion_profile`` is preferred; otherwise a direct
    ``estimated_coercion_score`` is used; otherwise the coercion is unknown.
    """
    if alternative.coercion_profile is not None:
        return score_coercion(alternative.coercion_profile).score
    return alternative.estimated_coercion_score


def analyse_alternatives(
    alternatives: list[AlternativeAction] | None,
    proposed_coercion_score: float,
    *,
    feasibility_floor: float = DEFAULT_FEASIBILITY_FLOOR,
) -> AlternativeAnalysis:
    """Compare the proposed action against its alternatives.

    ``alternatives is None`` means the alternatives were never analysed (an
    unknown), which is materially different from an empty list (analysed, none
    found).
    """
    if alternatives is None:
        return AlternativeAnalysis(
            evaluated=False,
            count=0,
            proposed_coercion_score=proposed_coercion_score,
            reasoning=["alternatives were not analysed; existence of a better option is unknown"],
        )

    feasible_less_coercive: list[str] = []
    infeasible_less_coercive: list[str] = []
    unquantified: list[str] = []
    feasible_scores: list[float] = []
    reasoning: list[str] = [
        f"comparing {len(alternatives)} alternative(s) against proposed coercion "
        f"{proposed_coercion_score:.2f} (feasibility floor {feasibility_floor:.2f})"
    ]

    for alt in alternatives:
        score = effective_coercion_score(alt)
        if score is None:
            unquantified.append(alt.label)
            reasoning.append(f"'{alt.label}': coercion not quantified; cannot compare")
            continue

        feasible = alt.feasibility >= feasibility_floor
        if feasible:
            feasible_scores.append(score)
        is_less_coercive = score < proposed_coercion_score - _MEANINGFUL_MARGIN

        if is_less_coercive and feasible:
            feasible_less_coercive.append(
                f"{alt.label} (coercion ~{score:.2f}, feasibility {alt.feasibility:.2f})"
            )
            reasoning.append(f"'{alt.label}': feasible and less coercive ({score:.2f})")
        elif is_less_coercive and not feasible:
            infeasible_less_coercive.append(
                f"{alt.label} (coercion ~{score:.2f}, feasibility {alt.feasibility:.2f})"
            )
            reasoning.append(
                f"'{alt.label}': less coercive ({score:.2f}) but not feasible "
                f"({alt.feasibility:.2f}); does not defeat the proposed action"
            )
        else:
            reasoning.append(f"'{alt.label}': not less coercive ({score:.2f})")

    best = min(feasible_scores) if feasible_scores else None

    return AlternativeAnalysis(
        evaluated=True,
        count=len(alternatives),
        proposed_coercion_score=proposed_coercion_score,
        feasible_less_coercive=feasible_less_coercive,
        infeasible_less_coercive=infeasible_less_coercive,
        unquantified=unquantified,
        best_feasible_alternative_score=best,
        reasoning=reasoning,
    )
