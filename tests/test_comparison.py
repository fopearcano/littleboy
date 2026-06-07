"""Tests for the v0.6 comparison engine."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionComparisonSet,
    ComparisonEngine,
    EvaluationReport,
    PolicyMode,
    Verdict,
)
from littleboy.cli import app
from littleboy.comparison.dominance import PARTIAL, STRICT_A, STRICT_B

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def _load(name: str) -> ActionComparisonSet:
    return ActionComparisonSet.model_validate_json((EXAMPLES / name).read_text())


def _entry(result, option_id):
    return next(e for e in result.ranking if e.option_id == option_id)


# --- 1. the engine evaluates all options -------------------------------------


def test_engine_evaluates_all_options():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    assert set(result.individual_reports) == {"ask", "pressure", "threaten"}
    assert len(result.ranking) == 3


# --- 2. clear low-coercion option ranks first --------------------------------


def test_clear_low_coercion_option_ranks_first():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    assert result.best_option_id == "ask"
    assert _entry(result, "ask").rank == 1


# --- 3. high-coercion option without justification ranks lower ---------------


def test_high_coercion_without_justification_ranks_lower():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    threaten = _entry(result, "threaten")
    assert threaten.verdict == Verdict.NOT_ACCEPTABLE
    assert threaten.is_morally_viable is False
    assert threaten.rank > _entry(result, "ask").rank


# --- 4. feasible less-coercive option dominates coercive options -------------


def test_less_coercive_option_dominates():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    assert "threaten" in result.dominated_options
    assert "ask" in result.non_dominated_options


# --- 5. weak data prevents a stable ranking ----------------------------------


def test_weak_data_prevents_stable_ranking():
    result = ComparisonEngine().compare(_load("comparison_uncertain_data.json"))
    assert result.ranking_stable is False
    assert result.best_option_id is None
    assert result.what_could_change_ranking


# --- 6. irreversible option downgraded under precautionary policy ------------


def test_irreversible_downgraded_under_precautionary():
    result = ComparisonEngine(PolicyMode.PRECAUTIONARY).compare(
        _load("comparison_irreversible_vs_reversible.json")
    )
    assert _entry(result, "reversible").rank < _entry(result, "irreversible").rank


# --- 7. strict and permissive produce different outcomes ---------------------


def test_strict_and_permissive_differ():
    cset = _load("comparison_irreversible_vs_reversible.json")
    permissive = ComparisonEngine(PolicyMode.PERMISSIVE).compare(cset)
    strict = ComparisonEngine(PolicyMode.STRICT).compare(cset)
    # Under permissive a viable best exists; under strict it does not.
    assert permissive.best_option_id is not None
    assert strict.best_option_id is None


# --- 8. linguistic coercion affects ranking when language is central ---------


def test_linguistic_coercion_affects_ranking():
    result = ComparisonEngine().compare(_load("comparison_language_framing_options.json"))
    assert result.best_option_id == "constructive"
    assert _entry(result, "constructive").rank < _entry(result, "manipulative").rank


# --- 9. manipulative consent language downgrades an option -------------------


def test_manipulative_consent_language_downgrades():
    result = ComparisonEngine().compare(_load("comparison_language_framing_options.json"))
    manipulative = _entry(result, "manipulative")
    assert manipulative.is_morally_viable is False
    assert manipulative.linguistic_coercion_score > 0.5


# --- 10. justified emergency coercion can outrank inaction -------------------


def test_justified_emergency_outranks_inaction():
    result = ComparisonEngine().compare(_load("comparison_emergency_options.json"))
    assert result.best_option_id == "restrain"
    assert _entry(result, "restrain").rank < _entry(result, "do_nothing").rank
    assert _entry(result, "restrain").is_morally_viable is True


# --- 11. dominance engine detects strict dominance ---------------------------


def test_dominance_detects_strict():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    relations = {(d.option_a_id, d.option_b_id): d.relation for d in result.dominance_results}
    # 'ask' (a, lower index) strictly dominates the coercive options.
    assert relations[("ask", "threaten")] == STRICT_A
    assert relations[("ask", "pressure")] in (STRICT_A,)


# --- 12. dominance engine detects partial dominance --------------------------


def test_dominance_detects_partial():
    result = ComparisonEngine().compare(_load("comparison_irreversible_vs_reversible.json"))
    relations = [d.relation for d in result.dominance_results]
    assert PARTIAL in relations
    assert STRICT_A not in relations and STRICT_B not in relations


# --- 13. comparison result preserves individual evaluation reports -----------


def test_comparison_preserves_individual_reports():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    assert result.individual_reports
    for report in result.individual_reports.values():
        assert isinstance(report, EvaluationReport)
        assert report.reasoning_trace is not None


# --- 14. CLI `compare` works with an example file ----------------------------


def test_cli_compare_works():
    result = runner.invoke(
        app, ["compare", str(EXAMPLES / "comparison_basic.json"), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["best_option_id"] == "ask"
    assert "ranking" in payload and "individual_reports" in payload

    text_result = runner.invoke(
        app,
        [
            "compare",
            str(EXAMPLES / "comparison_basic.json"),
            "--format",
            "text",
            "--policy",
            "strict",
        ],
    )
    assert text_result.exit_code == 0
    assert "BEST OPTION" in text_result.stdout


# --- 15. text output includes missing data that could change the ranking -----


def test_text_output_includes_missing_data_section():
    result = runner.invoke(
        app, ["compare", str(EXAMPLES / "comparison_uncertain_data.json"), "--format", "text"]
    )
    assert result.exit_code == 0
    assert "Missing data that could change the ranking" in result.stdout


def test_explanation_is_non_rhetorical():
    result = ComparisonEngine().compare(_load("comparison_basic.json"))
    text = result.comparison_explanation.lower()
    assert "under the" in text and "policy" in text
    for banned in ("objectively the best", "solved the ethical", "morally good because the system"):
        assert banned not in text
