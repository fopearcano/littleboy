"""Tests for the v0.25 policy-adoption decision log."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from littleboy import (
    NamedPolicy,
    PolicyProvenance,
    append_decision,
    current_policy,
    profile_hash,
    read_decision_log,
    save_named_policy,
    verify_decision_log,
)
from littleboy.calibration import candidate_profile
from littleboy.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def _gate(name: str = "research_gate_025") -> NamedPolicy:
    return NamedPolicy(
        name=name,
        profile=candidate_profile("standard", {"min_data_quality_for_approval": "0.25"}),
        provenance=PolicyProvenance(
            base="standard",
            changes={"min_data_quality_for_approval": "0.35 -> 0.25"},
            description="data gate lowered after the v0.20 diagnosis",
        ),
    )


def _strict() -> NamedPolicy:
    return NamedPolicy(
        name="strict_research",
        profile=candidate_profile("strict", {}),
        provenance=PolicyProvenance(base="strict", changes={}),
    )


def _registry(tmp_path: Path) -> Path:
    save_named_policy(tmp_path / "gate.json", _gate())
    save_named_policy(tmp_path / "strict.json", _strict())
    return tmp_path


# --- the log itself -----------------------------------------------------------


def test_profile_hash_is_stable_and_value_only():
    a = candidate_profile("standard", {"min_data_quality_for_approval": "0.25"})
    b = candidate_profile("standard", {"min_data_quality_for_approval": "0.25"})
    assert profile_hash(a) == profile_hash(b)
    c = candidate_profile("standard", {"min_data_quality_for_approval": "0.26"})
    assert profile_hash(a) != profile_hash(c)


def test_append_and_read_chains_entries(tmp_path):
    d = _registry(tmp_path)
    e0 = append_decision(_gate(), directory=d, reason="lower the gate")
    e1 = append_decision(_strict(), directory=d, reason="switch to strict for the audit")
    log = read_decision_log(d)
    assert [e.seq for e in log] == [0, 1]
    assert e0.replaced == "" and e1.replaced == "research_gate_025"
    assert e0.prev_hash == "0" * 64  # genesis
    assert current_policy(d).policy_name == "strict_research"


def test_log_is_clock_free_and_deterministic(tmp_path):
    d1, d2 = tmp_path / "a", tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    save_named_policy(d1 / "gate.json", _gate())
    save_named_policy(d2 / "gate.json", _gate())
    impact = {"base_policy": "standard", "n_cases": 40, "n_flips": 3, "net_deltas": {"fay": -0.075}}
    append_decision(_gate(), directory=d1, reason="x", impact=impact)
    append_decision(_gate(), directory=d2, reason="x", impact=impact)
    # identical bytes -> no timestamps, no nondeterminism
    assert (d1 / "decisions.jsonl").read_bytes() == (d2 / "decisions.jsonl").read_bytes()


def test_impact_digest_is_small_and_stable(tmp_path):
    d = _registry(tmp_path)
    impact = {
        "base_policy": "standard",
        "n_cases": 40,
        "n_flips": 3,
        "flip_summary": {"INSUFFICIENT_DATA -> NOT_ACCEPTABLE": 3},
        "net_deltas": {"fay": -0.075, "hana": 0.05},
        "flips": [{"case_id": "ext-0004"}],  # the noisy per-case list must be dropped
    }
    entry = append_decision(_gate(), directory=d, reason="x", impact=impact)
    assert "flips" not in entry.impact_summary
    assert entry.impact_summary["n_flips"] == 3
    assert entry.impact_summary["net_deltas"] == {"fay": -0.075, "hana": 0.05}


def test_clean_log_verifies(tmp_path):
    d = _registry(tmp_path)
    append_decision(_gate(), directory=d, reason="x")
    append_decision(_strict(), directory=d, reason="y")
    report = verify_decision_log(d)
    assert report.chain_intact and report.n_problems == 0
    assert report.current == "strict_research"


def test_missing_log_is_honest(tmp_path):
    report = verify_decision_log(tmp_path)
    assert not report.exists and report.n_entries == 0


# --- the integrity guarantees -------------------------------------------------


def test_refuses_tampered_policy_unless_forced(tmp_path):
    d = tmp_path
    tampered = _gate()
    tampered.provenance.changes["min_data_quality_for_approval"] = "0.35 -> 0.30"  # a lie
    save_named_policy(d / "tampered.json", tampered)
    with pytest.raises(ValueError, match="refusing to adopt"):
        append_decision(tampered, directory=d, reason="x")
    entry = append_decision(tampered, directory=d, reason="x", force=True)
    assert entry.forced
    assert entry.flags_at_adoption  # the flags are recorded, never silent


def test_content_drift_is_detected(tmp_path):
    d = _registry(tmp_path)
    append_decision(_gate(), directory=d, reason="x")
    # silently swap the registry file AFTER adoption
    swapped = NamedPolicy(
        name="research_gate_025",
        profile=candidate_profile("standard", {"min_data_quality_for_approval": "0.10"}),
        provenance=PolicyProvenance(
            base="standard", changes={"min_data_quality_for_approval": "0.35 -> 0.10"}
        ),
    )
    save_named_policy(d / "gate.json", swapped)
    report = verify_decision_log(d)
    assert report.n_problems >= 1
    assert any("DRIFTED" in p for p in report.problems)


def test_missing_adopted_file_is_detected(tmp_path):
    d = _registry(tmp_path)
    append_decision(_gate(), directory=d, reason="x")
    (d / "gate.json").unlink()
    report = verify_decision_log(d)
    assert any("not in the registry" in p for p in report.problems)


def test_chain_break_on_edited_entry(tmp_path):
    d = _registry(tmp_path)
    append_decision(_gate(), directory=d, reason="honest")
    append_decision(_strict(), directory=d, reason="y")
    lines = (d / "decisions.jsonl").read_text().splitlines()
    obj = json.loads(lines[0])
    obj["reason"] = "a lie inserted after the fact"
    lines[0] = json.dumps(obj)
    (d / "decisions.jsonl").write_text("\n".join(lines) + "\n")
    report = verify_decision_log(d)
    assert not report.chain_intact
    assert any("broken chain" in p for p in report.problems)


def test_chain_break_on_removed_entry(tmp_path):
    d = _registry(tmp_path)
    append_decision(_gate(), directory=d, reason="first")
    append_decision(_strict(), directory=d, reason="second")
    lines = (d / "decisions.jsonl").read_text().splitlines()
    (d / "decisions.jsonl").write_text(lines[1] + "\n")  # drop entry #0
    report = verify_decision_log(d)
    assert not report.chain_intact  # seq 1 where 0 expected, and genesis mismatch


# --- the CLI ------------------------------------------------------------------


def test_cli_adopt_and_decisions(tmp_path):
    d = _registry(tmp_path)
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    result = runner.invoke(
        app, ["adopt", "research_gate_025", "--because", "lower the gate"], env=env
    )
    assert result.exit_code == 0
    assert "adopted 'research_gate_025'" in result.stdout
    result = runner.invoke(app, ["adopt", "strict_research", "--because", "audit"], env=env)
    assert result.exit_code == 0
    assert "replaced 'research_gate_025'" in result.stdout

    result = runner.invoke(app, ["decisions"], env=env)
    assert result.exit_code == 0
    assert "current: strict_research" in result.stdout
    assert "reason: lower the gate" in result.stdout
    assert "#0 research_gate_025" in result.stdout


def test_cli_policies_shows_the_adopted_policy(tmp_path):
    d = _registry(tmp_path)
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    runner.invoke(app, ["adopt", "research_gate_025", "--because", "x"], env=env)
    result = runner.invoke(app, ["policies"], env=env)
    assert result.exit_code == 0
    assert "adopted: research_gate_025" in result.stdout


def test_cli_adopt_attaches_the_tuner_impact(tmp_path):
    out = tmp_path / "gate.json"
    # tune --save writes gate.json + gate.impact.json; adopt should attach the latter
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
        ],
    )
    assert result.exit_code == 0
    result = runner.invoke(app, ["adopt", str(out), "--because", "x", "--registry", str(tmp_path)])
    assert result.exit_code == 0
    entry = read_decision_log(tmp_path)[-1]
    assert entry.impact_summary.get("n_flips") == 3


def test_cli_adopt_refuses_flagged_without_force(tmp_path):
    tampered = _gate()
    tampered.provenance.changes["min_data_quality_for_approval"] = "0.35 -> 0.30"
    save_named_policy(tmp_path / "tampered.json", tampered)
    env = {"LITTLEBOY_POLICY_DIR": str(tmp_path)}
    result = runner.invoke(app, ["adopt", "research_gate_025", "--because", "x"], env=env)
    assert result.exit_code == 2
    assert "refusing to adopt" in result.output
    # --force adopts and records it
    result = runner.invoke(
        app, ["adopt", "research_gate_025", "--because", "x", "--force"], env=env
    )
    assert result.exit_code == 0
    assert "FORCED" in result.stdout
    assert read_decision_log(tmp_path)[-1].forced


def test_cli_decisions_verify_for_ci(tmp_path):
    d = _registry(tmp_path)
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    runner.invoke(app, ["adopt", "research_gate_025", "--because", "x"], env=env)
    result = runner.invoke(app, ["decisions", "--verify"], env=env)
    assert result.exit_code == 0
    # drift the adopted file -> CI gate fails
    save_named_policy(
        d / "gate.json",
        NamedPolicy(
            name="research_gate_025",
            profile=candidate_profile("standard", {"min_data_quality_for_approval": "0.10"}),
            provenance=PolicyProvenance(
                base="standard", changes={"min_data_quality_for_approval": "0.35 -> 0.10"}
            ),
        ),
    )
    result = runner.invoke(app, ["decisions", "--verify"], env=env)
    assert result.exit_code == 1
    assert "VERIFY FAILED" in result.output
