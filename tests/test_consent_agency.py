"""Tests for consent and agency handling (brief scenarios 1, 2, 3)."""

from __future__ import annotations

from littleboy import (
    ActionCase,
    AgencyProfile,
    AgentType,
    CoercionProfile,
    ConsentProfile,
    ConsentStatus,
    DataQualityProfile,
    EpistemicStatus,
    EthicalEvaluator,
    MoralAgent,
    Verdict,
)

POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}


def _type_ii(name: str = "Agent") -> MoralAgent:
    return MoralAgent(name=name, agent_type=AgentType.TYPE_II)


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.9,
        source_reliability=0.9,
        specificity=0.85,
        recency=0.9,
        corroboration=0.85,
        ambiguity=0.1,
    )


def _low_coercion() -> CoercionProfile:
    return CoercionProfile(social_pressure=0.1, duration=0.05, reversibility=1.0, severity=0.05)


def _base_case(**overrides) -> ActionCase:
    defaults = dict(
        title="Case",
        acting_agent=_type_ii(),
        affected_agents=[_type_ii("Subject")],
        coercion_profile=_low_coercion(),
        available_alternatives=[],
        data_quality=_good_data(),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="benign",
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


# --- Scenario 1: unknown consent lowers confidence ---------------------------


def test_unknown_consent_lowers_confidence():
    known = EthicalEvaluator().evaluate(_base_case(consent=ConsentStatus.GIVEN))
    unknown = EthicalEvaluator().evaluate(_base_case(consent=ConsentStatus.UNKNOWN))
    assert unknown.confidence < known.confidence
    assert any("consent" in m.lower() for m in unknown.missing_data)


# --- Scenario 2: disputed consent prevents confident approval ----------------


def test_disputed_consent_prevents_confident_approval():
    case = _base_case(
        consent=ConsentStatus.DISPUTED,
        consent_profile=ConsentProfile(
            status=ConsentStatus.DISPUTED,
            informed=EpistemicStatus.DISPUTED,
            voluntary=EpistemicStatus.DISPUTED,
        ),
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict != Verdict.ACCEPTABLE
    assert any("disput" in w.lower() for w in report.warnings)


def test_coerced_consent_is_not_valid_consent():
    case = _base_case(consent=ConsentStatus.COERCED)
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict not in {Verdict.ACCEPTABLE}
    assert any("coerced" in w.lower() for w in report.warnings)


# --- Scenario 3: high vulnerability increases warnings -----------------------


def test_high_vulnerability_increases_warnings():
    low_vuln = _base_case(
        agency_profile=AgencyProfile(agent_type=AgentType.TYPE_II, vulnerability_level=0.1)
    )
    high_vuln = _base_case(
        agency_profile=AgencyProfile(agent_type=AgentType.TYPE_II, vulnerability_level=0.85)
    )
    low_report = EthicalEvaluator().evaluate(low_vuln)
    high_report = EthicalEvaluator().evaluate(high_vuln)

    assert any("vulnerab" in w.lower() for w in high_report.warnings)
    assert not any("vulnerab" in w.lower() for w in low_report.warnings)


def test_report_exposes_consent_and_agency_status():
    report = EthicalEvaluator().evaluate(_base_case())
    assert report.consent_status is not None
    assert report.agency_status is not None
