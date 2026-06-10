"""Tests for the disagreement-explanation layer (v0.18) and fact accounts (v0.19)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from littleboy import ActionCase
from littleboy.calibration import (
    default_external_outcome_corpus,
    explain_label_disagreement,
    explain_policy_disagreement,
    explain_reliability_disagreements,
    explanation_golden_payload,
    minimal_fact_accounts,
    minimal_policy_accounts,
    run_reliability,
)
from littleboy.cli import app
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.deliberation.voi import build_probe_specs
from littleboy.rules.policy import DEFAULT_PROFILES, PolicyMode

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
EXPLANATION_GOLDEN = (
    Path(__file__).resolve().parent / "golden" / "disagreement_explanation.golden.json"
)
runner = CliRunner()


def _case(name: str) -> ActionCase:
    return ActionCase.model_validate_json((EXAMPLES / name).read_text())


def _entry(corpus, case_id: str):
    return next(e for e in corpus.entries if e.id == case_id)


# --- policy-vs-policy --------------------------------------------------------


def test_policy_vs_policy_explains_the_flip():
    exp = explain_policy_disagreement(
        _case("policy_permissive_case.json"), "standard", "permissive", case_id="permissive_case"
    )
    assert not exp.agree
    assert exp.kind == "policy-vs-policy"
    # the single coercion ceiling accounts for the whole divergence, verified
    assert exp.minimal_parameter_accounts == [["max_coercion_for_acceptable"]]
    assert any(f.threshold == "max_coercion_for_acceptable" for f in exp.threshold_flips)
    # the mechanism is visible in the rule deltas (the coercion blocker releases)
    delta_ids = {d.rule_id for d in exp.trace_deltas}
    assert "LB-R002" in delta_ids
    blocker_delta = next(d for d in exp.trace_deltas if d.rule_id == "LB-R002")
    assert blocker_delta.blocker_a and not blocker_delta.blocker_b


def test_minimal_account_actually_flips_and_is_minimal():
    case = _case("policy_permissive_case.json")
    profile_a = DEFAULT_PROFILES[PolicyMode.STANDARD]
    profile_b = DEFAULT_PROFILES[PolicyMode.PERMISSIVE]
    verdict_b = EthicalEvaluator(profile_b).evaluate(case).verdict
    accounts = minimal_policy_accounts(case, profile_a, profile_b)
    assert accounts
    sizes = {len(a) for a in accounts}
    assert len(sizes) == 1  # all returned accounts share the (minimal) size
    for account in accounts:
        hybrid = profile_a.model_copy(update={f: getattr(profile_b, f) for f in account})
        assert EthicalEvaluator(hybrid).evaluate(case).verdict == verdict_b


def test_policy_agreement_is_reported_not_fabricated():
    exp = explain_policy_disagreement(_case("low_coercion_good_data.json"), "standard", "standard")
    assert exp.agree
    assert exp.minimal_parameter_accounts == []
    assert any("no disagreement" in note for note in exp.notes)


def test_corpus_case_data_gate_account():
    entry = _entry(default_external_outcome_corpus(), "ext-0007")
    exp = explain_policy_disagreement(entry.case, "standard", "permissive", case_id=entry.id)
    # standard declines on the data gate; permissive judges -- the gate is the account
    assert ["min_data_quality_for_approval"] in exp.minimal_parameter_accounts


# --- engine-vs-label ---------------------------------------------------------


def test_label_disagreement_with_exact_bridge():
    entry = _entry(default_external_outcome_corpus(), "ext-0007")
    exp = explain_label_disagreement(entry, None, policy="standard")
    assert not exp.agree
    assert exp.kind == "engine-vs-label"
    assert "permissive" in exp.agreeing_policies_exact
    assert exp.bridge_policy == "permissive"
    assert ["min_data_quality_for_approval"] in exp.minimal_parameter_accounts
    assert any("LB-R004" in line for line in exp.engine_decisive)  # the data gate, named


def test_label_disagreement_within_disposition():
    entry = _entry(default_external_outcome_corpus(), "ext-0001")
    exp = explain_label_disagreement(entry, None, policy="standard")
    assert not exp.agree
    assert exp.disposition_a == exp.disposition_b  # both permissible: degree, not kind
    assert exp.bridge_policy is None
    assert any("within-disposition" in note for note in exp.notes)


def test_label_disagreement_with_no_builtin_account():
    entry = _entry(default_external_outcome_corpus(), "ext-0005")
    exp = explain_label_disagreement(entry, None, policy="standard")
    assert not exp.agree
    assert exp.bridge_policy is None
    assert exp.minimal_parameter_accounts == []
    assert any("not a threshold question" in note for note in exp.notes)


def test_label_agreement_short_circuits():
    corpus = default_external_outcome_corpus()
    evaluator = EthicalEvaluator(PolicyMode.STANDARD)
    entry = next(e for e in corpus.entries if evaluator.evaluate(e.case).verdict == e.human_verdict)
    exp = explain_label_disagreement(entry, None, policy="standard")
    assert exp.agree
    assert exp.minimal_parameter_accounts == []
    assert any("no disagreement" in note for note in exp.notes)


def test_unknown_labeler_raises():
    entry = _entry(default_external_outcome_corpus(), "ext-0001")
    with pytest.raises(ValueError, match="no label by 'zorro'"):
        explain_label_disagreement(entry, "zorro")


def test_bulk_explanations_match_the_reliability_disagreements():
    corpus = default_external_outcome_corpus()
    explanations = explain_reliability_disagreements(corpus, "hana", policy="standard")
    report = run_reliability(corpus, labeler="hana")
    listed = sum(
        len(p.disagreements) for s in report.splits for p in s.policies if p.policy == "standard"
    )
    # one inspectable explanation per opaque disagreement string, no more, no fewer
    assert len(explanations) == listed
    assert all(not e.agree for e in explanations)


# --- determinism, golden, CLI ------------------------------------------------


def test_explanations_are_deterministic():
    entry = _entry(default_external_outcome_corpus(), "ext-0007")
    a = explanation_golden_payload(explain_label_disagreement(entry, None))
    b = explanation_golden_payload(explain_label_disagreement(entry, None))
    assert a == b


def test_explanation_golden_regression():
    payload = explanation_golden_payload(
        explain_policy_disagreement(
            _case("policy_permissive_case.json"),
            "standard",
            "permissive",
            case_id="policy_permissive_case",
        )
    )
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        EXPLANATION_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(EXPLANATION_GOLDEN.read_text())
    assert payload == expected, (
        "disagreement explanation drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_explain_label_disagreement_works():
    result = runner.invoke(
        app, ["explain-disagreement", "ext-0007", "--external", "--against", "consensus"]
    )
    assert result.exit_code == 0
    assert "DISAGREEMENT ext-0007" in result.stdout
    assert "bridge policy: permissive" in result.stdout
    assert "minimal parameter account" in result.stdout


def test_cli_explain_policy_disagreement_on_a_path():
    result = runner.invoke(
        app,
        [
            "explain-disagreement",
            str(EXAMPLES / "policy_permissive_case.json"),
            "--against",
            "permissive",
        ],
    )
    assert result.exit_code == 0
    assert "DISAGREEMENT" in result.stdout
    assert "max_coercion_for_acceptable" in result.stdout


def test_cli_explain_all_works():
    result = runner.invoke(
        app, ["explain-disagreement", "--all", "--external", "--against", "hana"]
    )
    assert result.exit_code == 0
    assert "disagreement(s): engine[standard] vs hana" in result.stdout


def test_cli_explain_error_paths():
    # unknown labeler
    result = runner.invoke(
        app, ["explain-disagreement", "ext-0001", "--external", "--against", "zorro"]
    )
    assert result.exit_code == 2
    # --all needs a labeler, not a policy
    result = runner.invoke(
        app, ["explain-disagreement", "--all", "--external", "--against", "strict"]
    )
    assert result.exit_code == 2
    # no case and no --all
    result = runner.invoke(app, ["explain-disagreement", "--against", "consensus"])
    assert result.exit_code == 2


# --- fact accounts + unified classification (v0.19) ---------------------------


def test_fact_account_reaches_the_label_exactly():
    # ext-0034: consent is UNKNOWN; the panel judged it suspicious. Resolving the
    # unknown to REFUSED makes the engine produce the label's verdict exactly.
    entry = _entry(default_external_outcome_corpus(), "ext-0034")
    exp = explain_label_disagreement(entry, None, policy="standard")
    assert exp.bridge_classification == "fact-bridgeable"
    assert ["consent = REFUSED"] in exp.minimal_fact_accounts
    assert any("fact route" in note for note in exp.notes)


def test_fact_account_is_verified_via_the_probe_api():
    # rebuild the named resolution from the public probe API, apply it, and confirm
    # the engine actually lands on the label's verdict -- nothing is asserted on faith
    entry = _entry(default_external_outcome_corpus(), "ext-0034")
    exp = explain_label_disagreement(entry, None, policy="standard")
    account = exp.minimal_fact_accounts[0]
    case = entry.case
    specs = build_probe_specs(case)
    for label in account:
        transform = next(t for spec in specs for lbl, t in spec.resolutions if lbl == label)
        case = transform(case)
    verdict = EthicalEvaluator(PolicyMode.STANDARD).evaluate(case).verdict
    assert verdict == exp.verdict_b


def test_fact_accounts_empty_on_agreement_and_without_probes():
    corpus = default_external_outcome_corpus()
    evaluator = EthicalEvaluator(PolicyMode.STANDARD)
    agreeing = next(
        e for e in corpus.entries if evaluator.evaluate(e.case).verdict == e.human_verdict
    )
    assert minimal_fact_accounts(agreeing.case, "standard", agreeing.human_verdict) == []


def test_both_routes_unified_on_a_real_case():
    # policy_strict_borderline vs cleo: EITHER treat unknown consent as a blocker
    # (policy route) OR learn that consent was refused (fact route)
    from littleboy.calibration import default_independent_outcome_corpus

    entry = _entry(default_independent_outcome_corpus(), "policy_strict_borderline")
    exp = explain_label_disagreement(entry, "cleo", policy="standard")
    assert exp.bridge_classification == "both"
    assert ["unknown_consent_is_blocker"] in exp.minimal_parameter_accounts
    assert ["consent = REFUSED"] in exp.minimal_fact_accounts
    assert any("two routes to agreement" in note for note in exp.notes)


def test_classification_is_consistent_with_the_accounts():
    corpus = default_external_outcome_corpus()
    for exp in explain_reliability_disagreements(corpus, "hana", policy="standard"):
        policy_route = bool(exp.agreeing_policies_exact)
        fact_route = bool(exp.minimal_fact_accounts)
        expected = {
            (True, True): "both",
            (True, False): "policy-bridgeable",
            (False, True): "fact-bridgeable",
            (False, False): "neither",
        }[(policy_route, fact_route)]
        assert exp.bridge_classification == expected


def test_classification_covers_multiple_kinds():
    corpus = default_external_outcome_corpus()
    kinds = {
        e.bridge_classification
        for e in explain_reliability_disagreements(corpus, "hana", policy="standard")
    }
    assert kinds <= {"both", "policy-bridgeable", "fact-bridgeable", "neither"}
    assert {"fact-bridgeable", "policy-bridgeable", "neither"} <= kinds


def test_agreeing_explanation_has_no_classification():
    corpus = default_external_outcome_corpus()
    evaluator = EthicalEvaluator(PolicyMode.STANDARD)
    entry = next(e for e in corpus.entries if evaluator.evaluate(e.case).verdict == e.human_verdict)
    exp = explain_label_disagreement(entry, None, policy="standard")
    assert exp.bridge_classification == ""
    assert exp.minimal_fact_accounts == []


def test_policy_vs_policy_has_no_fact_machinery():
    exp = explain_policy_disagreement(
        _case("policy_permissive_case.json"), "standard", "permissive"
    )
    assert exp.bridge_classification == ""
    assert exp.minimal_fact_accounts == []


def test_cli_shows_fact_account_and_classification():
    result = runner.invoke(
        app,
        [
            "explain-disagreement",
            "policy_strict_borderline",
            "--independent",
            "--against",
            "cleo",
        ],
    )
    assert result.exit_code == 0
    assert "minimal fact account" in result.stdout
    assert "consent = REFUSED" in result.stdout
    assert "classification: both" in result.stdout


def test_cli_all_prints_classification_tally():
    result = runner.invoke(
        app, ["explain-disagreement", "--all", "--external", "--against", "hana"]
    )
    assert result.exit_code == 0
    assert "classification tally:" in result.stdout
    assert "fact-bridgeable" in result.stdout
