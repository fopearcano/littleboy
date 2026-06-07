"""Behavioural tests for the EthicalEvaluator (the scenarios in the brief)."""

from __future__ import annotations

from littleboy import (
    ActionCase,
    AgentType,
    CoercionProfile,
    ConsentStatus,
    DataQualityProfile,
    EthicalEvaluator,
    EvaluationReport,
    MoralAgent,
    Verdict,
)

POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}


# --- builders ----------------------------------------------------------------


def type_ii(name: str = "Agent A") -> MoralAgent:
    return MoralAgent(name=name, agent_type=AgentType.TYPE_II)


def good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.9,
        source_reliability=0.9,
        specificity=0.85,
        recency=0.9,
        corroboration=0.85,
        ambiguity=0.1,
    )


def poor_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.2,
        source_reliability=0.2,
        specificity=0.2,
        recency=0.3,
        corroboration=0.1,
        ambiguity=0.8,
        missing_critical_facts=["consent record"],
    )


def high_coercion() -> CoercionProfile:
    return CoercionProfile(
        threat=0.9,
        psychological_pressure=0.8,
        severity=0.85,
        duration=0.7,
        reversibility=0.2,
        scope_number_of_agents=10,
    )


def low_coercion() -> CoercionProfile:
    return CoercionProfile(
        social_pressure=0.1,
        duration=0.05,
        reversibility=1.0,
        scope_number_of_agents=5,
        severity=0.05,
    )


def low_coercion_case(**overrides) -> ActionCase:
    """A fully-specified, low-coercion, well-evidenced case (the happy path)."""
    defaults = dict(
        title="Voluntary optional workshop",
        acting_agent=type_ii(),
        affected_agents=[type_ii("Team")],
        intended_goal="Offer optional development",
        coercion_profile=low_coercion(),
        available_alternatives=[],
        data_quality=good_data(),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="Skills gained; no penalty for declining.",
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


# --- Scenario 2: Type II agents can be evaluated morally ---------------------


def test_type_ii_agent_can_be_evaluated():
    report = EthicalEvaluator().evaluate(low_coercion_case())
    assert isinstance(report, EvaluationReport)
    assert isinstance(report.verdict, Verdict)
    assert report.axioms_invoked  # always cites the axioms it used
    assert any("Type II" in reason for reason in report.main_reasons)


# --- Scenario 1: Type I acting agents are flagged as non-duty-bearing ---------


def test_type_i_acting_agent_is_flagged():
    case = low_coercion_case(acting_agent=MoralAgent(name="Guard dog", agent_type=AgentType.TYPE_I))
    report = EthicalEvaluator().evaluate(case)
    assert any("Type I" in warning for warning in report.warnings)


# --- Scenario 3: high coercion + low data quality must not be approved -------


def test_high_coercion_low_data_quality_is_not_confidently_approved():
    case = ActionCase(
        title="Murky high-pressure situation",
        acting_agent=type_ii(),
        coercion_profile=high_coercion(),
        data_quality=poor_data(),
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict in {Verdict.INSUFFICIENT_DATA, Verdict.ETHICALLY_SUSPICIOUS}
    assert report.verdict not in POSITIVE
    assert report.confidence < 0.5


# --- Scenario 4: high coercion with no alternative analysis ------------------


def test_high_coercion_without_alternative_analysis_is_rejected_or_suspicious():
    case = ActionCase(
        title="Forceful directive, no alternatives considered",
        acting_agent=type_ii(),
        coercion_profile=high_coercion(),
        available_alternatives=None,  # not analysed
        data_quality=good_data(),
        consent=ConsentStatus.REFUSED,
        responds_to_existing_coercion=False,
        expected_consequences="Compliance obtained under pressure.",
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict in {Verdict.NOT_ACCEPTABLE, Verdict.ETHICALLY_SUSPICIOUS}
    assert report.verdict not in POSITIVE


# --- Scenario 5: low coercion + good data is cautiously positive -------------


def test_low_coercion_good_data_is_cautiously_positive():
    report = EthicalEvaluator().evaluate(low_coercion_case())
    assert report.verdict in POSITIVE
    assert report.coercion_score < 0.3
    assert report.uncertainty_level.value in {"LOW", "MODERATE"}


# --- Scenario 6: missing consent is explicitly reported ----------------------


def test_missing_consent_is_reported():
    case = low_coercion_case(consent=ConsentStatus.UNKNOWN)
    report = EthicalEvaluator().evaluate(case)
    assert any("consent" in item.lower() for item in report.missing_data)


# --- Cross-cutting guarantees: never a black box -----------------------------


def test_every_report_exposes_its_reasoning():
    report = EthicalEvaluator().evaluate(low_coercion_case())
    assert report.axioms_invoked
    assert report.coercion_reasoning
    assert report.data_quality_reasoning
    assert report.main_reasons
    # The standing scope disclaimer is always attached.
    assert any("not a legal" in w.lower() for w in report.warnings)


def test_missing_profiles_yield_insufficient_data():
    case = ActionCase(title="Bare report with almost nothing known")
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict == Verdict.INSUFFICIENT_DATA
    assert report.missing_data


def test_less_coercive_alternative_is_detected():
    gentle = CoercionProfile(social_pressure=0.1, reversibility=1.0)
    case = low_coercion_case(
        coercion_profile=high_coercion(),
        available_alternatives=[
            {"description": "Ask politely instead", "coercion_profile": gentle.model_dump()}
        ],
        consent=ConsentStatus.REFUSED,
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.less_coercive_alternatives  # the gentle option is surfaced
