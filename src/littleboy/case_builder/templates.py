"""Scenario templates for the LittleBoy case builder.

A :class:`ScenarioTemplate` captures the *shape* of a common kind of ethical
case: which fields usually matter, which coercion dimensions are typical, what
evidence is usually needed, and which extra questions are worth asking. Templates
raise the priority of the categories they emphasise and add their own questions.

These are **ethical** templates only. They make no legal, medical, clinical, or
regulatory claims; the ``medical_decision`` template, for instance, asks about
consent and alternatives as *ethical* matters, not about standards of care.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import QuestionCategory, QuestionPriority
from littleboy.core.models import Question


class ScenarioTemplate(BaseModel):
    """A reusable description of a common ethical case type."""

    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str
    required_fields: list[str] = Field(default_factory=list)
    typical_coercion_dimensions: list[str] = Field(default_factory=list)
    emphasized_categories: list[QuestionCategory] = Field(default_factory=list)
    typical_evidence_needs: list[str] = Field(default_factory=list)
    typical_alternatives: list[str] = Field(default_factory=list)
    special_warnings: list[str] = Field(default_factory=list)
    extra_questions: list[Question] = Field(default_factory=list)


def _q(
    name: str,
    n: int,
    text: str,
    category: QuestionCategory,
    priority: QuestionPriority,
    why: str,
    answer_type: str,
    axioms: list[str],
    *,
    field_target: str | None = None,
) -> Question:
    return Question(
        question_id=f"Q-TPL-{name.upper()}-{n}",
        text=text,
        category=category,
        priority=priority,
        why_it_matters=why,
        expected_answer_type=answer_type,
        related_axioms=axioms,
        field_target=field_target,
    )


_TEMPLATES: dict[str, ScenarioTemplate] = {}


def _register(template: ScenarioTemplate) -> ScenarioTemplate:
    _TEMPLATES[template.name] = template
    return template


_register(
    ScenarioTemplate(
        name="generic_action",
        summary="A general action with no special structure; uses the base questions.",
        required_fields=["acting_agent", "affected_agents", "coercion_profile"],
        typical_coercion_dimensions=["social_pressure"],
        emphasized_categories=[],
        typical_evidence_needs=["a description of what happened and who said so"],
        typical_alternatives=["doing nothing", "a less forceful version of the action"],
        special_warnings=[],
    )
)

_register(
    ScenarioTemplate(
        name="medical_decision",
        summary="A care decision affecting a patient. Ethical framing only -- no clinical claims.",
        required_fields=["affected_agents", "consent_profile", "available_alternatives"],
        typical_coercion_dimensions=["physical_force", "psychological_pressure"],
        emphasized_categories=[
            QuestionCategory.CONSENT,
            QuestionCategory.ALTERNATIVES,
            QuestionCategory.VULNERABILITY,
            QuestionCategory.REVERSIBILITY,
        ],
        typical_evidence_needs=["who decided", "what the patient was told", "capacity to decide"],
        typical_alternatives=[
            "a less invasive option",
            "watchful waiting",
            "deferring the decision",
        ],
        special_warnings=[
            "LittleBoy gives an ethical reading only; it is not medical advice or a "
            "standard-of-care judgment."
        ],
        extra_questions=[
            _q(
                "medical_decision",
                1,
                "Was the affected person's consent informed (did they understand the "
                "options and effects) and voluntary?",
                QuestionCategory.CONSENT,
                QuestionPriority.CRITICAL,
                "Valid consent must be informed and voluntary; without it an intervention "
                "is coercive (Axioms 0, 2).",
                "consent_status",
                ["A0", "A2"],
                field_target="consent_profile",
            ),
            _q(
                "medical_decision",
                2,
                "What less-coercive or less-invasive alternatives were available, and how "
                "feasible was each?",
                QuestionCategory.ALTERNATIVES,
                QuestionPriority.HIGH,
                "If a feasible less-coercive option existed, the intervention is not the "
                "least-coercive course (Axiom 2).",
                "alternatives",
                ["A2"],
                field_target="available_alternatives",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="legal_or_institutional_constraint",
        summary="An institution applies a rule or sanction. Ethical framing only.",
        required_fields=["acting_agent", "affected_agents", "coercion_profile", "justification"],
        typical_coercion_dimensions=["legal_constraint", "threat", "economic_pressure"],
        emphasized_categories=[
            QuestionCategory.JUSTIFICATION,
            QuestionCategory.ALTERNATIVES,
            QuestionCategory.CONSEQUENCES,
        ],
        typical_evidence_needs=["the rule being applied", "the conduct it responds to"],
        typical_alternatives=["a warning", "a lesser sanction", "a non-coercive remedy"],
        special_warnings=["LittleBoy assesses coercion ethically; it does not determine legality."],
        extra_questions=[
            _q(
                "legal_or_institutional_constraint",
                1,
                "Does the constraint respond to a specific prior or imminent coercion, and "
                "does it stop once that is neutralised?",
                QuestionCategory.JUSTIFICATION,
                QuestionPriority.HIGH,
                "Coercion is justifiable only as a bounded response to coercion, with a "
                "defined stop condition (Axiom 3).",
                "justification",
                ["A3"],
                field_target="justification",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="emergency_intervention",
        summary="A time-critical intervention to stop ongoing or imminent harm.",
        required_fields=["coercion_profile", "justification", "available_alternatives"],
        typical_coercion_dimensions=["physical_force", "threat"],
        emphasized_categories=[
            QuestionCategory.JUSTIFICATION,
            QuestionCategory.ALTERNATIVES,
            QuestionCategory.REVERSIBILITY,
        ],
        typical_evidence_needs=["the imminent harm being prevented", "proportionality of force"],
        typical_alternatives=["de-escalation", "calling for help", "minimal restraint"],
        special_warnings=[
            "Emergencies do not suspend the Axiom 3 conditions; they make a defined stop "
            "condition more important, not less."
        ],
        extra_questions=[
            _q(
                "emergency_intervention",
                1,
                "What is the existing or imminent coercion this intervention responds to, and "
                "when will the intervention stop?",
                QuestionCategory.JUSTIFICATION,
                QuestionPriority.CRITICAL,
                "A defensive intervention is justifiable only against actual/imminent coercion "
                "and must cease once the threat ends (Axiom 3).",
                "justification",
                ["A3"],
                field_target="justification",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="speech_or_language_manipulation",
        summary="An action that works through misleading, deceptive, or manipulative language.",
        required_fields=["coercion_profile", "affected_agents"],
        typical_coercion_dimensions=["informational_manipulation", "psychological_pressure"],
        emphasized_categories=[
            QuestionCategory.COERCION,
            QuestionCategory.CONSENT,
            QuestionCategory.EVIDENCE,
        ],
        typical_evidence_needs=["the exact wording", "what was concealed or distorted"],
        typical_alternatives=["clear, neutral wording", "full disclosure", "an explicit opt-in"],
        special_warnings=[
            "Informational manipulation is coercion, not merely 'bad communication'."
        ],
        extra_questions=[
            _q(
                "speech_or_language_manipulation",
                1,
                "Does the action use misleading, deceptive, or manipulative information to "
                "steer the affected agents' choices? To what degree (0-1)?",
                QuestionCategory.COERCION,
                QuestionPriority.CRITICAL,
                "Informational manipulation is a coercion channel: deceiving someone into a "
                "choice overrides their will (Axioms 0, 2).",
                "score_0_1",
                ["A0", "A2"],
                field_target="coercion_profile.informational_manipulation",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="economic_pressure",
        summary="An action that works through financial leverage, dependency, or scarcity.",
        required_fields=["coercion_profile", "affected_agents", "available_alternatives"],
        typical_coercion_dimensions=["economic_pressure", "threat"],
        emphasized_categories=[
            QuestionCategory.COERCION,
            QuestionCategory.ALTERNATIVES,
            QuestionCategory.VULNERABILITY,
        ],
        typical_evidence_needs=["the dependency or leverage involved", "available exits"],
        typical_alternatives=["a fair offer", "time to decide", "an independent option"],
        special_warnings=[
            "Economic pressure is coercive in proportion to the affected agents' lack of "
            "feasible alternatives."
        ],
        extra_questions=[
            _q(
                "economic_pressure",
                1,
                "Do the affected agents have a feasible alternative to complying, or are they "
                "dependent on the acting agent?",
                QuestionCategory.VULNERABILITY,
                QuestionPriority.HIGH,
                "Pressure on someone with no feasible exit is far more coercive (Axioms 0, 2).",
                "agency_profile",
                ["A0", "A2"],
                field_target="agency_profile",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="caregiving_or_dependency",
        summary="An action by a caregiver toward a dependent person.",
        required_fields=["affected_agents", "consent_profile", "agency_profile"],
        typical_coercion_dimensions=["psychological_pressure", "physical_force"],
        emphasized_categories=[
            QuestionCategory.VULNERABILITY,
            QuestionCategory.CONSENT,
            QuestionCategory.ALTERNATIVES,
        ],
        typical_evidence_needs=["the dependant's capacity", "who speaks for them"],
        typical_alternatives=["assistance instead of substitution", "supported decision-making"],
        special_warnings=[
            "Dependency raises vulnerability; consent and capacity must be examined closely."
        ],
        extra_questions=[
            _q(
                "caregiving_or_dependency",
                1,
                "What is the dependant's decision-making capacity, and was their own will "
                "sought and respected where possible?",
                QuestionCategory.VULNERABILITY,
                QuestionPriority.CRITICAL,
                "Substituting one's will for a dependant's is coercive unless their capacity "
                "is genuinely lacking and their interests are served (Axioms 0, 2).",
                "agency_profile",
                ["A0", "A2"],
                field_target="agency_profile",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="self_regarding_action",
        summary="An action whose effects fall mainly on the acting agent themselves.",
        required_fields=["acting_agent", "affected_agents"],
        typical_coercion_dimensions=[],
        emphasized_categories=[
            QuestionCategory.AFFECTED_AGENT,
            QuestionCategory.CONSENT,
        ],
        typical_evidence_needs=["whether anyone else is materially affected"],
        typical_alternatives=["no action needed if no one else is coerced"],
        special_warnings=[
            "If the action coerces no one else, the coercion concern is minimal; confirm that "
            "no third party is affected."
        ],
        extra_questions=[
            _q(
                "self_regarding_action",
                1,
                "Does this action coerce anyone other than the acting agent? If so, who?",
                QuestionCategory.AFFECTED_AGENT,
                QuestionPriority.HIGH,
                "A purely self-regarding action involves little coercion; the question is "
                "whether third parties are affected (Axioms 0, 2).",
                "list_of_agents",
                ["A0", "A2"],
                field_target="affected_agents",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="collective_policy",
        summary="A rule or policy applied to many agents at once.",
        required_fields=["affected_agents", "coercion_profile", "available_alternatives"],
        typical_coercion_dimensions=["legal_constraint", "economic_pressure", "social_pressure"],
        emphasized_categories=[
            QuestionCategory.AFFECTED_AGENT,
            QuestionCategory.ALTERNATIVES,
            QuestionCategory.CONSEQUENCES,
        ],
        typical_evidence_needs=["who is in scope", "opt-out availability"],
        typical_alternatives=["an opt-in policy", "a narrower scope", "a voluntary scheme"],
        special_warnings=[
            "Scale matters: coercion applied to many agents aggregates; record how many are "
            "affected."
        ],
        extra_questions=[
            _q(
                "collective_policy",
                1,
                "How many agents does the policy affect, and can they opt out?",
                QuestionCategory.AFFECTED_AGENT,
                QuestionPriority.HIGH,
                "Coercion scales with the number of agents bound and the absence of an "
                "opt-out (Axiom 2).",
                "coercion_profile",
                ["A2"],
                field_target="coercion_profile.scope_number_of_agents",
            ),
        ],
    )
)

_register(
    ScenarioTemplate(
        name="ai_or_algorithmic_decision",
        summary="A decision made or mediated by an automated system.",
        required_fields=["acting_agent", "affected_agents", "coercion_profile"],
        typical_coercion_dimensions=["informational_manipulation", "economic_pressure"],
        emphasized_categories=[
            QuestionCategory.ACTING_AGENT,
            QuestionCategory.AFFECTED_AGENT,
            QuestionCategory.COERCION,
            QuestionCategory.EVIDENCE,
        ],
        typical_evidence_needs=["what the system does", "who is accountable for it"],
        typical_alternatives=["a human review step", "an appeal route", "an opt-out"],
        special_warnings=[
            "A Type I automated system cannot bear duties (Axiom 4); the duty falls on the "
            "Type II agents who deploy it."
        ],
        extra_questions=[
            _q(
                "ai_or_algorithmic_decision",
                1,
                "Is the deciding system itself a Type I tool, and which Type II agent is "
                "accountable for deploying it?",
                QuestionCategory.ACTING_AGENT,
                QuestionPriority.HIGH,
                "Duties bind only Type II agents; an automated tool's coercion is the "
                "responsibility of its deployer (Axiom 4).",
                "agent_type",
                ["A1", "A4"],
                field_target="acting_agent",
            ),
        ],
    )
)


def list_templates() -> list[str]:
    """Return the names of all registered templates, in registration order."""
    return list(_TEMPLATES)


def get_template(name: str) -> ScenarioTemplate | None:
    """Return a template by name, or ``None`` if there is no such template."""
    return _TEMPLATES.get(name)


def all_templates() -> list[ScenarioTemplate]:
    return list(_TEMPLATES.values())
