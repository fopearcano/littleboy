"""Tests for the v0.8 adversarial audit & bias-testing module."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    AdversarialStressTester,
    AgencyProfile,
    AgentType,
    AuditSeverity,
    CoercionJustification,
    CoercionProfile,
    ComparisonEngine,
    ConsentStatus,
    EpistemicStatus,
    EthicalEvaluator,
    LanguageAct,
    LanguageContext,
    LanguageEthicsProfile,
    MoralAgent,
)
from littleboy.cli import app
from littleboy.comparison.models import ActionComparisonSet

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def _load(name: str) -> ActionCase:
    return ActionCase.model_validate_json((EXAMPLES / name).read_text())


def _audit_case(case: ActionCase, policy: str = "standard"):
    return AdversarialStressTester(policy).audit_case(case)


def _ids(audit) -> set[str]:
    return {f.finding_id for f in audit.findings}


def _find(audit, finding_id):
    return next((f for f in audit.findings if f.finding_id == finding_id), None)


def _case(**overrides) -> ActionCase:
    defaults = dict(
        title="Case",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.2, reversibility=1.0, severity=0.2),
        consent=ConsentStatus.GIVEN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


# --- 1. fake consent creates a critical red flag -----------------------------


def test_fake_consent_creates_critical_red_flag():
    audit = _audit_case(_load("audit_fake_consent.json"))
    critical_consent = [
        f
        for f in audit.findings
        if f.severity == AuditSeverity.CRITICAL and f.category.value == "consent"
    ]
    assert critical_consent
    assert audit.has_critical


# --- 2. high power asymmetry + consent creates a warning ---------------------


def test_high_power_asymmetry_plus_consent_warns():
    case = _case(
        coercion_profile=CoercionProfile(social_pressure=0.2, reversibility=1.0, severity=0.2),
        agency_profile=AgencyProfile(agent_type=AgentType.TYPE_II, vulnerability_level=0.2),
        language_act=LanguageAct(
            text="Please consider signing when you are ready.",
            context=LanguageContext(power_asymmetry=0.7, target_vulnerability=0.2),
            ethics_profile=LanguageEthicsProfile(
                clarity=0.8, truthfulness=0.8, consent_support=0.8, manipulation_risk=0.0
            ),
        ),
    )
    audit = _audit_case(case)
    power = _find(audit, "AUD-CONSENT-POWER")
    assert power is not None
    assert power.severity == AuditSeverity.WARNING


# --- 3. missing counterevidence creates an audit finding ---------------------


def test_missing_counterevidence_creates_finding():
    audit = _audit_case(_load("audit_missing_counterevidence.json"))
    assert "AUD-EVID-NO-COUNTER" in _ids(audit)


# --- 4. coercion justification without cessation creates a red flag ----------


def test_justification_without_cessation_is_flagged():
    case = _case(
        coercion_profile=CoercionProfile(physical_force=0.5, reversibility=0.8, severity=0.5),
        justification=CoercionJustification(
            responds_to_existing_or_imminent_coercion=EpistemicStatus.CONFIRMED,
            necessity=EpistemicStatus.CONFIRMED,
            cessation_condition_defined=EpistemicStatus.UNKNOWN,
        ),
    )
    audit = _audit_case(case)
    finding = _find(audit, "AUD-COERCION-NO-CESSATION")
    assert finding is not None
    assert finding.severity == AuditSeverity.SERIOUS


# --- 5. high language manipulation with low coercion -> inconsistency --------


def test_low_coercion_high_manipulation_inconsistency():
    audit = _audit_case(_load("audit_hidden_coercion.json"))
    assert "AUD-COERCION-LANG-INCONSISTENCY" in _ids(audit)


# --- 6. irreversible action with weak evidence -> critical -------------------


def test_irreversible_weak_evidence_is_critical():
    case = _case(
        coercion_profile=CoercionProfile(physical_force=0.5, reversibility=0.1, severity=0.6),
        evidence=None,
        data_quality=None,
    )
    audit = _audit_case(case)
    finding = _find(audit, "AUD-EVID-IRREVERSIBLE-WEAK")
    assert finding is not None
    assert finding.severity == AuditSeverity.CRITICAL


# --- 7. beautiful language, bad content -> persuasive counterfeit ------------


def test_beautiful_language_bad_content_persuasive_counterfeit():
    audit = _audit_case(_load("audit_beautiful_language_bad_content.json"))
    assert "AUD-LANG-PERSUASIVE-COUNTERFEIT" in _ids(audit)
    assert audit.adversarial_risk_profile.leading_language_risk >= 0.5


# --- 8. ugly language, good content -> language-beauty bias ------------------


def test_ugly_language_good_content_beauty_bias_warning():
    audit = _audit_case(_load("audit_ugly_language_good_content.json"))
    assert audit.bias_profile.language_beauty_bias_risk >= 0.5
    assert "AUD-BIAS-BEAUTY-UNDERCREDIT" in _ids(audit)


# --- 9. authority capture triggers an audit finding --------------------------


def test_authority_capture_triggers_finding():
    audit = _audit_case(_load("audit_authority_capture.json"))
    assert "AUD-LANG-AUTHORITY-CAPTURE" in _ids(audit)


# --- 10. protection-as-paternalism check triggers a warning ------------------


def test_protection_as_paternalism_triggers_warning():
    audit = _audit_case(_load("audit_protection_as_paternalism.json"))
    finding = _find(audit, "AUD-IDEOLOGY-CARE_AS_CONTROL")
    assert finding is not None
    assert audit.adversarial_risk_profile.ideological_capture_risk >= 0.5


# --- 11. freedom-as-social-pressure check triggers a warning -----------------


def test_freedom_as_social_pressure_triggers_warning():
    audit = _audit_case(_load("audit_freedom_as_social_pressure.json"))
    assert "AUD-IDEOLOGY-FREEDOM_AS_PRESSURE" in _ids(audit)


# --- 12. evaluator includes the audit report only when enabled ---------------


def test_evaluator_includes_audit_only_when_enabled():
    case = _load("audit_fake_consent.json")
    assert EthicalEvaluator("standard").evaluate(case).audit_report is None
    audited = EthicalEvaluator("standard").evaluate(case, audit=True)
    assert audited.audit_report is not None
    assert audited.audit_report.has_critical
    assert audited.audit_report.judgment_stable is False


# --- 13. CLI audit command works ---------------------------------------------


def test_cli_audit_command_works():
    result = runner.invoke(
        app, ["audit", str(EXAMPLES / "audit_fake_consent.json"), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "findings" in payload
    assert payload["judgment_stable"] is False
    assert payload["red_flags"]


# --- 14. comparison audit detects unstable ranking due to missing data -------


def test_comparison_audit_detects_unstable_ranking():
    cset = ActionComparisonSet.model_validate_json(
        (EXAMPLES / "comparison_uncertain_data.json").read_text()
    )
    result = ComparisonEngine().compare(cset, audit=True)
    assert result.audit is not None
    assert result.audit.ranking_unstable_due_to_missing_data is True
    assert result.ranking_stable is False


# --- 15. audit findings include recommended questions ------------------------


def test_audit_findings_include_recommended_questions():
    audit = _audit_case(_load("audit_hidden_coercion.json"))
    assert any(f.recommended_questions for f in audit.findings)
    assert audit.recommended_questions


# --- extra: a clean, low-risk case is judged stable (no false alarms) --------


def test_clean_case_is_stable():
    audit = _audit_case(_load("low_coercion_good_data.json"))
    assert audit.judgment_stable is True
    assert not audit.has_critical


# --- extra: default evaluation is unchanged when audit is off ----------------


def test_default_evaluation_unchanged_without_audit():
    case = _load("audit_fake_consent.json")
    report = EthicalEvaluator("standard").evaluate(case)
    assert report.audit_report is None
    assert "[audit]" not in " ".join(report.warnings)
