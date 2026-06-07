"""Calibrating LittleBoy's scoring layers (coercion / data-sufficiency / temporal).

The audit corpus (v0.9) measures whether the *audit* flags the right cases. This
extends the same miss / false-alarm discipline to the underlying scoring layers,
so every layer -- not only the audit -- has measured rates. Each layer is treated
as a binary detector with a transparent rule over the evaluation report:

- **coercion**: predicts "at least moderately coercive" iff
  ``coercion_score >= policy.coercion_moderate``;
- **data-sufficiency**: predicts "enough data to judge" iff the verdict is not
  ``INSUFFICIENT_DATA``;
- **temporal**: predicts "rising-coercion trend" iff the temporal projection has
  data and its trend is ``rising``.

A labelled positive that is not detected is a *miss*; a labelled negative that is
detected is a *false alarm*. The end-to-end ``verdict`` label gives an accuracy.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from littleboy.calibration.models import (
    LayerMetrics,
    ScoringCalibrationReport,
    ScoringCorpus,
)
from littleboy.core.enums import Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.rules.policy import get_policy

_SCORING_RESOURCE = "scoring_corpus.json"


def load_scoring_corpus(path: str | Path) -> ScoringCorpus:
    """Load a scoring corpus from a JSON file."""
    return ScoringCorpus.model_validate_json(Path(path).read_text(encoding="utf-8"))


def default_scoring_corpus() -> ScoringCorpus:
    """Load the packaged default scoring corpus."""
    text = (
        resources.files("littleboy.calibration")
        .joinpath(_SCORING_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return ScoringCorpus.model_validate_json(text)


# Per-layer detectors over an evaluation report + policy.
def _predict_coercive(report, policy) -> bool:
    return report.coercion_score >= policy.coercion_moderate


def _predict_adequate_data(report, _policy) -> bool:
    return report.verdict != Verdict.INSUFFICIENT_DATA


def _predict_rising(report, _policy) -> bool:
    tp = report.temporal_projection
    return bool(tp is not None and tp.has_temporal_data and tp.trend == "rising")


_LAYERS = (
    ("coercion", "coercive", _predict_coercive),
    ("data_sufficiency", "adequate_data", _predict_adequate_data),
    ("temporal", "rising_coercion", _predict_rising),
)


def _rate(numer: int, denom: int) -> float:
    return round(numer / denom, 4) if denom else 0.0


def run_scoring_corpus(corpus: ScoringCorpus) -> ScoringCalibrationReport:
    """Audit the scoring layers against the corpus and return per-layer rates."""
    # Confusion counters per layer.
    counts = {name: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for name, _, _ in _LAYERS}
    verdict_labelled = 0
    verdict_correct = 0
    verdict_mismatches: list[str] = []

    for entry in corpus.entries:
        policy = get_policy(entry.policy)
        report = EthicalEvaluator(entry.policy).evaluate(entry.case)
        for name, label_field, predict in _LAYERS:
            label = getattr(entry.expect, label_field)
            if label is None:
                continue
            predicted = predict(report, policy)
            c = counts[name]
            if label and predicted:
                c["tp"] += 1
            elif label and not predicted:
                c["fn"] += 1
            elif not label and predicted:
                c["fp"] += 1
            else:
                c["tn"] += 1
        if entry.expect.verdict is not None:
            verdict_labelled += 1
            if report.verdict == entry.expect.verdict:
                verdict_correct += 1
            else:
                verdict_mismatches.append(
                    f"{entry.id}: expected {entry.expect.verdict.value}, got {report.verdict.value}"
                )

    layers = []
    for name, _label_field, _predict in _LAYERS:
        c = counts[name]
        positives = c["tp"] + c["fn"]
        negatives = c["fp"] + c["tn"]
        layers.append(
            LayerMetrics(
                layer=name,
                n_labelled=positives + negatives,
                true_positive=c["tp"],
                false_positive=c["fp"],
                false_negative=c["fn"],
                true_negative=c["tn"],
                miss_rate=_rate(c["fn"], positives),
                false_alarm_rate=_rate(c["fp"], negatives),
            )
        )

    return ScoringCalibrationReport(
        n_cases=len(corpus.entries),
        layers=layers,
        verdict_labelled=verdict_labelled,
        verdict_correct=verdict_correct,
        verdict_accuracy=_rate(verdict_correct, verdict_labelled),
        verdict_mismatches=verdict_mismatches,
        notes=[
            "each scoring layer is a transparent binary detector over the evaluation report",
            "miss_rate = labelled-positive cases the layer failed to detect; false_alarm_rate = "
            "labelled-negative cases the layer flagged anyway",
            "these are calibration indicators over a small corpus, not population statistics",
        ],
    )


def scoring_golden_payload(report: ScoringCalibrationReport) -> dict:
    """The stable subset of a scoring report compared by golden-file regression tests."""
    return {
        "n_cases": report.n_cases,
        "verdict_labelled": report.verdict_labelled,
        "verdict_correct": report.verdict_correct,
        "verdict_accuracy": report.verdict_accuracy,
        "layers": [layer.model_dump(mode="json") for layer in report.layers],
    }
