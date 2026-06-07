"""Interactive minimal intake: ask the cheapest verdict-relevant question, repeat.

This is the I/O-free engine behind ``littleboy build-case --minimal``. Given a
case and a callback that supplies an answer for a question, it:

1. plans the minimal, cheapest-first questions that could change the verdict;
2. asks the top one and applies the answer;
3. re-plans on the *updated* case and repeats,

until the verdict is **settled** (no remaining unknown could change it) or a
question budget is reached. Keeping the loop I/O-free makes it deterministic and
testable; the CLI supplies a prompting callback, tests supply a scripted one.
"""

from __future__ import annotations

from collections.abc import Callable

from littleboy.core.enums import AgentType, ConsentStatus, EpistemicStatus
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase, DataQualityProfile
from littleboy.deliberation import voi
from littleboy.deliberation.minimal_case import plan_minimal_questions
from littleboy.deliberation.models import (
    IntakeStep,
    IntakeTranscript,
    PlannedQuestion,
)
from littleboy.rules.policy import PolicyMode, PolicyProfile

AnswerFn = Callable[[PlannedQuestion], str | None]

_POOR_DATA = DataQualityProfile(
    completeness=0.2,
    source_reliability=0.2,
    specificity=0.2,
    recency=0.3,
    corroboration=0.1,
    ambiguity=0.8,
)

_CONSENT_WORDS = {
    "given": ConsentStatus.GIVEN,
    "yes": ConsentStatus.GIVEN,
    "refused": ConsentStatus.REFUSED,
    "no": ConsentStatus.REFUSED,
    "coerced": ConsentStatus.COERCED,
    "disputed": ConsentStatus.DISPUTED,
    "not_applicable": ConsentStatus.NOT_APPLICABLE,
    "na": ConsentStatus.NOT_APPLICABLE,
    "unknown": ConsentStatus.UNKNOWN,
}
_TYPE_II_WORDS = {"type_ii", "typeii", "type 2", "type ii", "ii", "2", "type2"}
_TYPE_I_WORDS = {"type_i", "typei", "type 1", "type i", "i", "1", "type1"}
_YES_WORDS = {"yes", "y", "true", "exists", "available"}
_NO_WORDS = {"no", "n", "false", "none"}


def apply_intake_answer(case: ActionCase, field: str, answer: str) -> ActionCase:
    """Apply a free-text answer for one probe field, returning an updated case.

    Unparseable or empty answers leave the case unchanged (so the loop will not
    pretend an unknown was resolved).
    """
    a = answer.strip().lower()
    if not a:
        return case

    if field == "consent":
        status = _CONSENT_WORDS.get(a)
        return voi._set_consent(case, status) if status is not None else case

    if field == "acting_agent.agent_type":
        if a in _TYPE_II_WORDS:
            return voi._set_agent_type(case, AgentType.TYPE_II)
        if a in _TYPE_I_WORDS:
            return voi._set_agent_type(case, AgentType.TYPE_I)
        return case

    if field == "coercion.reversibility":
        try:
            value = max(0.0, min(1.0, float(a)))
        except ValueError:
            return case
        return voi._set_reversibility(case, value)

    if field == "available_alternatives":
        if a in _YES_WORDS:
            return voi._set_alternatives(case, [voi._FEASIBLE_ALT])
        if a in _NO_WORDS:
            return voi._set_alternatives(case, [])
        return case

    if field == "data_quality":
        if a in {"good", "high", "strong"}:
            return voi._set_data_quality(case, voi._GOOD_DATA)
        if a in {"poor", "low", "weak", "bad"}:
            return voi._set_data_quality(case, _POOR_DATA)
        return case

    if field == "justification":
        if case.justification is None:
            return case
        if a in {"established", "yes", "justified", "confirmed"}:
            updates = {c: EpistemicStatus.CONFIRMED for c in voi._JUSTIFICATION_CONDITIONS}
            if (
                case.justification.expected_total_coercion_reduction is None
                or case.justification.expected_total_coercion_reduction <= 0
            ):
                updates["expected_total_coercion_reduction"] = 0.6
            return voi._set_justification(case, **updates)
        if a in {"failed", "no", "refuted", "unjustified"}:
            return voi._set_justification(
                case,
                necessity=EpistemicStatus.DISPUTED,
                no_less_coercive_alternative_available=EpistemicStatus.DISPUTED,
                expected_total_coercion_reduction=-0.2,
            )
        return case

    if field == "consequences":
        if a in {"worse", "worsen", "bad", "rising"}:
            return voi._set_consequences(case, voi._WORSE_FUTURE)
        if a in {"benign", "better", "good", "none", "neutral"}:
            return voi._set_consequences(case, voi._BENIGN_FUTURE)
        return case

    return case


def run_minimal_intake(
    case: ActionCase,
    answer_fn: AnswerFn,
    *,
    policy: PolicyMode | PolicyProfile | str | None = None,
    cost_model: dict[str, float] | None = None,
    max_steps: int = 10,
    max_size: int = 3,
) -> tuple[IntakeTranscript, ActionCase]:
    """Drive the minimal-intake loop, returning the transcript and the final case.

    ``answer_fn`` is called with the next :class:`PlannedQuestion`; returning
    ``None`` stops the loop early. A field is asked at most once (so an unparseable
    answer cannot loop forever).
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
        question = plan.questions[0]
        if question.field in asked_fields:
            break  # no further progress is possible on this unknown
        answer = answer_fn(question)
        if answer is None:
            break
        asked_fields.add(question.field)
        new_case = apply_intake_answer(case, question.field, answer)
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
    return transcript, case
