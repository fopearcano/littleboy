"""Tests for the v0.9 deliberation & value-of-information layer."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    AgentType,
    CoercionProfile,
    ConsentStatus,
    ConsequenceEstimate,
    ConsequenceSet,
    DataQualityProfile,
    Deliberator,
    MoralAgent,
    TimeHorizon,
    Verdict,
)
from littleboy.cli import app
from littleboy.comparison.models import ActionComparisonSet
from littleboy.deliberation.voi import verdict_distance

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def _load(name: str) -> ActionCase:
    return ActionCase.model_validate_json((EXAMPLES / name).read_text())


def _load_set(name: str) -> ActionComparisonSet:
    return ActionComparisonSet.model_validate_json((EXAMPLES / name).read_text())


# --- narration ---------------------------------------------------------------


def test_deliberation_narrates_verdict():
    d = Deliberator("standard").deliberate(_load("manipulative_language_case.json"))
    assert d.headline
    assert d.verdict is not None
    assert d.steps  # there is always at least the coercion/confidence context
    # the narration agrees with the evaluator's verdict
    assert d.verdict.value in d.headline


# --- value of information: the pivotal unknown -------------------------------


def test_voi_identifies_pivotal_consent():
    d = Deliberator("standard").deliberate(_load("voi_consent_pivotal.json"))
    assert d.most_informative is not None
    assert d.most_informative.field == "consent"
    assert d.most_informative.changes_verdict is True
    assert d.stable_under_information is False


def test_voi_records_counterfactual_resolutions():
    d = Deliberator("standard").deliberate(_load("voi_consent_pivotal.json"))
    res = d.most_informative.resolutions
    assert len(res) == 2
    # the two resolutions land on different verdicts (that is why it is pivotal)
    assert len({r.verdict for r in res}) > 1


def test_fully_specified_case_is_information_stable():
    case = ActionCase(
        title="Fully specified, low-coercion, consented action",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
        data_quality=DataQualityProfile(
            completeness=0.85,
            source_reliability=0.85,
            specificity=0.85,
            recency=0.85,
            corroboration=0.8,
            ambiguity=0.15,
        ),
        consent=ConsentStatus.GIVEN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="no lasting effect",
                    horizon=TimeHorizon.SHORT_TERM,
                    coercion_delta=-0.05,
                    probability=0.8,
                    confidence=0.8,
                )
            ]
        ),
    )
    d = Deliberator("standard").deliberate(case)
    assert d.information_values == []
    assert d.most_informative is None
    assert d.stable_under_information is True


# --- comparison deliberation -------------------------------------------------


def test_comparison_deliberation_finds_pivotal_option_fact():
    cd = Deliberator("standard").deliberate_comparison(_load_set("comparison_voi_pivotal.json"))
    assert cd.best_option_id == "option_x"
    assert cd.most_informative is not None
    assert cd.most_informative.changes_best_option is True
    assert cd.most_informative.value == 1.0
    assert cd.ranking_robust is False
    assert cd.why_top_wins


# --- helpers -----------------------------------------------------------------


def test_verdict_distance_metric():
    assert verdict_distance(Verdict.ACCEPTABLE, Verdict.ACCEPTABLE) == 0.0
    assert verdict_distance(Verdict.ACCEPTABLE, Verdict.NOT_ACCEPTABLE) == 1.0
    # resolving (or creating) the data gate is a maximal change
    assert verdict_distance(Verdict.INSUFFICIENT_DATA, Verdict.ACCEPTABLE) == 1.0


# --- CLI ---------------------------------------------------------------------


def test_cli_deliberate_case_works():
    result = runner.invoke(app, ["deliberate", str(EXAMPLES / "voi_consent_pivotal.json")])
    assert result.exit_code == 0
    assert "DELIBERATION:" in result.stdout
    assert "Most informative unknown" in result.stdout


def test_cli_deliberate_comparison_works():
    result = runner.invoke(
        app,
        [
            "deliberate",
            str(EXAMPLES / "comparison_voi_pivotal.json"),
            "--compare",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert '"target": "comparison"' in result.stdout


# --- backward compatibility --------------------------------------------------


def test_deliberation_does_not_change_default_evaluation():
    from littleboy import EthicalEvaluator

    case = _load("voi_consent_pivotal.json")
    base = EthicalEvaluator("standard").evaluate(case)
    # deliberation re-runs the evaluator internally; the user's own report is untouched.
    Deliberator("standard").deliberate(case)
    again = EthicalEvaluator("standard").evaluate(case)
    assert base.verdict == again.verdict
    assert base.audit_report is None
