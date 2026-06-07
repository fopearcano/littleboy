"""Tests for the Ethical Experiment runner (brief scenario 10)."""

from __future__ import annotations

from littleboy import (
    ActionCase,
    AgentType,
    AlternativeAction,
    CoercionJustification,
    CoercionProfile,
    ConsentStatus,
    DataQualityProfile,
    EpistemicStatus,
    EthicalExperiment,
    EthicalExperimentResult,
    MoralAgent,
)


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.9,
        source_reliability=0.9,
        specificity=0.85,
        recency=0.9,
        corroboration=0.85,
        ambiguity=0.1,
    )


def test_experiment_returns_missing_data_questions_for_sparse_case():
    # A case with almost nothing known should yield open questions and gaps.
    result = EthicalExperiment().run(ActionCase(title="Vague report of pressure"))
    assert isinstance(result, EthicalExperimentResult)
    assert result.recommended_next_questions
    assert result.insufficient_data_points
    assert result.can_be_judged is False  # not enough to judge


def test_experiment_reports_tested_axioms_and_risk():
    case = ActionCase(
        title="Mild nudge",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0),
        available_alternatives=[],
        data_quality=_good_data(),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="benign",
    )
    result = EthicalExperiment().run(case)
    assert result.tested_axioms
    assert 0.0 <= result.risk_of_coercion <= 1.0
    assert result.can_be_judged is True


def test_experiment_detects_a_contradiction():
    # The justification claims no less-coercive alternative exists, yet a feasible
    # less-coercive alternative is supplied: that is an internal contradiction.
    case = ActionCase(
        title="Contradictory justification",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(physical_force=0.8, severity=0.7, reversibility=0.4),
        available_alternatives=[
            AlternativeAction(title="Gentle option", estimated_coercion_score=0.05, feasibility=1.0)
        ],
        data_quality=_good_data(),
        consent=ConsentStatus.NOT_APPLICABLE,
        responds_to_existing_coercion=True,
        expected_consequences="known",
        justification=CoercionJustification(
            responds_to_existing_or_imminent_coercion=EpistemicStatus.CONFIRMED,
            no_less_coercive_alternative_available=EpistemicStatus.CONFIRMED,
            necessity=EpistemicStatus.CONFIRMED,
            proportionality=EpistemicStatus.CONFIRMED,
            expected_total_coercion_reduction=0.5,
            cessation_condition_defined=EpistemicStatus.CONFIRMED,
            reversibility=EpistemicStatus.CONFIRMED,
        ),
    )
    result = EthicalExperiment().run(case)
    assert result.contradictions
    assert any("less coercive" in c.lower() for c in result.contradictions)
