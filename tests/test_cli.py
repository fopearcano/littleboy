"""Tests for the command-line interface (brief scenario 11)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy.cli import app

runner = CliRunner()

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_cli_evaluates_an_example_json_file():
    result = runner.invoke(app, ["evaluate", str(EXAMPLES / "low_coercion_good_data.json")])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "ACCEPTABLE"
    assert "axioms_invoked" in payload


def test_cli_text_format_runs():
    result = runner.invoke(
        app, ["evaluate", str(EXAMPLES / "manipulative_language_case.json"), "--format", "text"]
    )
    assert result.exit_code == 0
    assert "VERDICT:" in result.stdout


def test_cli_experiment_command_runs():
    result = runner.invoke(
        app, ["experiment", str(EXAMPLES / "high_coercion_missing_consent.json")]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "recommended_next_questions" in payload
    assert payload["recommended_next_questions"]


def test_cli_reports_malformed_json_gracefully(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json ", encoding="utf-8")
    result = runner.invoke(app, ["evaluate", str(bad)])
    assert result.exit_code == 2
    assert "Invalid JSON" in result.output


def test_cli_reports_invalid_case_gracefully(tmp_path):
    # Valid JSON, but not a valid ActionCase (missing required `title`).
    bad = tmp_path / "case.json"
    bad.write_text(json.dumps({"description": "no title here"}), encoding="utf-8")
    result = runner.invoke(app, ["evaluate", str(bad)])
    assert result.exit_code == 2
    assert "Invalid ActionCase" in result.output
