"""Interactive minimal intake: ask the cheapest verdict-relevant question, repeat.

This is the I/O-free engine behind ``littleboy build-case --minimal``. Given a
case and a callback that supplies an answer for a question, it:

1. plans the minimal, cheapest-first questions that could change the verdict;
2. asks the top one (greedy cheapest, or expected-cost lookahead) and applies it;
3. re-plans on the *updated* case and repeats,

until the verdict is **settled** (no remaining unknown could change it) or a
question budget is reached. Keeping the loop I/O-free makes it deterministic and
testable; the CLI supplies a prompting callback, tests supply a scripted one.

Answer parsing and per-field application live in :mod:`littleboy.deliberation.voi`
(``apply_field_answer``), so case-supplied resolutions and interactive answers use
exactly the same logic; ``apply_intake_answer`` is kept here as an alias.
"""

from __future__ import annotations

from collections.abc import Callable

from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase
from littleboy.deliberation.minimal_case import plan_minimal_questions
from littleboy.deliberation.models import IntakeStep, IntakeTranscript, PlannedQuestion
from littleboy.deliberation.voi import (
    apply_field_answer,
    effective_costs,
    expected_cost_first_question,
)
from littleboy.rules.policy import PolicyMode, PolicyProfile

AnswerFn = Callable[[PlannedQuestion], str | None]

# The canonical parser lives in voi; keep the historical name as an alias.
apply_intake_answer = apply_field_answer


def _next_question(
    case: ActionCase,
    evaluator: EthicalEvaluator,
    plan,
    *,
    strategy: str,
    cost_model: dict[str, float] | None,
    max_size: int,
) -> PlannedQuestion | None:
    """Choose the next question: greedy cheapest-first, or expected-cost lookahead."""
    if not plan.questions:
        return None
    if strategy != "lookahead":
        return plan.questions[0]
    look = expected_cost_first_question(
        case,
        evaluator,
        cost=effective_costs(case, cost_model),
        max_size=min(max_size, 2),
    )
    if look is None:
        return None
    field = look[0]
    return next((q for q in plan.questions if q.field == field), plan.questions[0])


def run_minimal_intake(
    case: ActionCase,
    answer_fn: AnswerFn,
    *,
    policy: PolicyMode | PolicyProfile | str | None = None,
    cost_model: dict[str, float] | None = None,
    strategy: str = "greedy",
    max_steps: int = 10,
    max_size: int = 3,
) -> tuple[IntakeTranscript, ActionCase]:
    """Drive the minimal-intake loop, returning the transcript and the final case.

    ``answer_fn`` is called with the next :class:`PlannedQuestion`; returning
    ``None`` stops the loop early. ``strategy`` is ``"greedy"`` (ask the cheapest
    verdict-relevant question) or ``"lookahead"`` (minimise expected total cost over
    uncertain answers). A field is asked at most once, so an unparseable answer
    cannot loop forever.
    """
    evaluator = EthicalEvaluator(policy, include_completeness=False)
    initial_verdict = evaluator.evaluate(case).verdict
    transcript = IntakeTranscript(initial_verdict=initial_verdict)
    asked_fields: set[str] = set()
    settled = False

    while transcript.questions_asked < max_steps:
        plan = plan_minimal_questions(case, evaluator, max_size=max_size, cost_model=cost_model)
        if not plan.questions:
            settled = True
            break
        question = _next_question(
            case, evaluator, plan, strategy=strategy, cost_model=cost_model, max_size=max_size
        )
        if question is None or question.field in asked_fields:
            break  # no further progress is possible on this unknown
        answer = answer_fn(question)
        if answer is None:
            break
        asked_fields.add(question.field)
        new_case = apply_field_answer(case, question.field, answer)
        report = evaluator.evaluate(new_case)
        prev = transcript.steps[-1].verdict_after if transcript.steps else initial_verdict
        transcript.steps.append(
            IntakeStep(
                field=question.field,
                question=question.question,
                answer=answer,
                verdict_after=report.verdict,
                confidence_after=round(report.confidence, 4),
                verdict_changed=report.verdict != prev,
            )
        )
        case = new_case
        transcript.questions_asked += 1

    final = evaluator.evaluate(case)
    transcript.final_verdict = final.verdict
    transcript.final_confidence = round(final.confidence, 4)
    transcript.settled = settled
    if settled:
        transcript.notes.append(
            "stopped: the verdict is settled -- no remaining unknown could change it"
        )
    elif transcript.questions_asked >= max_steps:
        transcript.notes.append("stopped: reached the question budget")
    else:
        transcript.notes.append("stopped: no further answerable, verdict-relevant question")
    transcript.notes.append(f"strategy: {strategy}")
    return transcript, case
