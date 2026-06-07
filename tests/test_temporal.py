"""Tests for the v0.7 temporal & consequence module."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    ActionComparisonSet,
    AgentType,
    CaseBuilder,
    CoercionProfile,
    ComparisonEngine,
    ConsentStatus,
    ConsequenceEstimate,
    ConsequenceSet,
    CumulativeCoercionProfile,
    DataQualityProfile,
    EthicalEvaluator,
    MoralAgent,
    PolicyMode,
    TimeHorizon,
    Verdict,
    project_temporal,
    score_cumulative_coercion,
)
from littleboy.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}
runner = CliRunner()


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.85,
        source_reliability=0.85,
        specificity=0.85,
        recency=0.85,
        corroboration=0.8,
        ambiguity=0.1,
    )


def _case(**overrides) -> ActionCase:
    defaults = dict(
        title="Case",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
        data_quality=_good_data(),
        consent=ConsentStatus.GIVEN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        expected_consequences="benign",
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


def _load_case(name: str) -> ActionCase:
    return ActionCase.model_validate_json((EXAMPLES / name).read_text())


def _rule(report, rule_id):
    return next(r for r in report.reasoning_trace.applied if r.rule_id == rule_id)


# --- 1. long-term coercion downgrades low immediate coercion -----------------


def test_long_term_coercion_downgrades_low_immediate():
    report = EthicalEvaluator().evaluate(_load_case("temporal_low_now_high_later.json"))
    assert report.verdict not in {Verdict.ACCEPTABLE}
    tp = report.temporal_projection
    assert tp.long_term_coercion > tp.immediate_coercion
    assert _rule(report, "LB-R019").status.value == "failed"


# --- 2. temporary coercion preventing greater coercion -> with reservations --


def test_temporary_coercion_preventing_worse_is_acceptable_with_reservations():
    report = EthicalEvaluator().evaluate(_load_case("temporal_high_now_prevents_worse.json"))
    assert report.verdict == Verdict.ACCEPTABLE_WITH_RESERVATIONS
    assert report.temporal_projection.prevents_greater_future_coercion is True


# --- 3. inaction is evaluated as non-neutral ---------------------------------


def test_inaction_is_non_neutral():
    report = EthicalEvaluator().evaluate(_load_case("temporal_inaction_not_neutral.json"))
    assert report.verdict not in POSITIVE
    assert _rule(report, "LB-R022").status.value == "failed"


# --- 4. irreversible action with weak data -> insufficient / blocked ---------


def test_irreversible_weak_data_is_insufficient():
    report = EthicalEvaluator().evaluate(_load_case("temporal_irreversible_weak_data.json"))
    assert report.verdict == Verdict.INSUFFICIENT_DATA


# --- 5. cumulative coercion increases risk -----------------------------------


def test_cumulative_coercion_increases_risk():
    base = CumulativeCoercionProfile(single_action_coercion=0.15)
    amplified = CumulativeCoercionProfile(
        single_action_coercion=0.15,
        repetition_likelihood=0.9,
        normalization_risk=0.8,
        precedent_risk=0.8,
        institutionalization_risk=0.7,
    )
    assert score_cumulative_coercion(amplified) > score_cumulative_coercion(base)
    assert score_cumulative_coercion(amplified) > 0.5


# --- 6. normalization risk contributes to cumulative coercion ----------------


def test_normalization_risk_contributes():
    without = CumulativeCoercionProfile(single_action_coercion=0.15, repetition_likelihood=0.9)
    with_norm = CumulativeCoercionProfile(
        single_action_coercion=0.15, repetition_likelihood=0.9, normalization_risk=0.9
    )
    assert score_cumulative_coercion(with_norm) > score_cumulative_coercion(without)


# --- 7. unknown reversibility lowers confidence ------------------------------


def test_unknown_reversibility_lowers_confidence():
    known = EthicalEvaluator().evaluate(
        _case(coercion_profile=CoercionProfile(threat=0.3, reversibility=1.0, severity=0.2))
    )
    unknown = EthicalEvaluator().evaluate(
        _case(coercion_profile=CoercionProfile(threat=0.3, severity=0.2))  # reversibility unset
    )
    assert unknown.confidence < known.confidence


# --- 8. temporal uncertainty appears in the report ---------------------------


def test_temporal_uncertainty_in_report():
    report = EthicalEvaluator().evaluate(_load_case("temporal_irreversible_weak_data.json"))
    tp = report.temporal_projection
    assert tp.has_temporal_data is True
    assert tp.high_risk_unknowns  # the low-confidence, high-impact consequence is flagged


# --- 9. comparison detects immediate vs long-term conflict -------------------


def test_comparison_detects_horizon_conflict():
    cset = ActionComparisonSet.model_validate_json(
        (EXAMPLES / "comparison_temporal_tradeoff.json").read_text()
    )
    result = ComparisonEngine().compare(cset)
    assert result.rankings_conflict is True
    assert result.immediate_ranking[0] != result.long_term_ranking[0]


# --- 10. precautionary policy penalises temporal uncertainty more strongly ---


def test_precautionary_penalises_temporal_uncertainty_more():
    case = _case(
        coercion_profile=CoercionProfile(physical_force=0.3, reversibility=0.8, severity=0.2),
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="possible large future coercion",
                    horizon=TimeHorizon.LONG_TERM,
                    coercion_delta=0.6,
                    severity=0.6,
                    probability=0.6,
                    confidence=0.3,
                    evidence_quality=0.3,
                )
            ]
        ),
    )
    standard = EthicalEvaluator(PolicyMode.STANDARD).evaluate(case)
    precautionary = EthicalEvaluator(PolicyMode.PRECAUTIONARY).evaluate(case)
    assert precautionary.confidence < standard.confidence


# --- 11. case builder asks reversibility and future-consequence questions ----


def test_case_builder_asks_temporal_questions():
    case = _case(coercion_profile=CoercionProfile(threat=0.4, reversibility=0.6, severity=0.3))
    qs = CaseBuilder().generate_questions(case)
    ids = {q.question_id for q in qs.questions}
    assert "Q-FUTURE-CONSEQUENCES" in ids
    assert "Q-REVERSIBILITY-OVER-TIME" in ids


# --- 12. CLI `temporal` command works ----------------------------------------


def test_cli_temporal_command_works():
    case_path = str(EXAMPLES / "temporal_cumulative_policy_risk.json")
    result = runner.invoke(app, ["temporal", case_path, "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["has_temporal_data"] is True
    assert payload["cumulative_coercion"] > 0.5


# --- 13. existing (pre-v0.7) example JSON files still evaluate ----------------


def test_old_examples_still_evaluate():
    for name in ("simple_case.json", "high_coercion_case.json", "low_coercion_good_data.json"):
        report = EthicalEvaluator().evaluate(_load_case(name))
        assert isinstance(report.verdict, Verdict)
        # Non-temporal cases carry an inert projection.
        assert report.temporal_projection is not None
        assert report.temporal_projection.has_temporal_data is False


# --- 14. temporal rules appear in the rule trace -----------------------------


def test_temporal_rules_in_trace():
    report = EthicalEvaluator().evaluate(_load_case("temporal_cumulative_policy_risk.json"))
    applied = {r.rule_id for r in report.reasoning_trace.applied}
    assert {"LB-R019", "LB-R020", "LB-R021", "LB-R022", "LB-R023", "LB-R024"} <= applied
    assert _rule(report, "LB-R021").status.value == "failed"


# --- 15. high-impact low-confidence consequence creates a warning ------------


def test_high_impact_low_confidence_warns():
    result = project_temporal(
        base_coercion=0.2,
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="a big but uncertain future harm",
                    horizon=TimeHorizon.LONG_TERM,
                    coercion_delta=0.7,
                    severity=0.8,
                    probability=0.5,
                    confidence=0.2,
                    evidence_quality=0.2,
                )
            ]
        ),
    )
    assert result.consequence_report.high_impact_low_confidence
    assert result.high_risk_unknowns


def test_no_temporal_data_is_inert():
    result = project_temporal(base_coercion=0.4)
    assert result.has_temporal_data is False
    assert result.expected_total_coercion == 0.4
    assert result.warnings == []
