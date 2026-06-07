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
from littleboy.calibration.metrics import aggregate, score_entry
from littleboy.calibration.models import (
    AuditCorpus,
    CalibrationOutcome,
    CalibrationReport,
    CaseDigest,
    CorpusEntry,
)

__all__ = [
    "AuditCorpus",
    "CalibrationOutcome",
    "CalibrationReport",
    "CaseDigest",
    "CorpusEntry",
    "aggregate",
    "default_corpus",
    "golden_payload",
    "load_corpus",
    "run_corpus",
    "score_entry",
]
