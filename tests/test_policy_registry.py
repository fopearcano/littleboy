"""Tests for the v0.24 policy registry."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from littleboy import (
    NamedPolicy,
    PolicyProvenance,
    lookup_registered_policy,
    resolve_policy_ref,
    save_named_policy,
    scan_policy_registry,
)
from littleboy.calibration import candidate_profile
from littleboy.cli import app
from littleboy.core.enums import PolicyMode
from littleboy.rules.policy import registry_dir

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
FIXTURE_REGISTRY = Path(__file__).resolve().parent / "fixtures" / "policies"
REGISTRY_GOLDEN = Path(__file__).resolve().parent / "golden" / "policy_registry.golden.json"
runner = CliRunner()


def _gate_profile():
    return candidate_profile("standard", {"min_data_quality_for_approval": "0.25"})


# --- scanning -----------------------------------------------------------------


def test_scan_missing_directory_is_honest():
    reg = scan_policy_registry("no/such/directory")
    assert not reg.exists
    assert reg.n_policies == 0
    assert any("no registry directory" in note for note in reg.notes)


def test_scan_the_fixture_registry():
    reg = scan_policy_registry(FIXTURE_REGISTRY)
    assert reg.exists
    # 4 policies: broken, gate025, noprov, tampered -- the .impact.json companion excluded
    assert reg.n_policies == 4
    assert [entry.file for entry in reg.entries] == [
        "broken.json",
        "gate025.json",
        "noprov.json",
        "tampered.json",
    ]
    by_file = {entry.file: entry for entry in reg.entries}
    assert not by_file["broken.json"].loadable and by_file["broken.json"].flagged
    good = by_file["gate025.json"]
    assert good.name == "research_gate_025" and good.consistent and not good.flagged
    assert good.base == "standard" and good.changes
    bare = by_file["noprov.json"]
    assert not bare.has_provenance and not bare.flagged  # less history, not tampering
    bad = by_file["tampered.json"]
    assert bad.has_provenance and not bad.consistent and bad.flagged
    assert any("mismatched change" in p for p in bad.problems)
    assert reg.n_flagged == 2


def test_scan_flags_duplicates_and_builtin_collisions(tmp_path):
    profile = _gate_profile()
    save_named_policy(tmp_path / "a.json", NamedPolicy(name="twin", profile=profile))
    save_named_policy(tmp_path / "b.json", NamedPolicy(name="twin", profile=profile))
    save_named_policy(tmp_path / "c.json", NamedPolicy(name="standard", profile=profile))
    reg = scan_policy_registry(tmp_path)
    assert reg.duplicate_names == ["twin"]
    by_file = {entry.file: entry for entry in reg.entries}
    assert by_file["a.json"].flagged and by_file["b.json"].flagged
    assert by_file["c.json"].flagged
    assert any("collides with a built-in" in p for p in by_file["c.json"].problems)
    assert reg.n_flagged == 3


def test_registry_dir_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("LITTLEBOY_POLICY_DIR", raising=False)
    assert registry_dir(None) == Path("policies")
    monkeypatch.setenv("LITTLEBOY_POLICY_DIR", str(tmp_path))
    assert registry_dir(None) == tmp_path
    assert registry_dir("explicit") == Path("explicit")  # override beats the env var


def test_scan_is_deterministic_and_golden_pinned():
    a = scan_policy_registry(FIXTURE_REGISTRY).model_dump(mode="json")
    b = scan_policy_registry(FIXTURE_REGISTRY).model_dump(mode="json")
    assert a == b
    a["directory"] = "<fixture>"  # the absolute path is machine-specific
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        REGISTRY_GOLDEN.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(REGISTRY_GOLDEN.read_text())
    assert a == expected, (
        "the registry scan drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


# --- lookup & resolution --------------------------------------------------------


def test_lookup_by_name():
    named = lookup_registered_policy("research_gate_025", directory=FIXTURE_REGISTRY)
    assert named is not None
    assert named.profile.min_data_quality_for_approval == 0.25
    assert lookup_registered_policy("no_such_name", directory=FIXTURE_REGISTRY) is None


def test_lookup_rejects_duplicate_names(tmp_path):
    profile = _gate_profile()
    save_named_policy(tmp_path / "a.json", NamedPolicy(name="twin", profile=profile))
    save_named_policy(tmp_path / "b.json", NamedPolicy(name="twin", profile=profile))
    with pytest.raises(ValueError, match="ambiguous: defined by a.json, b.json"):
        lookup_registered_policy("twin", directory=tmp_path)


def test_resolve_policy_ref_prefers_builtins_then_registry_then_files(tmp_path):
    # a registry policy named 'standard' never shadows the built-in
    save_named_policy(
        tmp_path / "impostor.json", NamedPolicy(name="standard", profile=_gate_profile())
    )
    policy, label = resolve_policy_ref("standard", registry=tmp_path)
    assert policy == PolicyMode.STANDARD and label == ""
    # a registered name resolves with its name as the label
    profile, label = resolve_policy_ref("research_gate_025", registry=FIXTURE_REGISTRY)
    assert label == "research_gate_025"
    assert profile.min_data_quality_for_approval == 0.25


def test_resolve_policy_ref_rejects_name_vs_file_ambiguity(tmp_path, monkeypatch):
    # a registered policy whose name equals an existing file path
    save_named_policy(
        tmp_path / "reg.json", NamedPolicy(name="collider.json", profile=_gate_profile())
    )
    monkeypatch.chdir(tmp_path)
    save_named_policy(Path("collider.json"), NamedPolicy(name="other", profile=_gate_profile()))
    with pytest.raises(ValueError, match="ambiguous policy reference"):
        resolve_policy_ref("collider.json", registry=tmp_path)


# --- CLI -------------------------------------------------------------------------


def test_cli_policies_lists_and_explains():
    result = runner.invoke(app, ["policies", "--registry", str(FIXTURE_REGISTRY)])
    assert result.exit_code == 0
    assert "POLICY REGISTRY" in result.stdout
    assert "4 policies, 2 flagged" in result.stdout
    assert "research_gate_025" in result.stdout
    assert "UNREADABLE" in result.stdout
    assert "mismatched change" in result.stdout


def test_cli_policies_json_parses():
    result = runner.invoke(
        app, ["policies", "--registry", str(FIXTURE_REGISTRY), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["n_policies"] == 4
    assert payload["n_flagged"] == 2


def test_cli_policies_verify_for_ci(tmp_path):
    # flagged entries -> exit 1
    result = runner.invoke(app, ["policies", "--registry", str(FIXTURE_REGISTRY), "--verify"])
    assert result.exit_code == 1
    assert "VERIFY FAILED" in result.output
    # a clean registry -> exit 0
    save_named_policy(
        tmp_path / "gate.json",
        NamedPolicy(
            name="research_gate_025",
            profile=_gate_profile(),
            provenance=PolicyProvenance(
                base="standard",
                changes={"min_data_quality_for_approval": "0.35 -> 0.25"},
            ),
        ),
    )
    result = runner.invoke(app, ["policies", "--registry", str(tmp_path), "--verify"])
    assert result.exit_code == 0


def test_cli_resolves_registered_names_via_env():
    env = {"LITTLEBOY_POLICY_DIR": str(FIXTURE_REGISTRY)}
    result = runner.invoke(
        app,
        ["evaluate", str(EXAMPLES / "simple_case.json"), "--policy", "research_gate_025"],
        env=env,
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["policy_label"] == "research_gate_025"
    # tampered registered policies warn on use, exactly like files
    result = runner.invoke(
        app,
        ["evaluate", str(EXAMPLES / "simple_case.json"), "--policy", "suspicious_gate"],
        env=env,
    )
    assert result.exit_code == 0
    assert "does NOT match its profile" in result.output


def test_cli_with_policy_accepts_registered_names():
    env = {"LITTLEBOY_POLICY_DIR": str(FIXTURE_REGISTRY)}
    result = runner.invoke(
        app,
        ["recommend-policy", "--external", "--with-policy", "research_gate_025"],
        env=env,
    )
    assert result.exit_code == 0
    assert "research_gate_025" in result.stdout


def test_cli_against_accepts_registered_names_and_rejects_labeler_clash(tmp_path):
    env = {"LITTLEBOY_POLICY_DIR": str(FIXTURE_REGISTRY)}
    result = runner.invoke(
        app,
        [
            "explain-disagreement",
            "ext-0007",
            "--external",
            "--against",
            "research_gate_025",
        ],
        env=env,
    )
    assert result.exit_code == 0
    assert "research_gate_025 = " in result.output
    # a registered policy named like a labeller is ambiguous for --against
    save_named_policy(tmp_path / "h.json", NamedPolicy(name="hana", profile=_gate_profile()))
    result = runner.invoke(
        app,
        ["explain-disagreement", "ext-0007", "--external", "--against", "hana"],
        env={"LITTLEBOY_POLICY_DIR": str(tmp_path)},
    )
    assert result.exit_code == 2
    assert "Ambiguous --against" in result.output
