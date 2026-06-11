"""Tests for v0.26 signed adoptions (detached HMAC over the decision log)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    NamedPolicy,
    PolicyProvenance,
    SigningKey,
    append_decision,
    entry_signature_status,
    read_decision_log,
    save_named_policy,
    sign_entry,
    verify_decision_log,
)
from littleboy.calibration import candidate_profile
from littleboy.cli import app

runner = CliRunner()
_SECRET = "aa" * 32
_OTHER = "bb" * 32


def _named(name: str = "gate") -> NamedPolicy:
    return NamedPolicy(
        name=name,
        profile=candidate_profile("standard", {"min_data_quality_for_approval": "0.25"}),
        provenance=PolicyProvenance(
            base="standard", changes={"min_data_quality_for_approval": "0.35 -> 0.25"}
        ),
    )


def _key(key_id: str = "alice", secret: str = _SECRET) -> SigningKey:
    return SigningKey(key_id=key_id, secret=secret)


def _registry(tmp_path: Path) -> Path:
    save_named_policy(tmp_path / "gate.json", _named())
    return tmp_path


def _trust(directory: Path, *keys: SigningKey) -> None:
    directory.joinpath("trusted_keys.json").write_text(
        json.dumps([{"key_id": k.key_id, "secret": k.secret} for k in keys]), encoding="utf-8"
    )


# --- signing primitives -------------------------------------------------------


def test_unsigned_log_is_unchanged_behaviour(tmp_path):
    d = _registry(tmp_path)
    entry = append_decision(_named(), directory=d, reason="x")
    assert entry.key_id == "" and entry.signature == ""
    assert entry_signature_status(entry, {}) == "unsigned"
    report = verify_decision_log(d)
    assert report.chain_intact and report.n_problems == 0
    assert report.signature_status == ["unsigned"]


def test_signing_does_not_perturb_the_chain(tmp_path):
    # an unsigned and a signed adoption of the same policy chain to the same prev_hash
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    save_named_policy(da / "gate.json", _named())
    save_named_policy(db / "gate.json", _named())
    unsigned = append_decision(_named(), directory=da, reason="x")
    signed = append_decision(_named(), directory=db, reason="x", signing_key=_key())
    # second entries must chain identically (signature is not chain content)
    from littleboy.rules.decisions import entry_hash

    assert entry_hash(unsigned) == entry_hash(signed)


def test_signed_log_is_deterministic(tmp_path):
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    save_named_policy(da / "gate.json", _named())
    save_named_policy(db / "gate.json", _named())
    append_decision(_named(), directory=da, reason="x", signing_key=_key())
    append_decision(_named(), directory=db, reason="x", signing_key=_key())
    assert (da / "decisions.jsonl").read_bytes() == (db / "decisions.jsonl").read_bytes()


def test_signature_status_classification(tmp_path):
    d = _registry(tmp_path)
    entry = append_decision(_named(), directory=d, reason="x", signing_key=_key())
    assert entry_signature_status(entry, {}) == "signed-untrusted"  # no trusted keys
    assert entry_signature_status(entry, {"alice": _SECRET}) == "signed-trusted"
    assert entry_signature_status(entry, {"alice": _OTHER}) == "signed-invalid"


def test_sign_entry_binds_key_id_and_position(tmp_path):
    d = _registry(tmp_path)
    entry = append_decision(_named(), directory=d, reason="x", signing_key=_key())
    # re-signing the same entry reproduces the signature (deterministic HMAC)
    assert sign_entry(entry, _key()) == entry.signature
    # changing the key id invalidates the signature under the original secret
    impostor = entry.model_copy(update={"key_id": "mallory"})
    assert entry_signature_status(impostor, {"mallory": _SECRET}) == "signed-invalid"


# --- verification through the log ---------------------------------------------


def test_trusted_signature_verifies(tmp_path):
    d = _registry(tmp_path)
    append_decision(_named(), directory=d, reason="x", signing_key=_key())
    _trust(d, _key())
    report = verify_decision_log(d)
    assert report.signature_status == ["signed-trusted"]
    assert report.n_problems == 0
    assert report.trusted_keys_found


def test_invalid_signature_is_always_a_problem(tmp_path):
    d = _registry(tmp_path)
    append_decision(_named(), directory=d, reason="x", signing_key=_key())
    _trust(d, _key("alice", _OTHER))  # trusted key id, wrong secret
    report = verify_decision_log(d)
    assert report.signature_status == ["signed-invalid"]
    assert report.n_problems == 1
    assert any("signature is INVALID" in p for p in report.problems)


def test_tampering_a_signed_entry_invalidates_it(tmp_path):
    d = _registry(tmp_path)
    append_decision(_named(), directory=d, reason="honest", signing_key=_key())
    _trust(d, _key())
    lines = (d / "decisions.jsonl").read_text().splitlines()
    obj = json.loads(lines[0])
    obj["reason"] = "a lie added after signing"
    (d / "decisions.jsonl").write_text(json.dumps(obj) + "\n")
    report = verify_decision_log(d)
    assert report.signature_status == ["signed-invalid"]


def test_require_signatures_gate(tmp_path):
    d = _registry(tmp_path)
    append_decision(_named(), directory=d, reason="x")  # unsigned
    # default: unsigned is fine
    assert verify_decision_log(d).n_problems == 0
    # strict: unsigned now fails
    report = verify_decision_log(d, require_signatures=True)
    assert report.n_problems == 1
    assert any("is unsigned" in p for p in report.problems)


def test_require_signatures_rejects_untrusted(tmp_path):
    d = _registry(tmp_path)
    append_decision(_named(), directory=d, reason="x", signing_key=_key())
    # signed but no trusted-keys file -> untrusted -> fails under --require-signatures
    report = verify_decision_log(d, require_signatures=True)
    assert any("untrusted key 'alice'" in p for p in report.problems)


def test_external_trusted_keys_path(tmp_path):
    d = _registry(tmp_path)
    append_decision(_named(), directory=d, reason="x", signing_key=_key())
    keys = tmp_path / "secrets" / "trusted.json"
    keys.parent.mkdir()
    keys.write_text(json.dumps([{"key_id": "alice", "secret": _SECRET}]), encoding="utf-8")
    report = verify_decision_log(d, trusted_keys=keys)
    assert report.signature_status == ["signed-trusted"]


def test_signature_survives_a_clean_chain(tmp_path):
    # two signed adoptions: chain intact, both trusted
    d = _registry(tmp_path)
    save_named_policy(d / "strict.json", _named("strict_research"))
    append_decision(_named(), directory=d, reason="one", signing_key=_key())
    append_decision(_named("strict_research"), directory=d, reason="two", signing_key=_key("bob"))
    _trust(d, _key("alice"), _key("bob"))
    report = verify_decision_log(d)
    assert report.chain_intact
    assert report.signature_status == ["signed-trusted", "signed-trusted"]


# --- the CLI ------------------------------------------------------------------


def test_cli_adopt_sign_and_verify(tmp_path):
    d = _registry(tmp_path)
    (tmp_path / "alice.key").write_text(json.dumps({"key_id": "alice", "secret": _SECRET}))
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    result = runner.invoke(
        app,
        ["adopt", "gate", "--because", "x", "--sign-with", str(tmp_path / "alice.key")],
        env=env,
    )
    assert result.exit_code == 0
    assert "signed by 'alice'" in result.stdout
    assert read_decision_log(d)[0].signature  # actually signed

    # untrusted until we trust the key
    result = runner.invoke(app, ["decisions"], env=env)
    assert "signed-untrusted: alice" in result.stdout
    _trust(d, _key())
    result = runner.invoke(app, ["decisions", "--verify"], env=env)
    assert result.exit_code == 0
    assert "signed-trusted: alice" in result.stdout


def test_cli_decisions_require_signatures(tmp_path):
    d = _registry(tmp_path)
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    runner.invoke(app, ["adopt", "gate", "--because", "x"], env=env)  # unsigned
    result = runner.invoke(app, ["decisions", "--verify"], env=env)
    assert result.exit_code == 0  # unsigned is fine by default
    result = runner.invoke(app, ["decisions", "--verify", "--require-signatures"], env=env)
    assert result.exit_code == 1
    assert "VERIFY FAILED" in result.output


def test_cli_decisions_flags_tamper_in_ci(tmp_path):
    d = _registry(tmp_path)
    (tmp_path / "alice.key").write_text(json.dumps({"key_id": "alice", "secret": _SECRET}))
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    runner.invoke(
        app,
        ["adopt", "gate", "--because", "x", "--sign-with", str(tmp_path / "alice.key")],
        env=env,
    )
    _trust(d, _key())
    # tamper the signed line; --verify must fail on the invalid signature
    lines = (d / "decisions.jsonl").read_text().splitlines()
    obj = json.loads(lines[0])
    obj["reason"] = "tampered"
    (d / "decisions.jsonl").write_text(json.dumps(obj) + "\n")
    result = runner.invoke(app, ["decisions", "--verify"], env=env)
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_cli_adopt_rejects_a_bad_keyfile(tmp_path):
    d = _registry(tmp_path)
    (tmp_path / "bad.key").write_text("{not json")
    env = {"LITTLEBOY_POLICY_DIR": str(d)}
    result = runner.invoke(
        app, ["adopt", "gate", "--because", "x", "--sign-with", str(tmp_path / "bad.key")], env=env
    )
    assert result.exit_code == 2
    assert "Invalid signing key" in result.output
