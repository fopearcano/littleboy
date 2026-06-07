"""Tests for the v0.9 adversarial calibration corpus & golden-file regression."""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from littleboy import ActionCase
from littleboy.calibration import (
    AuditCorpus,
    ConfidenceInterval,
    CorpusEntry,
    LayerExpectation,
    ScoringCorpus,
    ScoringCorpusEntry,
    default_corpus,
    default_generated_scoring_corpus,
    default_labelled_outcome_corpus,
    default_outcome_corpus,
    default_scoring_corpus,
    disposition,
    generate_outcome_corpus,
    generate_scoring_corpus,
    golden_payload,
    recommend_policy_for_stakeholder,
    reliability_golden_payload,
    run_corpus,
    run_reliability,
    run_scoring_corpus,
    scoring_golden_payload,
    wilson_ci,
)
from littleboy.cli import app
from littleboy.core.enums import Verdict

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
    assert "CALIBRATION (audit)" in result.stdout
    assert "CALIBRATION (scoring)" in result.stdout
    assert "miss_rate=" in result.stdout


# --- scoring-layer calibration (v0.10) ---------------------------------------


SCORING_GOLDEN = Path(__file__).resolve().parent / "golden" / "scoring_corpus.golden.json"


def test_scoring_corpus_runs_clean():
    report = run_scoring_corpus(default_scoring_corpus())
    assert report.verdict_accuracy == 1.0
    assert report.verdict_mismatches == []
    for layer in report.layers:
        assert layer.miss_rate == 0.0
        assert layer.false_alarm_rate == 0.0


def test_scoring_layers_cover_coercion_evidence_temporal():
    report = run_scoring_corpus(default_scoring_corpus())
    layers = {layer.layer for layer in report.layers}
    assert {"coercion", "data_sufficiency", "temporal"} <= layers


def test_scoring_golden_regression():
    payload = scoring_golden_payload(run_scoring_corpus(default_scoring_corpus()))
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        SCORING_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(SCORING_GOLDEN.read_text())
    assert payload == expected, (
        "scoring calibration drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_scoring_miss_is_detected():
    # Mislabel a clearly low-coercion case as coercive: the coercion layer must miss it.
    corpus = ScoringCorpus(
        entries=[
            ScoringCorpusEntry(
                id="planted_coercion_miss",
                case=_load("low_coercion_good_data.json"),
                expect=LayerExpectation(coercive=True),
            )
        ]
    )
    report = run_scoring_corpus(corpus)
    coercion = next(layer for layer in report.layers if layer.layer == "coercion")
    assert coercion.miss_rate == 1.0


def test_scoring_false_alarm_is_detected():
    # Mislabel a high-coercion case as non-coercive: the coercion layer must false-alarm.
    corpus = ScoringCorpus(
        entries=[
            ScoringCorpusEntry(
                id="planted_coercion_false_alarm",
                case=_load("high_coercion_case.json"),
                expect=LayerExpectation(coercive=False),
            )
        ]
    )
    report = run_scoring_corpus(corpus)
    coercion = next(layer for layer in report.layers if layer.layer == "coercion")
    assert coercion.false_alarm_rate == 1.0


# --- per-policy breakdown and confidence intervals (v0.11) -------------------


def test_scoring_reports_all_four_policies():
    report = run_scoring_corpus(default_scoring_corpus())
    policies = {pp.policy for pp in report.per_policy}
    assert policies == {"permissive", "standard", "strict", "precautionary"}


def test_scoring_confidence_intervals_bracket_the_rates():
    report = run_scoring_corpus(default_scoring_corpus())
    for layer in report.layers:
        assert layer.miss_rate_ci.low <= layer.miss_rate <= layer.miss_rate_ci.high
        assert (
            layer.false_alarm_rate_ci.low
            <= layer.false_alarm_rate
            <= layer.false_alarm_rate_ci.high
        )
        assert layer.miss_rate_ci.low <= layer.miss_rate_ci.high


def test_wilson_ci_is_deterministic_and_bounded():
    a = wilson_ci(1, 10)
    b = wilson_ci(1, 10)
    assert a == b  # deterministic
    assert 0.0 <= a.low <= a.high <= 1.0
    assert wilson_ci(0, 0) == ConfidenceInterval(low=0.0, high=1.0)  # no data -> unknown


def test_stricter_policy_shifts_the_false_alarm_rate():
    report = run_scoring_corpus(default_scoring_corpus())
    by_policy = {pp.policy: pp for pp in report.per_policy}

    def coercion_fa(policy: str) -> float:
        layer = next(layer for layer in by_policy[policy].layers if layer.layer == "coercion")
        return layer.false_alarm_rate

    # Lower coercion thresholds flag more borderline cases: precautionary >= standard.
    assert coercion_fa("precautionary") >= coercion_fa("standard")


# --- generated, independently-labelled corpus at scale (v0.12) ---------------


GENERATED_GOLDEN = Path(__file__).resolve().parent / "golden" / "scoring_generated.golden.json"


def test_generator_is_deterministic():
    a = scoring_golden_payload(run_scoring_corpus(generate_scoring_corpus(n=50, seed=7)))
    b = scoring_golden_payload(run_scoring_corpus(generate_scoring_corpus(n=50, seed=7)))
    assert a == b


def test_generated_labels_are_independent_of_the_heuristics():
    # Labels come from latent parameters, so the heuristic detector genuinely disagrees
    # with some of them -- a real, measured miss/false-alarm rate (not a tautological 0).
    report = run_scoring_corpus(default_generated_scoring_corpus())
    coercion = next(layer for layer in report.layers if layer.layer == "coercion")
    assert coercion.n_labelled == 120
    assert (coercion.false_alarm_rate > 0.0) or (coercion.miss_rate > 0.0)


def test_confidence_intervals_tighten_with_more_data():
    def fa_width(n: int) -> float:
        report = run_scoring_corpus(generate_scoring_corpus(n=n, seed=0))
        layer = next(x for x in report.layers if x.layer == "coercion")
        return layer.false_alarm_rate_ci.high - layer.false_alarm_rate_ci.low

    assert fa_width(320) < fa_width(40)


def test_generated_golden_regression():
    payload = scoring_golden_payload(run_scoring_corpus(default_generated_scoring_corpus()))
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        GENERATED_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(GENERATED_GOLDEN.read_text())
    assert payload == expected, (
        "generated-corpus calibration drifted; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_calibrate_generated_works():
    result = runner.invoke(app, ["calibrate", "--scope", "scoring", "--generated", "--n", "40"])
    assert result.exit_code == 0
    assert "CALIBRATION (scoring)" in result.stdout


# --- external-validity reliability vs held-out human labels (v0.13) ----------


RELIABILITY_GOLDEN = Path(__file__).resolve().parent / "golden" / "outcome_reliability.golden.json"


def test_disposition_mapping():
    assert disposition(Verdict.ACCEPTABLE) == "permissible"
    assert disposition(Verdict.ACCEPTABLE_WITH_RESERVATIONS) == "permissible"
    assert disposition(Verdict.NOT_ACCEPTABLE) == "impermissible"
    assert disposition(Verdict.ETHICALLY_SUSPICIOUS) == "impermissible"
    assert disposition(Verdict.INSUFFICIENT_DATA) == "insufficient"


def test_reliability_has_dev_and_holdout_splits_per_policy():
    report = run_reliability(default_outcome_corpus())
    splits = {s.split for s in report.splits}
    assert splits == {"dev", "holdout"}
    for s in report.splits:
        assert {p.policy for p in s.policies} == {
            "permissive",
            "standard",
            "strict",
            "precautionary",
        }


def test_standard_policy_tracks_human_labels_best_on_holdout():
    report = run_reliability(default_outcome_corpus())
    holdout = next(s for s in report.splits if s.split == "holdout")
    by_policy = {p.policy: p.exact_accuracy for p in holdout.policies}
    # standard is at least as aligned with human judgment as the stricter policies
    assert by_policy["standard"] >= by_policy["strict"]
    assert by_policy["standard"] >= by_policy["precautionary"]
    # and it is the (a) best -- a real, measured, sub-1.0 reliability
    assert by_policy["standard"] == max(by_policy.values())
    assert by_policy["standard"] < 1.0


def test_reliability_intervals_bracket_the_accuracies():
    report = run_reliability(default_outcome_corpus())
    for s in report.splits:
        for p in s.policies:
            assert p.exact_accuracy_ci.low <= p.exact_accuracy <= p.exact_accuracy_ci.high
            assert (
                p.disposition_accuracy_ci.low
                <= p.disposition_accuracy
                <= p.disposition_accuracy_ci.high
            )


def test_reliability_golden_regression():
    payload = reliability_golden_payload(run_reliability(default_outcome_corpus()))
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        RELIABILITY_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(RELIABILITY_GOLDEN.read_text())
    assert payload == expected, (
        "reliability drifted from the golden file; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_calibrate_reliability_works():
    result = runner.invoke(app, ["calibrate", "--scope", "reliability"])
    assert result.exit_code == 0
    assert "reliability vs held-out human labels" in result.stdout
    assert "holdout" in result.stdout


# --- multi-labeller corpus, inter-rater agreement & policy recommendation (v0.14) ---


LABELLED_GOLDEN = (
    Path(__file__).resolve().parent / "golden" / "labelled_outcome_reliability.golden.json"
)


def test_outcome_generator_is_deterministic():
    a = reliability_golden_payload(run_reliability(generate_outcome_corpus(n=40, seed=3)))
    b = reliability_golden_payload(run_reliability(generate_outcome_corpus(n=40, seed=3)))
    assert a == b


def test_inter_rater_agreement_is_a_real_ceiling():
    report = run_reliability(default_labelled_outcome_corpus())
    holdout = next(s for s in report.splits if s.split == "holdout")
    ir = holdout.inter_rater
    assert ir is not None
    assert ir.n_labelers == 3
    # the labelers genuinely disagree (kappa well below 1) but better than chance (above 0)
    assert 0.0 < ir.fleiss_kappa < 1.0
    assert 0.0 < ir.percent_agreement < 1.0


def test_recommendation_diverges_by_stakeholder():
    corpus = default_labelled_outcome_corpus()
    lenient = recommend_policy_for_stakeholder(corpus, "lenient")
    strict = recommend_policy_for_stakeholder(corpus, "strict")
    # a lenient stakeholder is best matched by a permissive policy; a strict one by a
    # conservative policy -- the recommendation tracks *them*, not a fixed answer.
    assert lenient.recommended_policy == "permissive"
    assert strict.recommended_policy in {"strict", "precautionary"}
    assert lenient.recommended_policy != strict.recommended_policy


def test_recommendation_shows_tradeoffs_and_ceiling():
    rec = recommend_policy_for_stakeholder(default_labelled_outcome_corpus(), "strict")
    # the winner is the max-accuracy policy in the ranking
    best = max(rec.ranked, key=lambda p: p.disposition_accuracy)
    assert rec.recommended_policy == best.policy
    assert rec.recommended_accuracy == best.disposition_accuracy
    # ties and the agreement ceiling are surfaced, not hidden
    assert rec.agreement_ceiling is not None
    assert rec.ranked  # full ranking is present


def test_recommendation_handles_consensus_target():
    rec = recommend_policy_for_stakeholder(default_labelled_outcome_corpus(), None)
    assert rec.target == "consensus"
    assert rec.recommended_policy is not None


def test_labelled_reliability_golden_regression():
    payload = reliability_golden_payload(run_reliability(default_labelled_outcome_corpus()))
    if os.environ.get("LITTLEBOY_UPDATE_GOLDEN"):
        LABELLED_GOLDEN.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    expected = json.loads(LABELLED_GOLDEN.read_text())
    assert payload == expected, (
        "labelled-corpus reliability drifted; "
        "re-run with LITTLEBOY_UPDATE_GOLDEN=1 if the change is intended"
    )


def test_cli_recommend_policy_works():
    result = runner.invoke(app, ["recommend-policy", "--stakeholder", "strict"])
    assert result.exit_code == 0
    assert "RECOMMENDED POLICY" in result.stdout
    assert "inter-labeller agreement ceiling" in result.stdout


def test_cli_calibrate_labelled_reliability_shows_ceiling():
    result = runner.invoke(app, ["calibrate", "--scope", "reliability", "--labelled"])
    assert result.exit_code == 0
    assert "reliability vs held-out human labels" in result.stdout
    # the large multi-labeller corpus surfaces the inter-rater ceiling; the small
    # packaged corpus (without --labelled) has no panel and so does not.
    assert "inter-rater ceiling" in result.stdout
