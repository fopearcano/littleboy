"""Tests for named custom policies (v0.22) and calibration under them (v0.23)."""

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
    profile_changes,
    resolve_policy_ref,
    save_named_policy,
    verify_named_policy,
)
from littleboy.calibration import (
    candidate_profile,
    default_external_outcome_corpus,
    recommend_policy_for_stakeholder,
    run_reliability,
    tune_dry_run,
)
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
    # v0.23: the diagnosis itself carries the name (not just a stderr notice)
    assert "DIAGNOSIS: engine[research_gate_025] vs consensus" in result.output


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


# --- calibration under a named policy + provenance integrity (v0.23) ----------


def test_profile_changes_is_the_canonical_rendering():
    named = _gate_policy()
    base = DEFAULT_PROFILES[PolicyMode.STANDARD]
    assert profile_changes(base, named.profile) == {"min_data_quality_for_approval": "0.35 -> 0.25"}
    assert profile_changes(base, base) == {}


def test_verify_consistent_provenance():
    check = verify_named_policy(_gate_policy())
    assert check.has_provenance and check.consistent
    assert check.problems == []
    assert check.recomputed_changes == check.declared_changes


def test_verify_catches_every_kind_of_tampering():
    # 1. mismatched value: the declared history lies about the change
    named = _gate_policy()
    named.provenance.changes["min_data_quality_for_approval"] = "0.35 -> 0.30"
    check = verify_named_policy(named)
    assert not check.consistent
    assert any("mismatched change" in p for p in check.problems)

    # 2. undeclared change: the profile differs from base in ways provenance omits
    named = _gate_policy()
    named.profile = named.profile.model_copy(update={"coercion_moderate": 0.2})
    check = verify_named_policy(named)
    assert not check.consistent
    assert any("undeclared change: coercion_moderate" in p for p in check.problems)

    # 3. declared-but-not-real change
    named = _gate_policy()
    named.provenance.changes["min_confidence"] = "0.3 -> 0.2"
    check = verify_named_policy(named)
    assert not check.consistent
    assert any("not present in the profile" in p for p in check.problems)

    # 4. unknown base
    named = _gate_policy()
    named.provenance.base = "imaginary"
    check = verify_named_policy(named)
    assert not check.consistent
    assert any("unknown base policy" in p for p in check.problems)


def test_verify_without_provenance_says_so():
    named = NamedPolicy(name="bare", profile=_gate_policy().profile)
    check = verify_named_policy(named)
    assert not check.has_provenance
    assert check.consistent  # vacuously: nothing declared, nothing contradicted
    assert any("nothing to verify" in p for p in check.problems)


def test_reliability_includes_the_named_policy_row():
    corpus = default_external_outcome_corpus()
    named = _gate_policy()
    report = run_reliability(corpus, labeler="hana", extra_policies=[named])
    for split in report.splits:
        names = [p.policy for p in split.policies]
        assert names == ["permissive", "standard", "strict", "precautionary", "research_gate_025"]
    # consistency: the named row equals the tuner's after-numbers for hana
    impact = tune_dry_run(corpus, {"min_data_quality_for_approval": "0.25"}, check_goldens=False)
    for split in report.splits:
        row = next(p for p in split.policies if p.policy == "research_gate_025")
        si = next(
            s for s in impact.stakeholder_impacts if s.target == "hana" and s.split == split.split
        )
        assert row.exact_correct == si.after_correct


def test_reliability_rejects_name_collisions_and_duplicates():
    corpus = default_external_outcome_corpus()
    impostor = NamedPolicy(name="standard", profile=_gate_policy().profile)
    with pytest.raises(ValueError, match="collides with a built-in"):
        run_reliability(corpus, extra_policies=[impostor])
    named = _gate_policy()
    with pytest.raises(ValueError, match="duplicate named policy"):
        run_reliability(corpus, extra_policies=[named, named])


def test_recommendation_can_rank_the_named_policy():
    rec = recommend_policy_for_stakeholder(
        default_external_outcome_corpus(), None, extra_policies=[_gate_policy()]
    )
    assert "research_gate_025" in [p.policy for p in rec.ranked]


def test_cli_calibrate_with_policy_row(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    result = runner.invoke(app, ["calibrate", "--scope", "reliability", "--with-policy", str(path)])
    assert result.exit_code == 0
    assert "research_gate_025" in result.stdout


def test_cli_recommend_policy_with_policy_row(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    result = runner.invoke(app, ["recommend-policy", "--external", "--with-policy", str(path)])
    assert result.exit_code == 0
    assert "research_gate_025" in result.stdout


def test_cli_explain_disagreement_carries_the_name(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    # engine-vs-label under the named policy
    result = runner.invoke(
        app,
        [
            "explain-disagreement",
            "ext-0005",
            "--external",
            "--against",
            "consensus",
            "--policy",
            str(path),
        ],
    )
    assert result.exit_code == 0
    assert "engine[research_gate_025]" in result.output
    # policy-vs-policy where --against is itself a named-policy file
    result = runner.invoke(
        app,
        [
            "explain-disagreement",
            "ext-0007",
            "--external",
            "--against",
            str(path),
            "--policy",
            "standard",
        ],
    )
    assert result.exit_code == 0
    assert "standard = " in result.output
    assert "research_gate_025 = " in result.output


def test_cli_warns_on_tampered_provenance(tmp_path):
    named = _gate_policy()
    named.provenance.changes["min_data_quality_for_approval"] = "0.35 -> 0.30"
    path = tmp_path / "tampered.json"
    save_named_policy(path, named)
    result = runner.invoke(
        app, ["evaluate", str(EXAMPLES / "simple_case.json"), "--policy", str(path)]
    )
    # the profile still runs (it is valid); the lie about its history is loud
    assert result.exit_code == 0
    assert "does NOT match its profile" in result.output
    assert "mismatched change for min_data_quality_for_approval" in result.output


def test_cli_consistent_provenance_is_silent(tmp_path):
    path = tmp_path / "gate.json"
    save_named_policy(path, _gate_policy())
    result = runner.invoke(
        app, ["evaluate", str(EXAMPLES / "simple_case.json"), "--policy", str(path)]
    )
    assert result.exit_code == 0
    assert "does NOT match" not in result.output
