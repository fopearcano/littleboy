"""Tests for the v0.21 dry-run tuner."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from littleboy.calibration import (
    candidate_profile,
    default_external_outcome_corpus,
    run_reliability,
    tune_dry_run,
    tuning_golden_payload,
)
from littleboy.cli import app
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.rules.policy import DEFAULT_PROFILES

TUNE_GOLDEN = Path(__file__).resolve().parent / "golden" / "tuning_impact.golden.json"
runner = CliRunner()

GATE_CHANGE = {"min_data_quality_for_approval": "0.25"}


def test_dry_run_is_really_dry():
    snapshots = {mode: profile.model_dump() for mode, profile in DEFAULT_PROFILES.items()}
    corpus = default_external_outcome_corpus()
    case = corpus.entries[0].case
    verdict_before = EthicalEvaluator(PolicyMode.STANDARD).evaluate(case).verdict
    tune_dry_run(corpus, GATE_CHANGE)
    # the built-in profiles are untouched, and so is every verdict under them
    assert {m: p.model_dump() for m, p in DEFAULT_PROFILES.items()} == snapshots
    assert EthicalEvaluator(PolicyMode.STANDARD).evaluate(case).verdict == verdict_before


def test_candidate_validation_rejects_garbage():
    with pytest.raises(ValueError, match="unknown policy parameter"):
        candidate_profile("standard", {"coercion_vibes": 0.2})
    with pytest.raises(Exception, match="less than or equal"):
        candidate_profile("standard", {"min_data_quality_for_approval": 1.5})
    # string values are coerced through the model, like everywhere else
    cand = candidate_profile("standard", {"min_data_quality_for_approval": "0.25"})
    assert cand.min_data_quality_for_approval == 0.25
    assert cand.unknown_consent_is_blocker is False  # everything else inherited


def test_flip_arithmetic_is_consistent():
    impact = tune_dry_run(default_external_outcome_corpus(), GATE_CHANGE, check_goldens=False)
    assert impact.n_flips == len(impact.flips) == sum(impact.flip_summary.values())
    for flip in impact.flips:
        assert flip.before != flip.after
        assert flip.direction in {
            "more permissive",
            "less permissive",
            "gains a verdict",
            "declines to insufficient data",
        }
    # lowering the data gate only releases verdicts; nothing becomes insufficient
    assert all(flip.before == Verdict.INSUFFICIENT_DATA for flip in impact.flips)
    assert all(flip.direction == "gains a verdict" for flip in impact.flips)


def test_before_accuracy_matches_the_reliability_table():
    corpus = default_external_outcome_corpus()
    impact = tune_dry_run(corpus, GATE_CHANGE, check_goldens=False)
    report = run_reliability(corpus, labeler="hana")
    for split_rel in report.splits:
        std = next(p for p in split_rel.policies if p.policy == "standard")
        si = next(
            s
            for s in impact.stakeholder_impacts
            if s.target == "hana" and s.split == split_rel.split
        )
        assert si.before_correct == std.exact_correct  # same measurement, before the change


def test_the_tradeoff_is_on_the_table():
    impact = tune_dry_run(default_external_outcome_corpus(), GATE_CHANGE, check_goldens=False)
    # every labeller and the consensus are covered
    assert set(impact.net_deltas) == {"consensus", "dora", "emil", "fay", "gus", "hana"}
    # the gate change helps some stakeholders and HURTS fay (who endorsed the refusals)
    assert impact.net_deltas["hana"] > 0
    assert impact.net_deltas["fay"] < 0
    assert any("net agreement falls for: fay" in note for note in impact.notes)


def test_stakeholder_intervals_and_deltas_are_consistent():
    impact = tune_dry_run(default_external_outcome_corpus(), GATE_CHANGE, check_goldens=False)
    for si in impact.stakeholder_impacts:
        assert si.before_ci.low <= si.before_accuracy <= si.before_ci.high
        assert si.after_ci.low <= si.after_accuracy <= si.after_ci.high
        assert si.delta == round(si.after_accuracy - si.before_accuracy, 4)


def test_golden_impact_names_the_breakage():
    impact = tune_dry_run(default_external_outcome_corpus(), GATE_CHANGE)
    by_name = {gi.golden: gi for gi in impact.golden_impacts}
    # the external corpus flips -> its goldens break; the fully-specified panel does not
    assert by_name["cv_gain_inference.golden.json"].would_break
    assert by_name["disagreement_diagnosis.golden.json"].would_break
    assert not by_name["labelled_outcome_reliability.golden.json"].would_break
    assert not by_name["audit_corpus.golden.json"].would_break  # the audit ignores the data gate
    assert not by_name["disagreement_explanation.golden.json"].checked  # honestly unchecked
    assert any("golden files to regenerate deliberately" in note for note in impact.notes)


def test_coercion_change_touches_the_audit():
    # the audit reads coercion_moderate, so changing it must flag the audit golden
    impact = tune_dry_run(default_external_outcome_corpus(), {"coercion_moderate": "0.2"})
    by_name = {gi.golden: gi for gi in impact.golden_impacts}
    assert by_name["audit_corpus.golden.json"].would_break
    assert by_name["scoring_corpus.golden.json"].would_break  # detector band moves


def test_identity_change_reports_no_effect():
    impact = tune_dry_run(
        default_external_outcome_corpus(),
        {"min_data_quality_for_approval": "0.35"},  # the current value
        check_goldens=False,
    )
    assert impact.changes == {}
    assert impact.n_flips == 0
    assert all(d == 0.0 for d in impact.net_deltas.values())
    assert any("unchanged for every stakeholder" in note for note in impact.notes)


def test_multiple_changes_apply_together():
    impact = tune_dry_run(
        default_external_outcome_corpus(),
        {"min_data_quality_for_approval": "0.25", "coercion_moderate": "0.2"},
        check_goldens=False,
    )
    assert set(impact.changes) == {"min_data_quality_for_approval", "coercion_moderate"}


def test_empty_changes_are_rejected():
    with pytest.raises(ValueError, match="no changes given"):
        tune_dry_run(default_external_outcome_corpus(), {})


def test_tuning_impact_is_deterministic():
    corpus = default_external_outcome_corpus()
    a = tuning_golden_payload(tune_dry_run(corpus, GATE_CHANGE))
    b = tuning_golden_payload(tune_dry_run(corpus, GATE_CHANGE))
    assert a == b


def test_tuning_golden_regression():
    payload = tuning_golden_payload(tune_dry_run(default_external_outcome_corpus(), GATE_CHANGE))
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        TUNE_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(TUNE_GOLDEN.read_text())
    assert payload == expected, (
        "tuning impact drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_tune_works():
    result = runner.invoke(
        app, ["tune", "--set", "min_data_quality_for_approval=0.25", "--external"]
    )
    assert result.exit_code == 0
    assert "TUNE (dry run)" in result.stdout
    assert "verdict flips: 3/40" in result.stdout
    assert "<- loses" in result.stdout  # the cost is visible
    assert "golden impact" in result.stdout
    assert "WOULD BREAK" in result.stdout


def test_cli_tune_json_parses():
    result = runner.invoke(
        app,
        [
            "tune",
            "--set",
            "min_data_quality_for_approval=0.25",
            "--external",
            "--no-goldens",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["base_policy"] == "standard"
    assert payload["n_flips"] == 3
    assert payload["golden_impacts"] == []  # --no-goldens


def test_cli_tune_error_paths():
    # malformed --set
    result = runner.invoke(app, ["tune", "--set", "gate0.25", "--external"])
    assert result.exit_code == 2
    # unknown parameter
    result = runner.invoke(app, ["tune", "--set", "coercion_vibes=0.2", "--external"])
    assert result.exit_code == 2
    # out-of-range value
    result = runner.invoke(
        app, ["tune", "--set", "min_data_quality_for_approval=1.5", "--external"]
    )
    assert result.exit_code == 2
