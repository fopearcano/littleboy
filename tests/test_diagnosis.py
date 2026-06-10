"""Tests for the v0.20 corpus-level disagreement diagnosis."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from littleboy.calibration import (
    default_external_outcome_corpus,
    diagnose_disagreements,
    diagnosis_golden_payload,
    explain_reliability_disagreements,
    run_reliability,
)
from littleboy.cli import app

DIAGNOSIS_GOLDEN = Path(__file__).resolve().parent / "golden" / "disagreement_diagnosis.golden.json"
runner = CliRunner()


def test_diagnosis_counts_add_up():
    d = diagnose_disagreements(default_external_outcome_corpus(), "hana", policy="standard")
    assert d.n_agree + d.n_disagree == d.n_cases == 40
    assert sum(f.count for f in d.fractions) == d.n_disagree
    assert len(d.case_classifications) == d.n_disagree
    # the fractions are exactly the per-case classification tally
    for fraction in d.fractions:
        assert fraction.count == sum(
            1 for cls in d.case_classifications.values() if cls == fraction.classification
        )


def test_diagnosis_agreement_matches_the_reliability_table():
    corpus = default_external_outcome_corpus()
    d = diagnose_disagreements(corpus, "hana", policy="standard")
    report = run_reliability(corpus, labeler="hana")
    exact_correct = sum(
        p.exact_correct for s in report.splits for p in s.policies if p.policy == "standard"
    )
    # the diagnosis is the same measurement as the reliability table, decomposed
    assert d.n_agree == exact_correct


def test_diagnosis_is_consistent_with_the_explanations():
    corpus = default_external_outcome_corpus()
    d = diagnose_disagreements(corpus, "hana", policy="standard")
    explanations = explain_reliability_disagreements(corpus, "hana", policy="standard")
    assert d.case_classifications == {e.case_id: e.bridge_classification for e in explanations}


def test_recurring_parameters_are_ranked_with_cases():
    d = diagnose_disagreements(default_external_outcome_corpus(), "hana", policy="standard")
    assert d.recurring_parameters
    top = d.recurring_parameters[0]
    assert top.account == "min_data_quality_for_approval"  # the data gate recurs most
    assert top.kind == "parameter"
    assert top.count == len(top.cases) >= 2
    # ranked: counts are non-increasing
    counts = [ra.count for ra in d.recurring_parameters]
    assert counts == sorted(counts, reverse=True)


def test_recurring_facts_are_counted_per_disagreement():
    d = diagnose_disagreements(default_external_outcome_corpus(), "hana", policy="standard")
    assert d.recurring_facts
    for ra in d.recurring_facts:
        assert ra.kind == "fact"
        assert 1 <= ra.count <= d.n_disagree
        assert len(set(ra.cases)) == ra.count  # one count per disagreement, no doubles


def test_tuning_agenda_names_routes_and_review_cases():
    d = diagnose_disagreements(default_external_outcome_corpus(), "hana", policy="standard")
    agenda = "\n".join(d.tuning_agenda)
    assert "min_data_quality_for_approval" in agenda
    assert "establishing" in agenda  # the fact route
    assert "genuine divergence" in agenda  # the review line


def test_wilson_intervals_bracket_the_fractions():
    d = diagnose_disagreements(default_external_outcome_corpus(), None, policy="standard")
    assert d.agreement_ci.low <= d.agreement <= d.agreement_ci.high
    for fraction in d.fractions:
        assert fraction.fraction_ci.low <= fraction.fraction <= fraction.fraction_ci.high


def test_split_restriction():
    corpus = default_external_outcome_corpus()
    holdout = diagnose_disagreements(corpus, "hana", policy="standard", split="holdout")
    assert holdout.split == "holdout"
    assert holdout.n_cases == sum(1 for e in corpus.entries if e.split == "holdout")
    with pytest.raises(ValueError, match="no cases to diagnose"):
        diagnose_disagreements(corpus, "hana", split="nonexistent")


def test_diagnosis_is_deterministic():
    corpus = default_external_outcome_corpus()
    a = diagnosis_golden_payload(diagnose_disagreements(corpus, "hana"))
    b = diagnosis_golden_payload(diagnose_disagreements(corpus, "hana"))
    assert a == b


def test_diagnosis_golden_regression():
    payload = diagnosis_golden_payload(
        diagnose_disagreements(default_external_outcome_corpus(), None, policy="standard")
    )
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        DIAGNOSIS_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(DIAGNOSIS_GOLDEN.read_text())
    assert payload == expected, (
        "disagreement diagnosis drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_diagnose_works():
    result = runner.invoke(app, ["diagnose", "--external", "--against", "hana"])
    assert result.exit_code == 0
    assert "DIAGNOSIS: engine[standard] vs hana" in result.stdout
    assert "disagreement breakdown" in result.stdout
    assert "tuning agenda:" in result.stdout
    assert "inter-labeller ceiling" in result.stdout


def test_cli_diagnose_json_parses():
    result = runner.invoke(app, ["diagnose", "--external", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["target"] == "consensus"
    assert payload["n_cases"] == 40


def test_cli_diagnose_error_paths():
    # a policy name is not a labeller
    result = runner.invoke(app, ["diagnose", "--external", "--against", "strict"])
    assert result.exit_code == 2
    # unknown labeller
    result = runner.invoke(app, ["diagnose", "--external", "--against", "zorro"])
    assert result.exit_code == 2
    # bad split
    result = runner.invoke(app, ["diagnose", "--external", "--split", "weird"])
    assert result.exit_code == 2
