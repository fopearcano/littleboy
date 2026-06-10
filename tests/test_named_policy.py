"""Tests for the v0.22 named custom policies."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from littleboy import (
    NamedPolicy,
    PolicyProvenance,
    load_named_policy,
    resolve_policy_ref,
    save_named_policy,
)
from littleboy.calibration import candidate_profile, default_external_outcome_corpus
from littleboy.cli import app
from littleboy.core.enums import PolicyMode
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.reasoning.report import render_text
from littleboy.rules.policy import DEFAULT_PROFILES

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
NAMED_GOLDEN = Path(__file__).resolve().parent / "golden" / "named_policy.golden.json"
runner = CliRunner()


def _gate_policy() -> NamedPolicy:
    return NamedPolicy(
        name="research_gate_025",
        profile=candidate_profile("standard", {"min_data_quality_for_approval": "0.25"}),
        provenance=PolicyProvenance(
            base="standard",
            changes={"min_data_quality_for_approval": "0.35 -> 0.25"},
            description="data gate lowered after the v0.20 diagnosis",
        ),
    )


def test_save_load_round_trip_is_exact(tmp_path):
    named = _gate_policy()
    path = tmp_path / "gate.json"
    save_named_policy(path, named)
    loaded = load_named_policy(path)
    assert loaded == named  # full model equality, provenance included


def test_loaded_policy_behaves_identically(tmp_path):
    named = _gate_policy()
    path = tmp_path / "gate.json"
    save_named_policy(path, named)
    loaded = load_named_policy(path)
    direct = EthicalEvaluator(named.profile)
    via_file = EthicalEvaluator(loaded.profile)
    for entry in default_external_outcome_corpus().entries[:10]:
        assert direct.evaluate(entry.case).verdict == via_file.evaluate(entry.case).verdict


def test_load_validates_garbage(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_named_policy(bad)
    # an out-of-range profile value is rejected on load, not mid-evaluation
    payload = _gate_policy().model_dump(mode="json")
    payload["profile"]["coercion_moderate"] = 7.0
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_named_policy(bad)
    # unknown fields are rejected too (extra='forbid')
    payload = _gate_policy().model_dump(mode="json")
    payload["surprise"] = True
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_named_policy(bad)


def test_resolve_policy_ref_handles_all_three_shapes(tmp_path):
    policy, label = resolve_policy_ref("strict")
    assert policy == PolicyMode.STRICT and label == ""
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    profile, label = resolve_policy_ref(str(path))
    assert label == "research_gate_025"
    assert profile.min_data_quality_for_approval == 0.25
    with pytest.raises(ValueError, match="not a built-in mode"):
        resolve_policy_ref("no_such_policy_or_file")


def test_builtins_are_untouched_by_save_and_load(tmp_path):
    snapshots = {m: p.model_dump() for m, p in DEFAULT_PROFILES.items()}
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    load_named_policy(path)
    assert {m: p.model_dump() for m, p in DEFAULT_PROFILES.items()} == snapshots


def test_report_carries_the_custom_label():
    case = default_external_outcome_corpus().entries[0].case
    named = _gate_policy()
    report = EthicalEvaluator(named.profile, policy_label=named.name).evaluate(case)
    assert report.policy_label == "research_gate_025"
    assert report.policy_mode == PolicyMode.STANDARD  # the base, plus the label
    # built-in evaluations stay unlabelled (old reports unchanged)
    plain = EthicalEvaluator(PolicyMode.STANDARD).evaluate(case)
    assert plain.policy_label == ""


def test_text_render_distinguishes_custom_from_builtin():
    case = default_external_outcome_corpus().entries[0].case
    named = _gate_policy()
    custom_text = render_text(
        EthicalEvaluator(named.profile, policy_label=named.name).evaluate(case)
    )
    assert "[policy: research_gate_025 (custom, base standard)]" in custom_text
    plain_text = render_text(EthicalEvaluator(PolicyMode.STANDARD).evaluate(case))
    assert "[policy: standard]" in plain_text


def test_named_policy_golden_regression():
    payload = _gate_policy().model_dump(mode="json")
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        NAMED_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(NAMED_GOLDEN.read_text())
    assert payload == expected, (
        "the named-policy payload drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_tune_save_writes_policy_and_impact(tmp_path):
    out = tmp_path / "gate.json"
    result = runner.invoke(
        app,
        [
            "tune",
            "--set",
            "min_data_quality_for_approval=0.25",
            "--external",
            "--no-goldens",
            "--save",
            str(out),
            "--name",
            "research_gate_025",
            "--describe",
            "data gate lowered after the v0.20 diagnosis",
        ],
    )
    assert result.exit_code == 0
    named = load_named_policy(out)
    assert named.name == "research_gate_025"
    assert named.profile.min_data_quality_for_approval == 0.25
    assert named.provenance is not None
    assert named.provenance.base == "standard"
    assert named.provenance.changes == {"min_data_quality_for_approval": "0.35 -> 0.25"}
    impact = json.loads(out.with_suffix(".impact.json").read_text())
    assert impact["n_flips"] == 3  # the full tuning-impact report rides alongside


def test_cli_evaluate_accepts_a_policy_file(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    result = runner.invoke(
        app,
        ["evaluate", str(EXAMPLES / "irreversible_low_data_case.json"), "--policy", str(path)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["policy_label"] == "research_gate_025"
    assert payload["policy_mode"] == "standard"


def test_cli_diagnose_announces_a_custom_policy(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    result = runner.invoke(app, ["diagnose", "--external", "--policy", str(path)])
    assert result.exit_code == 0
    assert "[using custom policy 'research_gate_025'" in result.output


def test_cli_tune_accepts_a_custom_base(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    result = runner.invoke(
        app,
        [
            "tune",
            "--set",
            "coercion_moderate=0.2",
            "--base",
            str(path),
            "--external",
            "--no-goldens",
        ],
    )
    assert result.exit_code == 0
    assert "coercion_moderate: 0.3 -> 0.2" in result.output


def test_cli_rejects_a_bad_policy_ref():
    result = runner.invoke(
        app,
        [
            "evaluate",
            str(EXAMPLES / "simple_case.json"),
            "--policy",
            "no_such_policy_or_file.json",
        ],
    )
    assert result.exit_code == 2
