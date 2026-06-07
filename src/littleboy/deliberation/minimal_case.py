"""The minimal-sufficient-case planner.

Given a case, ask *only the questions that could change the verdict*, in priority
order. A question earns a place only if resolving it -- alone, or as part of a
minimal combination of unknowns -- could flip the verdict; questions that can only
nudge confidence are omitted, because answering them cannot settle the case.

This connects the value-of-information search (single- and multi-fact) to the
case builder: it turns "what is missing?" into "what is *worth asking*, and in
what order?".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.deliberation.models import MinimalQuestionPlan, PlannedQuestion
from littleboy.deliberation.voi import (
    DEFAULT_QUESTION_COSTS,
    cheapest_flip_set,
    effective_costs,
    minimal_flip_sets,
    question_cost,
    value_of_information,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.core.evaluator import EthicalEvaluator
    from littleboy.core.models import ActionCase

# Re-exported for backwards compatibility (the canonical definitions live in voi).
__all__ = ["DEFAULT_QUESTION_COSTS", "plan_minimal_questions", "question_cost"]

# Probe field -> case-builder question category (matches QuestionCategory values).
_FIELD_CATEGORY = {
    "acting_agent.agent_type": "acting_agent",
    "consent": "consent",
    "coercion.reversibility": "reversibility",
    "available_alternatives": "alternatives",
    "data_quality": "data_quality",
    "justification": "justification",
    "consequences": "consequences",
}

_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2}


def plan_minimal_questions(
    case: ActionCase,
    evaluator: EthicalEvaluator,
    *,
    max_size: int = 3,
    cost_model: dict[str, float] | None = None,
) -> MinimalQuestionPlan:
    """Return the priority-ordered questions that could change the verdict, cheapest first.

    A question is included only if resolving it -- alone, or in a minimal
    combination -- could flip the verdict. The ``cheapest_set`` is the lowest-total-
    cost sufficient set (which, unlike the smallest set, may favour two cheap
    questions over one expensive one).
    """
    base = evaluator.evaluate(case)
    # Effective costs: built-in defaults < case-supplied hints < caller-supplied map. Used
    # for both the per-question cost and the cheapest-set search, so they stay consistent.
    effective_cost = effective_costs(case, cost_model)

    ivs = value_of_information(case, evaluator)
    flip_sets, smallest = minimal_flip_sets(case, evaluator, max_size=max_size)
    fields_in_min = {f for fs in flip_sets for f in fs.fields}

    cheapest = cheapest_flip_set(case, evaluator, cost=effective_cost, max_size=max_size)
    cheapest_fields = set(cheapest[0].fields) if cheapest is not None else set()
    cheapest_cost = cheapest[1] if cheapest is not None else None

    planned: list[PlannedQuestion] = []
    for iv in ivs:
        alone = iv.changes_verdict
        in_min = iv.field in fields_in_min
        in_cheap = iv.field in cheapest_fields
        if not (alone or in_min or in_cheap):
            continue  # this unknown cannot change the verdict; do not ask it
        planned.append(
            PlannedQuestion(
                field=iv.field,
                question=iv.question,
                why_it_matters=iv.why_it_matters,
                category=_FIELD_CATEGORY.get(iv.field, "context"),
                priority="critical" if alone else "high",
                value=iv.value,
                cost=effective_cost.get(iv.field, 1.0),
                alone_changes_verdict=alone,
                in_minimal_set=in_min,
                in_cheapest_set=in_cheap,
                related_axioms=iv.related_axioms,
            )
        )

    # Pursue the cheapest sufficient set first: cheapest-set members, then by cost, then
    # priority, then informativeness. This makes the interactive loop follow the cheapest
    # path to a settled verdict rather than always asking a single (possibly costly) flipper.
    planned.sort(
        key=lambda q: (0 if q.in_cheapest_set else 1, q.cost, _PRIORITY_RANK[q.priority], -q.value)
    )

    notes = [
        "only questions whose answers could change the verdict are listed, cheapest-useful first",
    ]
    if smallest is None:
        notes.append(
            "the verdict is robust to every resolvable combination searched; no question would "
            "change it (some may still raise confidence)"
        )
    elif smallest >= 2:
        notes.append(
            f"no single answer changes the verdict; the smallest sufficient set has {smallest} "
            "questions, which must be answered together"
        )
    if cheapest_fields and cheapest_cost is not None:
        notes.append(
            f"cheapest sufficient set: {{{', '.join(sorted(cheapest_fields))}}} "
            f"(total cost {cheapest_cost:g})"
        )

    return MinimalQuestionPlan(
        target="evaluation",
        verdict=base.verdict,
        confidence=base.confidence,
        questions=planned,
        smallest_flip_size=smallest,
        cheapest_set=sorted(cheapest_fields),
        cheapest_set_cost=cheapest_cost,
        verdict_robust=(smallest is None),
        notes=notes,
    )
