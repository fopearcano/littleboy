"""LittleBoy adversarial calibration corpus & golden-file regression (v0.9).

A labelled corpus of adversarial and clean cases, run through the audit, scored
into a miss rate and a false-alarm rate, and pinned by golden-file regression so
that drift in the audit's behaviour is caught and the false-alarm/miss trade-off
can be tuned deliberately.
"""

from __future__ import annotations

from littleboy.calibration.corpus import (
    default_corpus,
    golden_payload,
    load_corpus,
    run_corpus,
)
from littleboy.calibration.generator import (
    default_generated_scoring_corpus,
    generate_scoring_corpus,
)
from littleboy.calibration.metrics import aggregate, score_entry
from littleboy.calibration.models import (
    AuditCorpus,
    CalibrationOutcome,
    CalibrationReport,
    CaseDigest,
    ConfidenceInterval,
    CorpusEntry,
    LayerExpectation,
    LayerMetrics,
    PolicyScoringMetrics,
    ScoringCalibrationReport,
    ScoringCorpus,
    ScoringCorpusEntry,
)
from littleboy.calibration.scoring import (
    default_scoring_corpus,
    load_scoring_corpus,
    run_scoring_corpus,
    scoring_golden_payload,
    wilson_ci,
)

__all__ = [
    "AuditCorpus",
    "CalibrationOutcome",
    "CalibrationReport",
    "CaseDigest",
    "ConfidenceInterval",
    "CorpusEntry",
    "LayerExpectation",
    "LayerMetrics",
    "PolicyScoringMetrics",
    "ScoringCalibrationReport",
    "ScoringCorpus",
    "ScoringCorpusEntry",
    "aggregate",
    "default_corpus",
    "default_generated_scoring_corpus",
    "default_scoring_corpus",
    "generate_scoring_corpus",
    "golden_payload",
    "load_corpus",
    "load_scoring_corpus",
    "run_corpus",
    "run_scoring_corpus",
    "score_entry",
    "scoring_golden_payload",
    "wilson_ci",
]
