"""Tests for the v0.4 scenario builder / case-input wizard."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    AgencyProfile,
    AgentType,
    CaseBuilder,
    CoercionProfile,
    ConsentStatus,
    DataQualityProfile,
    EthicalEvaluator,
    MoralAgent,
    QuestionCategory,
    QuestionPriority,
    get_template,
)
from littleboy.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def _agent(name: str = "A") -> MoralAgent:
    return MoralAgent(name=name, agent_type=AgentType.TYPE_II)


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.85,
        source_reliability=0.85,
        specificity=0.8,
        recency=0.85,
        corroboration=0.8,
        ambiguity=0.15,
    )


def _complete_case(**overrides) -> ActionCase:
    """A well-specified case; override fields to introduce gaps."""
    defaults = dict(
        title="Case",
        description="A described action.",
        acting_agent=_agent(),
        affected_agents=[_agent("B")],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
        available_alternatives=[],
        data_quality=_good_data(),
        agency_profile=AgencyProfile(agent_type=AgentType.TYPE_II, vulnerability_level=0.1),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="benign",
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


def _categories(question_set) -> set[QuestionCategory]:
    return {q.category for q in question_set.questions}


# --- 1. incomplete case generates critical questions -------------------------


def test_incomplete_case_generates_critical_questions():
    builder = CaseBuilder()
    qs = builder.generate_questions(ActionCase(title="Bare case"))
    assert qs.critical  # at least one CRITICAL question
    assert any(q.blocks_evaluation for q in qs.questions)


# --- 2. missing affected agents blocks confident evaluation ------------------


def test_missing_affected_agents_blocks_evaluation():
    builder = CaseBuilder()
    case = _complete_case(affected_agents=[])
    qs = builder.generate_questions(case)
    report = builder.completeness_report(case)
    affected_q = next(q for q in qs.questions if q.category == QuestionCategory.AFFECTED_AGENT)
    assert affected_q.blocks_evaluation is True
    assert report.can_evaluate is False


# --- 3. unknown consent generates a consent question -------------------------


def test_unknown_consent_generates_consent_question():
    builder = CaseBuilder()
    qs = builder.generate_questions(_complete_case(consent=ConsentStatus.UNKNOWN))
    assert QuestionCategory.CONSENT in _categories(qs)


# --- 4. high coercion + unknown alternatives -> alternatives question --------


def test_high_coercion_unknown_alternatives_generates_critical_alternatives_question():
    builder = CaseBuilder()
    case = _complete_case(
        coercion_profile=CoercionProfile(physical_force=0.9, severity=0.8, reversibility=0.3),
        available_alternatives=None,
    )
    qs = builder.generate_questions(case)
    alt = next(q for q in qs.questions if q.category == QuestionCategory.ALTERNATIVES)
    assert alt.priority == QuestionPriority.CRITICAL


# --- 5. irreversible action + low data quality generates a warning -----------


def test_irreversible_low_data_quality_generates_warning():
    builder = CaseBuilder()
    case = _complete_case(
        coercion_profile=CoercionProfile(physical_force=0.5, severity=0.4, reversibility=0.1),
        data_quality=DataQualityProfile(
            completeness=0.2,
            source_reliability=0.2,
            specificity=0.2,
            recency=0.3,
            corroboration=0.2,
            ambiguity=0.7,
        ),
    )
    report = builder.completeness_report(case)
    assert any("irreversible" in w.lower() for w in report.warnings)


# --- 6. vulnerability + unknown consent -> critical, blocking question -------


def test_vulnerability_with_unknown_consent_is_critical():
    builder = CaseBuilder()
    case = _complete_case(
        consent=ConsentStatus.UNKNOWN,
        agency_profile=AgencyProfile(agent_type=AgentType.TYPE_II, vulnerability_level=0.85),
    )
    qs = builder.generate_questions(case)
    consent_q = next(q for q in qs.questions if q.category == QuestionCategory.CONSENT)
    assert consent_q.priority == QuestionPriority.CRITICAL
    assert consent_q.blocks_evaluation is True


# --- 7. template-specific questions are generated ----------------------------


def test_template_specific_questions_are_generated():
    builder = CaseBuilder()
    qs = builder.generate_questions(_complete_case(), template="emergency_intervention")
    assert any(q.question_id.startswith("Q-TPL-EMERGENCY_INTERVENTION") for q in qs.questions)


# --- 8. language manipulation template asks about informational manipulation -


def test_language_template_asks_about_informational_manipulation():
    builder = CaseBuilder()
    qs = builder.generate_questions(_complete_case(), template="speech_or_language_manipulation")
    assert any("manipulat" in q.text.lower() for q in qs.questions)


# --- 9. medical template asks consent + alternatives, no clinical/legal claims


def test_medical_template_asks_consent_and_alternatives_without_clinical_claims():
    builder = CaseBuilder()
    qs = builder.generate_questions(
        _complete_case(consent=ConsentStatus.UNKNOWN), "medical_decision"
    )
    cats = _categories(qs)
    assert QuestionCategory.CONSENT in cats
    assert QuestionCategory.ALTERNATIVES in cats
    template = get_template("medical_decision")
    assert any("not medical advice" in w.lower() for w in template.special_warnings)


# --- 10. CLI `questions` works with a partial example ------------------------


def test_cli_questions_works_with_partial_example():
    result = runner.invoke(
        app, ["questions", str(EXAMPLES / "partial_generic_case.json"), "--format", "text"]
    )
    assert result.exit_code == 0
    assert "COMPLETENESS" in result.stdout

    json_result = runner.invoke(
        app,
        [
            "questions",
            str(EXAMPLES / "partial_medical_case.json"),
            "--template",
            "medical_decision",
            "--format",
            "json",
        ],
    )
    assert json_result.exit_code == 0
    payload = json.loads(json_result.stdout)
    assert "completeness" in payload and "questions" in payload


# --- 11. CLI `build-case` creates valid JSON ---------------------------------


def test_cli_build_case_creates_valid_json(tmp_path):
    out = tmp_path / "built.json"
    # One line per wizard prompt; only the title is given, the rest are skipped.
    answers = "My constructed case\n" + "\n" * 14
    result = runner.invoke(
        app, ["build-case", "--no-evaluate", "--output", str(out)], input=answers
    )
    assert result.exit_code == 0
    assert out.exists()
    rebuilt = ActionCase.model_validate_json(out.read_text())
    assert rebuilt.title == "My constructed case"


# --- 12. completeness report appears in the evaluation report ----------------


def test_completeness_report_in_evaluation_report():
    report = EthicalEvaluator().evaluate(_complete_case(consent=ConsentStatus.UNKNOWN))
    assert report.case_completeness is not None
    assert 0.0 <= report.case_completeness.completeness_score <= 1.0
    # An incomplete case yields recommended questions in the evaluation report.
    assert report.recommended_questions


def test_completeness_can_be_disabled():
    report = EthicalEvaluator(include_completeness=False).evaluate(_complete_case())
    assert report.case_completeness is None


# --- 13. recommended questions include why_it_matters ------------------------


def test_questions_explain_why_they_matter():
    builder = CaseBuilder()
    qs = builder.generate_questions(ActionCase(title="Bare case"))
    assert qs.questions
    for q in qs.questions:
        assert q.why_it_matters.strip()
        assert q.related_axioms  # each ties back to at least one axiom
