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
from littleboy.calibration.fitting import (
    fit_threshold_policy,
    fitted_policy_golden_payload,
)
from littleboy.calibration.generator import (
    default_generated_scoring_corpus,
    default_labelled_outcome_corpus,
    generate_outcome_corpus,
    generate_scoring_corpus,
)
from littleboy.calibration.labels import (
    apply_labels,
    consensus_verdict,
    labels_to_csv,
    outcome_corpus_from_csv,
    parse_labels_csv,
    parse_verdict,
)
from littleboy.calibration.metrics import aggregate, score_entry
from littleboy.calibration.models import (
    AuditCorpus,
    CalibrationOutcome,
    CalibrationReport,
    CaseDigest,
    ConfidenceInterval,
    CorpusEntry,
    FittedPolicy,
    InterRaterAgreement,
    LabelerVerdict,
    LayerExpectation,
    LayerMetrics,
    OutcomeCorpus,
    OutcomeEntry,
    PolicyRecommendation,
    PolicyReliability,
    PolicyScoringMetrics,
    ReliabilityReport,
    ScoringCalibrationReport,
    ScoringCorpus,
    ScoringCorpusEntry,
    SplitReliability,
    ThresholdSet,
)
from littleboy.calibration.reliability import (
    default_outcome_corpus,
    disposition,
    inter_rater_agreement,
    load_outcome_corpus,
    recommend_policy,
    recommend_policy_for_stakeholder,
    reliability_golden_payload,
    run_reliability,
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
    "FittedPolicy",
    "InterRaterAgreement",
    "LabelerVerdict",
    "LayerExpectation",
    "LayerMetrics",
    "OutcomeCorpus",
    "OutcomeEntry",
    "PolicyRecommendation",
    "PolicyReliability",
    "PolicyScoringMetrics",
    "ReliabilityReport",
    "ScoringCalibrationReport",
    "ScoringCorpus",
    "ScoringCorpusEntry",
    "SplitReliability",
    "ThresholdSet",
    "aggregate",
    "apply_labels",
    "consensus_verdict",
    "default_corpus",
    "default_generated_scoring_corpus",
    "default_labelled_outcome_corpus",
    "default_outcome_corpus",
    "default_scoring_corpus",
    "disposition",
    "fit_threshold_policy",
    "fitted_policy_golden_payload",
    "generate_outcome_corpus",
    "generate_scoring_corpus",
    "golden_payload",
    "inter_rater_agreement",
    "labels_to_csv",
    "load_corpus",
    "load_outcome_corpus",
    "load_scoring_corpus",
    "outcome_corpus_from_csv",
    "parse_labels_csv",
    "parse_verdict",
    "recommend_policy",
    "recommend_policy_for_stakeholder",
    "reliability_golden_payload",
    "run_corpus",
    "run_reliability",
    "run_scoring_corpus",
    "score_entry",
    "scoring_golden_payload",
    "wilson_ci",
]
