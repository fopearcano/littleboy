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
detected is a *false alarm*. Each rate carries a deterministic **Wilson score
confidence interval**, and the whole corpus is re-run under each policy mode (the
detectors use policy thresholds), so the precision/recall trade-off is visible
*per layer per policy*.
"""

from __future__ import annotations

import math
from importlib import resources
from pathlib import Path

from littleboy.calibration.models import (
    ConfidenceInterval,
    LayerMetrics,
    PolicyScoringMetrics,
    ScoringCalibrationReport,
    ScoringCorpus,
)
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.rules.policy import get_policy

_SCORING_RESOURCE = "scoring_corpus.json"
_Z = 1.96  # 95% confidence


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


def wilson_ci(k: int, n: int, z: float = _Z) -> ConfidenceInterval:
    """Deterministic Wilson score interval for ``k`` successes in ``n`` trials.

    With no trials (``n == 0``) the rate is unknown, so the interval is the whole
    ``[0, 1]``. No randomness is involved -- the bounds are a closed-form function
    of the counts.
    """
    if n == 0:
        return ConfidenceInterval(low=0.0, high=1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return ConfidenceInterval(
        low=round(max(0.0, center - half), 4),
        high=round(min(1.0, center + half), 4),
    )


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


def _layer_metrics(corpus: ScoringCorpus, policy_override: str | None) -> list[LayerMetrics]:
    """Confusion + rates + CIs for each layer, under each entry's policy (or an override)."""
    counts = {name: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for name, _, _ in _LAYERS}
    for entry in corpus.entries:
        mode = policy_override or entry.policy
        policy = get_policy(mode)
        report = EthicalEvaluator(mode).evaluate(entry.case)
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

    layers: list[LayerMetrics] = []
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
                miss_rate_ci=wilson_ci(c["fn"], positives),
                false_alarm_rate=_rate(c["fp"], negatives),
                false_alarm_rate_ci=wilson_ci(c["fp"], negatives),
            )
        )
    return layers


def run_scoring_corpus(corpus: ScoringCorpus) -> ScoringCalibrationReport:
    """Audit the scoring layers against the corpus, with CIs and a per-policy breakdown."""
    layers = _layer_metrics(corpus, policy_override=None)

    verdict_labelled = 0
    verdict_correct = 0
    verdict_mismatches: list[str] = []
    for entry in corpus.entries:
        if entry.expect.verdict is None:
            continue
        verdict_labelled += 1
        report = EthicalEvaluator(entry.policy).evaluate(entry.case)
        if report.verdict == entry.expect.verdict:
            verdict_correct += 1
        else:
            verdict_mismatches.append(
                f"{entry.id}: expected {entry.expect.verdict.value}, got {report.verdict.value}"
            )

    per_policy = [
        PolicyScoringMetrics(policy=mode.value, layers=_layer_metrics(corpus, policy_override=mode))
        for mode in PolicyMode
    ]

    return ScoringCalibrationReport(
        n_cases=len(corpus.entries),
        layers=layers,
        verdict_labelled=verdict_labelled,
        verdict_correct=verdict_correct,
        verdict_accuracy=_rate(verdict_correct, verdict_labelled),
        verdict_mismatches=verdict_mismatches,
        per_policy=per_policy,
        notes=[
            "each scoring layer is a transparent binary detector over the evaluation report",
            "miss_rate = labelled-positive cases the layer failed to detect; false_alarm_rate = "
            "labelled-negative cases the layer flagged anyway",
            "rates carry deterministic Wilson 95% confidence intervals; per_policy re-runs the "
            "corpus under each policy mode (detectors use policy thresholds)",
            "verdict accuracy is reported only against each entry's own policy (the verdict is "
            "policy-dependent by design)",
        ],
    )


def scoring_golden_payload(report: ScoringCalibrationReport) -> dict:
    """The stable subset of a scoring report compared by golden-file regression tests."""

    def _layer(layer: LayerMetrics) -> dict:
        return {
            "layer": layer.layer,
            "n_labelled": layer.n_labelled,
            "true_positive": layer.true_positive,
            "false_positive": layer.false_positive,
            "false_negative": layer.false_negative,
            "true_negative": layer.true_negative,
            "miss_rate": layer.miss_rate,
            "miss_rate_ci": layer.miss_rate_ci.model_dump(mode="json"),
            "false_alarm_rate": layer.false_alarm_rate,
            "false_alarm_rate_ci": layer.false_alarm_rate_ci.model_dump(mode="json"),
        }

    return {
        "n_cases": report.n_cases,
        "verdict_labelled": report.verdict_labelled,
        "verdict_correct": report.verdict_correct,
        "verdict_accuracy": report.verdict_accuracy,
        "layers": [_layer(layer) for layer in report.layers],
        "per_policy": [
            {"policy": pp.policy, "layers": [_layer(layer) for layer in pp.layers]}
            for pp in report.per_policy
        ],
    }
