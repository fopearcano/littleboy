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
from littleboy.deliberation.voi import minimal_flip_sets, value_of_information

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.core.evaluator import EthicalEvaluator
    from littleboy.core.models import ActionCase

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
    case: ActionCase, evaluator: EthicalEvaluator, *, max_size: int = 3
) -> MinimalQuestionPlan:
    """Return the smallest, priority-ordered set of questions that could change the verdict."""
    base = evaluator.evaluate(case)
    ivs = value_of_information(case, evaluator)
    flip_sets, smallest = minimal_flip_sets(case, evaluator, max_size=max_size)
    fields_in_min = {f for fs in flip_sets for f in fs.fields}

    planned: list[PlannedQuestion] = []
    for iv in ivs:
        alone = iv.changes_verdict
        in_min = iv.field in fields_in_min
        if not (alone or in_min):
            continue  # this unknown cannot change the verdict; do not ask it
        planned.append(
            PlannedQuestion(
                field=iv.field,
                question=iv.question,
                why_it_matters=iv.why_it_matters,
                category=_FIELD_CATEGORY.get(iv.field, "context"),
                priority="critical" if alone else "high",
                value=iv.value,
                alone_changes_verdict=alone,
                in_minimal_set=in_min,
                related_axioms=iv.related_axioms,
            )
        )

    planned.sort(key=lambda q: (_PRIORITY_RANK[q.priority], -q.value))

    notes = [
        "only questions whose answers could change the verdict are listed, in priority order",
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

    return MinimalQuestionPlan(
        target="evaluation",
        verdict=base.verdict,
        confidence=base.confidence,
        questions=planned,
        smallest_flip_size=smallest,
        verdict_robust=(smallest is None),
        notes=notes,
    )
