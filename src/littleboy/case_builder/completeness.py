"""Completeness analysis for the LittleBoy case builder.

This turns the generated questions, plus a few cross-cutting checks, into a
:class:`~littleboy.core.models.CaseCompletenessReport`: how ready a case is to be
judged, whether it can be judged at all, whether it can be judged *confidently*,
and which questions to answer next. The aim is to prevent premature moral
judgment under weak data (Axiom 5).
"""

from __future__ import annotations

from littleboy.case_builder.questions import (
    HIGH_VULNERABILITY_THRESHOLD,
    IRREVERSIBLE_THRESHOLD,
    generate_questions,
)
from littleboy.case_builder.templates import ScenarioTemplate
from littleboy.core.enums import ConsentStatus, QuestionPriority
from littleboy.core.models import ActionCase, CaseCompletenessReport, Question
from littleboy.core.scoring import score_coercion
from littleboy.data.evidence import assess_evidence
from littleboy.data.quality import assess_data_quality, combine_epistemic_score
from littleboy.rules.policy import PolicyProfile, get_policy

# How much each missing question subtracts from a perfect completeness score.
_PENALTY = {
    QuestionPriority.CRITICAL: 0.25,
    QuestionPriority.HIGH: 0.12,
    QuestionPriority.MEDIUM: 0.05,
    QuestionPriority.LOW: 0.02,
}
_PRIORITY_RANK = {
    QuestionPriority.CRITICAL: 0,
    QuestionPriority.HIGH: 1,
    QuestionPriority.MEDIUM: 2,
    QuestionPriority.LOW: 3,
}
_MAX_RECOMMENDED = 6


def _field_label(q: Question) -> str:
    return q.field_target or q.category.value


def completeness_report(
    case: ActionCase,
    *,
    policy: PolicyProfile | None = None,
    template: ScenarioTemplate | None = None,
) -> CaseCompletenessReport:
    """Assess how ready ``case`` is for evaluation."""
    policy = policy or get_policy(None)
    question_set = generate_questions(case, policy=policy, template=template)
    questions = list(question_set.questions)

    critical = [q for q in questions if q.priority == QuestionPriority.CRITICAL]
    high = [q for q in questions if q.priority == QuestionPriority.HIGH]
    optional = [
        q for q in questions if q.priority in (QuestionPriority.MEDIUM, QuestionPriority.LOW)
    ]

    score = 1.0 - sum(_PENALTY[q.priority] for q in questions)
    score = max(0.0, min(1.0, score))

    can_evaluate = not any(q.blocks_evaluation for q in questions)
    can_confidently_evaluate = can_evaluate and not critical

    recommended = sorted(questions, key=lambda q: _PRIORITY_RANK[q.priority])[:_MAX_RECOMMENDED]

    warnings = _build_warnings(case, policy)

    return CaseCompletenessReport(
        completeness_score=round(score, 4),
        can_evaluate=can_evaluate,
        can_confidently_evaluate=can_confidently_evaluate,
        critical_missing_fields=[_field_label(q) for q in critical],
        high_priority_missing_fields=[_field_label(q) for q in high],
        optional_missing_fields=[_field_label(q) for q in optional],
        recommended_next_questions=recommended,
        warnings=warnings,
    )


def _build_warnings(case: ActionCase, policy: PolicyProfile) -> list[str]:
    """The cross-cutting completeness warnings (the rules in the brief, step 4)."""
    warnings: list[str] = []

    coercion_present = case.coercion_profile is not None
    coercion_score = score_coercion(case.coercion_profile).score if coercion_present else 0.0
    consent_status = case.effective_consent_status()
    consent_weak = consent_status in (
        ConsentStatus.UNKNOWN,
        ConsentStatus.DISPUTED,
        ConsentStatus.COERCED,
    )

    dq = assess_data_quality(case.data_quality)
    evidence = assess_evidence(case.evidence)
    has_epistemic_basis = case.data_quality is not None or evidence.provided
    epistemic = combine_epistemic_score(
        dq.score, evidence_provided=evidence.provided, evidence_score=evidence.score
    )
    weak_epistemic = (not has_epistemic_basis) or epistemic < policy.min_data_quality_for_approval

    irreversible = (
        coercion_present
        and case.coercion_profile.reversibility_is_known
        and case.coercion_profile.reversibility < IRREVERSIBLE_THRESHOLD
    )
    vulnerability = case.agency_profile.vulnerability_level if case.agency_profile else None
    high_vulnerability = vulnerability is not None and vulnerability >= HIGH_VULNERABILITY_THRESHOLD

    if case.effective_agent_type() is None:
        warnings.append("Acting agent type is unknown; confidence is limited (Axiom 4).")
    if not case.affected_agents:
        warnings.append(
            "Affected agents are unknown; evaluation is blocked until they are identified."
        )
    if consent_status == ConsentStatus.UNKNOWN:
        warnings.append("Consent is unknown; confident approval is blocked (Axioms 0, 2).")
    if (
        coercion_present
        and coercion_score >= policy.max_coercion_for_acceptable
        and case.justification is None
    ):
        warnings.append(
            "Coercion is high but no justification is supplied; evaluation can proceed only "
            "as suspicious or not acceptable (Axiom 3)."
        )
    if case.available_alternatives is None and coercion_score >= policy.coercion_moderate:
        warnings.append(
            "Coercion is moderate/high and alternatives are unknown; confident approval is "
            "blocked (Axiom 2)."
        )
    if irreversible and weak_epistemic:
        warnings.append(
            "The action is irreversible and the evidential basis is weak; evaluation should "
            "be treated as insufficient data or blocked (Axiom 5)."
        )
    if high_vulnerability and (consent_weak or weak_epistemic):
        warnings.append(
            "Affected subject is highly vulnerable and consent/evidence are weak; evaluation "
            "should be blocked or heavily downgraded (Axioms 0, 2)."
        )

    return warnings
