"""The :class:`CaseBuilder`: the public entry point for constructing cases.

A builder inspects a partial :class:`~littleboy.core.models.ActionCase`, tells you
what is missing and why it matters, estimates whether the case is ready for
evaluation, and can apply simple answers back onto the case.

It never invents facts. ``apply_answer`` only fills fields the user has actually
answered, and only for the simple, unambiguous fields; complex structures
(coercion profile, evidence, alternatives, justification) are left to be supplied
directly, which keeps the builder honest and auditable.
"""

from __future__ import annotations

from littleboy.audit.models import AuditReport
from littleboy.audit.stress import AdversarialStressTester
from littleboy.case_builder.completeness import completeness_report
from littleboy.case_builder.questions import generate_questions
from littleboy.case_builder.templates import ScenarioTemplate, get_template
from littleboy.core.enums import AgentType, ConsentStatus
from littleboy.core.models import ActionCase, CaseCompletenessReport, MoralAgent, QuestionSet
from littleboy.rules.policy import PolicyMode, PolicyProfile, get_policy

# Which base questions can be applied automatically, and onto which field.
_QID_TO_FIELD: dict[str, str] = {
    "Q-DESCRIPTION": "description",
    "Q-AGENT-TYPE": "acting_agent",
    "Q-CONSENT": "consent",
    "Q-COERCION-SOURCE": "responds_to_existing_coercion",
    "Q-CONSEQUENCES": "expected_consequences",
}

_TEXT_FIELDS = {
    "description",
    "expected_consequences",
    "intended_goal",
    "prior_coercion_description",
    "context_notes",
    "title",
}
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


def _resolve_template(template: ScenarioTemplate | str | None) -> ScenarioTemplate | None:
    if template is None or isinstance(template, ScenarioTemplate):
        return template
    resolved = get_template(template)
    if resolved is None:
        raise ValueError(f"unknown template: {template}")
    return resolved


class CaseBuilder:
    """Builds and inspects (partial) action cases under a chosen policy."""

    def __init__(self, policy_mode: PolicyMode | PolicyProfile | str | None = None) -> None:
        self.policy: PolicyProfile = get_policy(policy_mode)

    def generate_questions(
        self, case: ActionCase, template: ScenarioTemplate | str | None = None
    ) -> QuestionSet:
        """Return the questions needed to make ``case`` evaluable."""
        return generate_questions(case, policy=self.policy, template=_resolve_template(template))

    def completeness_report(
        self, case: ActionCase, template: ScenarioTemplate | str | None = None
    ) -> CaseCompletenessReport:
        """Return how ready ``case`` is for evaluation."""
        return completeness_report(case, policy=self.policy, template=_resolve_template(template))

    def audit(self, case: ActionCase) -> AuditReport:
        """Adversarially audit how the (possibly partial) case is described.

        Lets a case being built be checked for leading language, missing
        counterevidence, false consent, fake alternatives, and ideological
        framing before it is ever evaluated -- the audit's stress-test questions
        complement the builder's completeness questions.
        """
        return AdversarialStressTester(self.policy).audit_case(case)

    def apply_answer(self, case: ActionCase, question_id: str, answer: object) -> ActionCase:
        """Return a copy of ``case`` with one simple answer applied.

        Only the simple, unambiguous fields are supported (description, acting
        agent type, consent, coercion source, expected consequences). Complex
        structures must be supplied directly; attempting to apply them raises
        ``ValueError`` rather than guessing.
        """
        field = _QID_TO_FIELD.get(question_id)
        if field is None:
            raise ValueError(
                f"answer for '{question_id}' cannot be applied automatically; "
                "supply this field directly in the case JSON"
            )
        return self._apply_field(case, field, answer)

    # -- internals ------------------------------------------------------------

    def _apply_field(self, case: ActionCase, field: str, answer: object) -> ActionCase:
        if field in _TEXT_FIELDS:
            return case.model_copy(update={field: str(answer)})
        if field == "consent":
            return case.model_copy(update={"consent": ConsentStatus(str(answer))})
        if field == "responds_to_existing_coercion":
            return case.model_copy(update={"responds_to_existing_coercion": _parse_bool(answer)})
        if field == "acting_agent":
            return case.model_copy(update={"acting_agent": self._build_agent(case, answer)})
        raise ValueError(f"field '{field}' is not auto-applicable")  # pragma: no cover

    def _build_agent(self, case: ActionCase, answer: object) -> MoralAgent:
        agent_type = AgentType(str(answer))
        name = case.acting_agent.name if case.acting_agent else "acting agent"
        description = case.acting_agent.description if case.acting_agent else ""
        return MoralAgent(name=name, agent_type=agent_type, description=description)


def _parse_bool(answer: object) -> bool:
    if isinstance(answer, bool):
        return answer
    text = str(answer).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"expected a yes/no answer, got: {answer!r}")
