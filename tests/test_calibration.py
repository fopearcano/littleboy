"""Tests for the v0.9 adversarial calibration corpus & golden-file regression."""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from littleboy import ActionCase
from littleboy.calibration import (
    AuditCorpus,
    CorpusEntry,
    default_corpus,
    golden_payload,
    run_corpus,
)
from littleboy.cli import app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
GOLDEN = Path(__file__).resolve().parent / "golden" / "audit_corpus.golden.json"
runner = CliRunner()


def _load(name: str) -> ActionCase:
    return ActionCase.model_validate_json((EXAMPLES / name).read_text())


def test_default_corpus_loads():
    corpus = default_corpus()
    assert corpus.entries
    labels = {e.label for e in corpus.entries}
    assert "adversarial" in labels
    assert "clean" in labels


def test_corpus_runs_clean():
    report = run_corpus(default_corpus())
    assert report.miss_rate == 0.0
    assert report.false_alarm_rate == 0.0
    assert report.n_passed == report.n_cases


def test_clean_cases_raise_no_red_flags():
    report = run_corpus(default_corpus())
    by_id = {d.id: d for d in report.digests}
    for entry in default_corpus().entries:
        if entry.label == "clean":
            assert by_id[entry.id].red_flags == []


def test_adversarial_cases_are_flagged():
    report = run_corpus(default_corpus())
    by_id = {d.id: d for d in report.digests}
    for entry in default_corpus().entries:
        if entry.label == "adversarial":
            assert by_id[entry.id].red_flags, f"{entry.id} raised no red flags"


def test_golden_regression():
    payload = golden_payload(run_corpus(default_corpus()))
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(GOLDEN.read_text())
    assert payload == expected, (
        "calibration drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_a_miss_raises_the_miss_rate():
    # An adversarial entry expecting a flag that a clean case will never raise.
    corpus = AuditCorpus(
        entries=[
            CorpusEntry(
                id="planted_miss",
                label="adversarial",
                case=_load("low_coercion_good_data.json"),
                expect_findings=["AUD-CONSENT-CONTAMINATION"],
            )
        ]
    )
    report = run_corpus(corpus)
    assert report.miss_rate == 1.0
    assert report.outcomes[0].passed is False
    assert "AUD-CONSENT-CONTAMINATION" in report.outcomes[0].missing_expected


def test_a_false_alarm_raises_the_false_alarm_rate():
    # A genuinely adversarial case mislabelled "clean" must register as a false alarm.
    corpus = AuditCorpus(
        entries=[
            CorpusEntry(
                id="planted_false_alarm",
                label="clean",
                case=_load("audit_fake_consent.json"),
            )
        ]
    )
    report = run_corpus(corpus)
    assert report.false_alarm_rate == 1.0
    assert report.outcomes[0].passed is False
    assert report.outcomes[0].false_alarms


def test_cli_calibrate_works():
    result = runner.invoke(app, ["calibrate"])
    assert result.exit_code == 0
    assert "CALIBRATION:" in result.stdout
    assert "miss_rate=" in result.stdout
