"""Tests for the v0.5 language & coercion module."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    AgencyProfile,
    AgentType,
    CaseBuilder,
    ConsentStatus,
    DataQualityProfile,
    EthicalEvaluator,
    LanguageAct,
    LanguageContext,
    LanguageEthicsProfile,
    LanguageMedium,
    MoralAgent,
    QuestionCategory,
    Verdict,
    analyze_language,
    score_constructive_language,
    score_linguistic_coercion,
)
from littleboy.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}
runner = CliRunner()


def _ctx(**overrides) -> LanguageContext:
    return LanguageContext(**overrides)


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.85,
        source_reliability=0.85,
        specificity=0.8,
        recency=0.85,
        corroboration=0.8,
        ambiguity=0.15,
    )


def _lang_case(act: LanguageAct, **overrides) -> ActionCase:
    defaults = dict(
        title="Language case",
        acting_agent=MoralAgent(name="Speaker", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="Target", agent_type=AgentType.TYPE_II)],
        data_quality=_good_data(),
        consent=ConsentStatus.GIVEN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        expected_consequences="known",
        language_act=act,
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


# --- 1. false necessity increases linguistic coercion ------------------------


def test_false_necessity_increases_coercion():
    ctx = _ctx(power_asymmetry=0.5, stakes=0.5)
    low = score_linguistic_coercion(LanguageEthicsProfile(false_necessity=0.0), ctx)
    high = score_linguistic_coercion(LanguageEthicsProfile(false_necessity=0.8), ctx)
    assert high > low


# --- 2. false dichotomy increases linguistic coercion ------------------------


def test_false_dichotomy_increases_coercion():
    ctx = _ctx(power_asymmetry=0.5, stakes=0.5)
    low = score_linguistic_coercion(LanguageEthicsProfile(false_dichotomy=0.0), ctx)
    high = score_linguistic_coercion(LanguageEthicsProfile(false_dichotomy=0.8), ctx)
    assert high > low


# --- 3. shame pressure increases coercion, especially under vulnerability -----


def test_shame_pressure_amplified_by_vulnerability():
    profile = LanguageEthicsProfile(shame_pressure=0.8)
    low_vuln = score_linguistic_coercion(profile, _ctx(target_vulnerability=0.1))
    high_vuln = score_linguistic_coercion(profile, _ctx(target_vulnerability=0.9))
    assert high_vuln > low_vuln
    assert score_linguistic_coercion(
        profile, _ctx(target_vulnerability=0.9)
    ) > score_linguistic_coercion(
        LanguageEthicsProfile(shame_pressure=0.0), _ctx(target_vulnerability=0.9)
    )


# --- 4. fear pressure increases coercion, especially under power asymmetry ----


def test_fear_pressure_amplified_by_power_asymmetry():
    profile = LanguageEthicsProfile(fear_pressure=0.8)
    low_power = score_linguistic_coercion(profile, _ctx(power_asymmetry=0.1))
    high_power = score_linguistic_coercion(profile, _ctx(power_asymmetry=0.9))
    assert high_power > low_power


# --- 5. unclear language in a high-stakes context creates a warning ----------


def test_unclear_language_high_stakes_warns():
    act = LanguageAct(
        text="",
        context=_ctx(medium=LanguageMedium.MEDICAL_CONSENT, stakes=0.8),
        ethics_profile=LanguageEthicsProfile(clarity=0.2, ambiguity_level=0.7),
    )
    analysis = analyze_language(act)
    assert any("clarity" in w.lower() or "ambig" in w.lower() for w in analysis.warnings)


# --- 6. manipulative consent language reduces consent quality ----------------


def test_manipulative_language_reduces_consent_quality():
    clean = score_constructive_language(
        LanguageEthicsProfile(consent_support=0.9, manipulation_risk=0.0), _ctx()
    )
    manipulative = score_constructive_language(
        LanguageEthicsProfile(consent_support=0.9, manipulation_risk=0.8), _ctx()
    )
    assert manipulative.consent_support < clean.consent_support


# --- 7. language module contributes to the total coercion profile ------------


def test_language_contributes_to_total_coercion():
    manipulative = LanguageAct(
        text="You have no choice.",
        context=_ctx(power_asymmetry=0.7, stakes=0.7, target_vulnerability=0.6),
        ethics_profile=LanguageEthicsProfile(
            manipulation_risk=0.7, fear_pressure=0.6, agency_respect=0.2
        ),
    )
    # No base coercion profile at all: coercion must come from the language.
    report = EthicalEvaluator().evaluate(_lang_case(manipulative, coercion_profile=None))
    assert report.coercion_score > 0.3
    assert report.language_analysis is not None
    assert report.language_analysis.linguistic_coercion_score > 0.3


# --- 8. constructive language: lower coercion, higher agency support ---------


def test_constructive_language_lower_coercion_higher_agency():
    constructive = LanguageEthicsProfile(
        clarity=0.9, truthfulness=0.9, agency_respect=0.9, consent_support=0.9
    )
    manipulative = LanguageEthicsProfile(
        manipulation_risk=0.8, fear_pressure=0.7, agency_respect=0.2, truthfulness=0.3
    )
    ctx = _ctx(power_asymmetry=0.5, stakes=0.5)
    assert score_linguistic_coercion(constructive, ctx) < score_linguistic_coercion(
        manipulative, ctx
    )
    assert (
        score_constructive_language(constructive, ctx).agency_support
        > score_constructive_language(manipulative, ctx).agency_support
    )


# --- 9. testimonial injustice rule triggers a warning ------------------------


def test_testimonial_injustice_rule_triggers():
    case = ActionCase.model_validate_json(
        (EXAMPLES / "testimonial_injustice_case.json").read_text()
    )
    report = EthicalEvaluator().evaluate(case)
    r016 = next(r for r in report.reasoning_trace.applied if r.rule_id == "LB-R016")
    assert r016.status.value == "failed"
    assert report.language_analysis.replaces_subject_framing is True


# --- 10. semantic compression case generates a warning -----------------------


def test_semantic_compression_generates_warning():
    case = ActionCase.model_validate_json(
        (EXAMPLES / "semantic_compression_euthanasia_case.json").read_text()
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.language_analysis.replaces_subject_framing is True
    assert any("framing" in w.lower() for w in report.warnings)


# --- 11. speech/language template generates language-specific questions -------


def test_language_template_generates_language_questions():
    builder = CaseBuilder()
    qs = builder.generate_questions(
        ActionCase(title="A message"), template="speech_or_language_manipulation"
    )
    assert any(q.category == QuestionCategory.LANGUAGE for q in qs.questions)


# --- 12. CLI `analyze-language` works ----------------------------------------


def test_cli_analyze_language_works():
    result = runner.invoke(
        app,
        ["analyze-language", str(EXAMPLES / "language_manipulative_case.json"), "--format", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["linguistic_coercion_score"] > 0.5
    assert "manipulation_findings" in payload

    text_result = runner.invoke(
        app,
        ["analyze-language", str(EXAMPLES / "language_constructive_case.json"), "--format", "text"],
    )
    assert text_result.exit_code == 0
    assert "LINGUISTIC COERCION" in text_result.stdout


def test_cli_analyze_language_without_language_act_fails():
    result = runner.invoke(app, ["analyze-language", str(EXAMPLES / "simple_case.json")])
    assert result.exit_code == 2
    assert "no `language_act`" in result.output


# --- 13. the evaluator includes the language rule trace ----------------------


def test_evaluator_includes_language_rule_trace():
    case = ActionCase.model_validate_json(
        (EXAMPLES / "language_manipulative_case.json").read_text()
    )
    report = EthicalEvaluator().evaluate(case)
    applied_ids = {r.rule_id for r in report.reasoning_trace.applied}
    assert {"LB-R013", "LB-R014", "LB-R015", "LB-R016", "LB-R017", "LB-R018"} <= applied_ids
    r013 = next(r for r in report.reasoning_trace.applied if r.rule_id == "LB-R013")
    assert r013.status.value != "not_applicable"


# --- 14. constructive-language duty rule applies when language is central -----


def test_constructive_language_duty_rule_applies():
    act = LanguageAct(
        text="Plain explanation.",
        context=_ctx(stakes=0.7),
        ethics_profile=LanguageEthicsProfile(clarity=0.9, agency_respect=0.9),
    )
    report = EthicalEvaluator().evaluate(_lang_case(act))
    r017 = next(r for r in report.reasoning_trace.applied if r.rule_id == "LB-R017")
    assert r017.status.value != "not_applicable"


# --- 15. no confident approval when consent rests on manipulative language ----


def test_no_confident_approval_when_consent_is_manipulated():
    act = LanguageAct(
        text="You have no choice but to agree.",
        context=_ctx(medium=LanguageMedium.CONTRACT, power_asymmetry=0.7, stakes=0.6),
        ethics_profile=LanguageEthicsProfile(
            clarity=0.3, manipulation_risk=0.7, consent_support=0.2, agency_respect=0.2
        ),
    )
    case = _lang_case(
        act,
        consent=ConsentStatus.GIVEN,
        agency_profile=AgencyProfile(agent_type=AgentType.TYPE_II, vulnerability_level=0.6),
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict not in POSITIVE
    r015 = next(r for r in report.reasoning_trace.applied if r.rule_id == "LB-R015")
    assert r015.status.value == "failed"
