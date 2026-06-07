"""Question generation for the LittleBoy case builder.

Given a (possibly partial) :class:`~littleboy.core.models.ActionCase`, this
module works out what LittleBoy still needs to know in order to judge the action
and returns precise, prioritised :class:`~littleboy.core.models.Question` s. Each
question explains *why it matters* ethically and points at the axioms it serves.

The builder never invents facts. It only asks for them. Question priority is
context-sensitive: e.g. an unknown consent becomes *critical* when the affected
subject is highly vulnerable, and unknown alternatives become *critical* when
coercion is already moderate or high.
"""

from __future__ import annotations

from littleboy.case_builder.templates import ScenarioTemplate
from littleboy.core.enums import ConsentStatus, QuestionCategory, QuestionPriority
from littleboy.core.models import ActionCase, Question, QuestionSet
from littleboy.core.scoring import score_coercion
from littleboy.rules.policy import PolicyProfile, get_policy

# Below this reversibility value an action is treated as effectively irreversible.
IRREVERSIBLE_THRESHOLD = 0.30
HIGH_VULNERABILITY_THRESHOLD = 0.6

_PRIORITY_ORDER = (
    QuestionPriority.LOW,
    QuestionPriority.MEDIUM,
    QuestionPriority.HIGH,
    QuestionPriority.CRITICAL,
)


def _bump(priority: QuestionPriority, steps: int = 1) -> QuestionPriority:
    """Raise a priority by ``steps`` levels (capped at CRITICAL)."""
    idx = _PRIORITY_ORDER.index(priority)
    return _PRIORITY_ORDER[min(idx + steps, len(_PRIORITY_ORDER) - 1)]


def generate_questions(
    case: ActionCase,
    *,
    policy: PolicyProfile | None = None,
    template: ScenarioTemplate | None = None,
) -> QuestionSet:
    """Return the questions LittleBoy would ask to make ``case`` evaluable."""
    policy = policy or get_policy(None)
    coercion_present = case.coercion_profile is not None
    coercion_score = score_coercion(case.coercion_profile).score if coercion_present else 0.0
    consent_status = case.effective_consent_status()
    consent_unknown = consent_status == ConsentStatus.UNKNOWN
    vulnerability = case.agency_profile.vulnerability_level if case.agency_profile else None
    high_vulnerability = vulnerability is not None and vulnerability >= HIGH_VULNERABILITY_THRESHOLD

    emphasized = set(template.emphasized_categories) if template else set()
    questions: list[Question] = []

    def add(
        question_id: str,
        text: str,
        category: QuestionCategory,
        priority: QuestionPriority,
        why_it_matters: str,
        expected_answer_type: str,
        related_axioms: list[str],
        *,
        blocks_evaluation: bool = False,
        suggested_choices: list[str] | None = None,
        field_target: str | None = None,
    ) -> None:
        if category in emphasized:
            priority = _bump(priority)
        questions.append(
            Question(
                question_id=question_id,
                text=text,
                category=category,
                priority=priority,
                why_it_matters=why_it_matters,
                expected_answer_type=expected_answer_type,
                related_axioms=related_axioms,
                blocks_evaluation=blocks_evaluation,
                suggested_choices=suggested_choices,
                field_target=field_target,
            )
        )

    # --- Action description --------------------------------------------------
    if not case.description.strip():
        add(
            "Q-DESCRIPTION",
            "What exactly is the action being evaluated?",
            QuestionCategory.ACTION_DESCRIPTION,
            QuestionPriority.MEDIUM,
            "A vague action cannot be assessed for the coercion it involves.",
            "text",
            ["A1"],
            field_target="description",
        )

    # --- Acting agent --------------------------------------------------------
    if case.effective_agent_type() is None:
        add(
            "Q-AGENT-TYPE",
            "Is the acting agent a Type I (no symbolic metacognition) or Type II agent?",
            QuestionCategory.ACTING_AGENT,
            QuestionPriority.HIGH,
            "Only Type II agents can bear duties (Axiom 4); an unknown type limits "
            "how confidently the action can be judged.",
            "agent_type",
            ["A1", "A4"],
            suggested_choices=["TYPE_I", "TYPE_II"],
            field_target="acting_agent",
        )

    # --- Affected agents (a hard prerequisite) -------------------------------
    if not case.affected_agents:
        add(
            "Q-AFFECTED",
            "Who are the agents affected by this action?",
            QuestionCategory.AFFECTED_AGENT,
            QuestionPriority.CRITICAL,
            "Coercion is suffered by affected agents; without knowing who is "
            "affected, the central ethical question cannot be assessed.",
            "list_of_agents",
            ["A0", "A2"],
            blocks_evaluation=True,
            field_target="affected_agents",
        )

    # --- Coercion presence (a hard prerequisite) -----------------------------
    if not coercion_present:
        add(
            "Q-COERCION-PRESENCE",
            "What coercion, if any, does this action involve (force, threat, "
            "economic/psychological pressure, manipulation, legal/social pressure)?",
            QuestionCategory.COERCION,
            QuestionPriority.CRITICAL,
            "Coercion is the central ethical quantity (Axiom 0); without it the "
            "action cannot be assessed.",
            "coercion_profile",
            ["A0", "A2"],
            blocks_evaluation=True,
            field_target="coercion_profile",
        )
    else:
        # Reversibility of the coercion.
        if not case.coercion_profile.reversibility_is_known:
            add(
                "Q-REVERSIBILITY",
                "Is the action's effect reversible, and to what degree (0 = irreversible, "
                "1 = fully reversible)?",
                QuestionCategory.REVERSIBILITY,
                QuestionPriority.HIGH,
                "Irreversible coercion demands a stronger evidential basis; "
                "reversibility bounds the harm (Axiom 5).",
                "score_0_1",
                ["A5"],
                field_target="coercion_profile.reversibility",
            )

    # --- Consent -------------------------------------------------------------
    if consent_unknown:
        priority = QuestionPriority.CRITICAL if high_vulnerability else QuestionPriority.HIGH
        add(
            "Q-CONSENT",
            "Did the affected agents consent, and was that consent informed and voluntary?",
            QuestionCategory.CONSENT,
            priority,
            "Consent that is unknown blocks confident approval; coerced consent is "
            "not valid consent (Axioms 0, 2).",
            "consent_status",
            ["A0", "A2"],
            blocks_evaluation=high_vulnerability,
            suggested_choices=[s.value for s in ConsentStatus],
            field_target="consent",
        )

    # --- Justification for high coercion -------------------------------------
    if (
        coercion_present
        and coercion_score >= policy.max_coercion_for_acceptable
        and case.justification is None
    ):
        add(
            "Q-JUSTIFICATION",
            "If coercion is high, is there a complete Axiom 3 justification (responds to "
            "prior coercion, necessary, proportional, no less coercive alternative, reduces "
            "total coercion, with a defined stop condition)?",
            QuestionCategory.JUSTIFICATION,
            QuestionPriority.CRITICAL,
            "High coercion can be acceptable only with a complete justification; "
            "without one it is not acceptable (Axiom 3).",
            "justification",
            ["A3"],
            field_target="justification",
        )

    # --- Alternatives --------------------------------------------------------
    if case.available_alternatives is None:
        if coercion_score >= policy.coercion_moderate:
            priority = QuestionPriority.CRITICAL
        else:
            priority = QuestionPriority.MEDIUM
        add(
            "Q-ALTERNATIVES",
            "What less-coercive alternatives were considered, and how feasible is each?",
            QuestionCategory.ALTERNATIVES,
            priority,
            "If a feasible less-coercive alternative exists, the action is not the "
            "least-coercive option (Axiom 2); unknown alternatives block confident "
            "approval of a coercive action.",
            "alternatives",
            ["A2"],
            field_target="available_alternatives",
        )

    # --- Coercion source -----------------------------------------------------
    if (
        coercion_present
        and case.responds_to_existing_coercion is None
        and coercion_score >= policy.coercion_moderate
    ):
        add(
            "Q-COERCION-SOURCE",
            "Is this action a response to existing or imminent coercion?",
            QuestionCategory.JUSTIFICATION,
            QuestionPriority.MEDIUM,
            "Coercion responding to prior coercion can sometimes be justified; "
            "originating coercion cannot (Axiom 3).",
            "boolean",
            ["A3"],
            field_target="responds_to_existing_coercion",
        )

    # --- Consequences --------------------------------------------------------
    if case.expected_consequences is None:
        add(
            "Q-CONSEQUENCES",
            "What are the expected consequences of the action?",
            QuestionCategory.CONSEQUENCES,
            QuestionPriority.MEDIUM,
            "Consequences bear on whether coercion is proportional and whether it "
            "reduces total coercion (Axioms 2, 3).",
            "text",
            ["A2", "A3"],
            field_target="expected_consequences",
        )

    # --- Epistemic basis: data quality and evidence --------------------------
    if case.data_quality is None and case.evidence is None:
        add(
            "Q-DATA-QUALITY",
            "How reliable is the information about this case (completeness, sources, "
            "corroboration)?",
            QuestionCategory.DATA_QUALITY,
            QuestionPriority.CRITICAL,
            "A confident verdict built on poor information is itself an ethical failure (Axiom 5).",
            "data_quality",
            ["A5"],
            blocks_evaluation=True,
            field_target="data_quality",
        )
    elif case.evidence is None:
        add(
            "Q-EVIDENCE",
            "Is there structured evidence for the key claims, with sources?",
            QuestionCategory.EVIDENCE,
            QuestionPriority.LOW,
            "Per-claim evidence lets LittleBoy judge how well each claim is "
            "supported and flag contested ones (Axiom 5).",
            "evidence",
            ["A5"],
            field_target="evidence",
        )

    # --- Vulnerability -------------------------------------------------------
    if case.agency_profile is None:
        add(
            "Q-VULNERABILITY",
            "How vulnerable are the affected agents (capacity, dependency, power imbalance)?",
            QuestionCategory.VULNERABILITY,
            QuestionPriority.MEDIUM,
            "High vulnerability raises the bar for valid consent and the scrutiny "
            "applied to any coercion (Axioms 0, 2).",
            "agency_profile",
            ["A0", "A2"],
            field_target="agency_profile",
        )

    # --- Temporal & consequence questions (v0.7) -----------------------------
    # Asked for coercive cases that have not characterised their future or
    # reversibility -- an action must be judged across time, not just now.
    if coercion_present and case.consequences is None and case.temporal_profile is None:
        add(
            "Q-FUTURE-CONSEQUENCES",
            "What happens after the immediate effect (short, medium, long term)? Could the "
            "coercion grow, repeat, normalise, create dependency, or become irreversible later?",
            QuestionCategory.CONSEQUENCES,
            QuestionPriority.MEDIUM,
            "An action that lowers coercion now but raises it later is ethically unstable; "
            "coercion must be judged across time (Axioms 2, 5).",
            "consequences",
            ["A2", "A5"],
            field_target="consequences",
        )
    if coercion_present and case.reversibility_profile is None:
        add(
            "Q-REVERSIBILITY-OVER-TIME",
            "Is the action reversible over time, at what cost, and what remains harmful even "
            "if it is reversed?",
            QuestionCategory.REVERSIBILITY,
            QuestionPriority.MEDIUM,
            "Irreversible actions demand stronger evidence and justification; residual harm "
            "persists even after reversal (Axioms 3, 5).",
            "reversibility_profile",
            ["A3", "A5"],
            field_target="reversibility_profile",
        )
    if case.is_inaction:
        add(
            "Q-INACTION-PREVENTS",
            "Does doing nothing allow existing coercion to continue or grow -- and would acting "
            "prevent a greater coercion later?",
            QuestionCategory.CONSEQUENCES,
            QuestionPriority.HIGH,
            "Inaction is not neutral if it permits coercion to continue; and temporary coercion "
            "may be qualifiedly justified only if it credibly prevents greater future coercion "
            "(Axioms 2, 3).",
            "consequences",
            ["A2", "A3"],
            field_target="consequences",
        )

    # --- Template-specific questions -----------------------------------------
    if template is not None:
        for q in template.extra_questions:
            questions.append(q)

    return QuestionSet(questions=questions)
