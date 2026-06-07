"""Evaluator-level v0.2 tests (brief scenarios 4, 7, 8, 12)."""

from __future__ import annotations

import json

from littleboy import (
    ActionCase,
    AgentType,
    AlternativeAction,
    CoercionJustification,
    CoercionProfile,
    ConsentStatus,
    DataQualityProfile,
    EpistemicStatus,
    EthicalEvaluator,
    MoralAgent,
    Verdict,
)
from littleboy.reasoning.report import render_json


def _agent(name: str = "A") -> MoralAgent:
    return MoralAgent(name=name, agent_type=AgentType.TYPE_II)


def _data(**overrides) -> DataQualityProfile:
    defaults = dict(
        completeness=0.8,
        source_reliability=0.8,
        specificity=0.8,
        recency=0.8,
        corroboration=0.7,
        ambiguity=0.2,
    )
    defaults.update(overrides)
    return DataQualityProfile(**defaults)


# --- Scenario 4: informational manipulation is counted as coercion -----------


def test_informational_manipulation_is_flagged_as_coercion():
    case = ActionCase(
        title="Manipulative framing",
        acting_agent=_agent(),
        affected_agents=[_agent()],
        coercion_profile=CoercionProfile(informational_manipulation=0.8, reversibility=0.6),
        available_alternatives=None,
        data_quality=_data(),
        consent=ConsentStatus.UNKNOWN,
        responds_to_existing_coercion=False,
        expected_consequences="users misled",
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.coercion_score > 0.5
    assert any("informational manipulation" in w.lower() for w in report.warnings)


# --- Scenario 7: justified emergency coercion -> acceptable with reservations -


def test_justified_emergency_coercion_is_acceptable_with_reservations():
    case = ActionCase(
        title="Restrain an attacker",
        acting_agent=_agent(),
        affected_agents=[_agent("attacker"), _agent("victim")],
        coercion_profile=CoercionProfile(
            physical_force=0.7, threat=0.3, duration=0.2, reversibility=0.9, severity=0.5
        ),
        available_alternatives=[
            AlternativeAction(title="Do nothing", estimated_coercion_score=0.95, feasibility=1.0),
            AlternativeAction(
                title="Verbal de-escalation", estimated_coercion_score=0.15, feasibility=0.2
            ),
        ],
        data_quality=_data(),
        consent=ConsentStatus.NOT_APPLICABLE,
        responds_to_existing_coercion=True,
        prior_coercion_description="active assault",
        expected_consequences="assault stops; attacker released after",
        justification=CoercionJustification(
            responds_to_existing_or_imminent_coercion=EpistemicStatus.CONFIRMED,
            no_less_coercive_alternative_available=EpistemicStatus.LIKELY,
            necessity=EpistemicStatus.CONFIRMED,
            proportionality=EpistemicStatus.LIKELY,
            expected_total_coercion_reduction=0.6,
            cessation_condition_defined=EpistemicStatus.CONFIRMED,
            reversibility=EpistemicStatus.CONFIRMED,
        ),
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict == Verdict.ACCEPTABLE_WITH_RESERVATIONS
    assert report.justification_result is not None
    assert report.justification_result.is_justified is True


# --- Scenario 8: irreversible action + low data quality -> insufficient data --


def test_irreversible_action_with_low_data_quality_is_insufficient():
    case = ActionCase(
        title="Irreversible act on weak evidence",
        acting_agent=_agent(),
        affected_agents=[_agent()],
        coercion_profile=CoercionProfile(
            physical_force=0.5, duration=0.2, reversibility=0.1, severity=0.3
        ),
        available_alternatives=[],
        # Epistemic basis ~0.45: above the 0.35 floor, below the 0.50 irreversibility bar.
        data_quality=_data(
            completeness=0.6,
            source_reliability=0.6,
            specificity=0.5,
            recency=0.6,
            corroboration=0.5,
        ),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="permanent change",
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict == Verdict.INSUFFICIENT_DATA
    assert any("irreversible" in r.lower() for r in report.main_reasons)


# --- Scenario 12: reports expose axioms + machine-readable fields ------------


def test_report_includes_axioms_and_is_machine_readable():
    case = ActionCase(
        title="Simple",
        acting_agent=_agent(),
        affected_agents=[_agent()],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0),
        available_alternatives=[],
        data_quality=_data(),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="benign",
    )
    report = EthicalEvaluator().evaluate(case)

    assert report.axioms_invoked
    assert any(a.startswith("A0") for a in report.axioms_invoked)
    assert report.explanation
    assert report.ethical_experiment is not None

    # Round-trips through JSON with all the documented fields present.
    payload = json.loads(render_json(report))
    for key in (
        "verdict",
        "coercion_score",
        "data_quality_score",
        "evidence_score",
        "confidence",
        "consent_status",
        "agency_status",
        "justification_result",
        "alternatives_analysis",
        "ethical_experiment",
        "missing_data",
        "warnings",
        "axioms_invoked",
        "explanation",
    ):
        assert key in payload
