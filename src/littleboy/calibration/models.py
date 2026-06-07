"""Typed models for the adversarial calibration corpus (v0.9).

A *calibration corpus* is a labelled set of cases — both adversarial (where audit
red flags *should* fire) and clean (where they should *not*) — together with the
findings each case is expected to raise. Running the corpus produces a
:class:`CalibrationReport` with two headline numbers a maintainer can tune
against: the **miss rate** (expected adversarial flags that did not fire) and the
**false-alarm rate** (clean cases that nonetheless raised a red flag). Golden-file
regression tests pin the per-case digests so that any drift in the audit's
behaviour is caught.

Cases are stored inline so the corpus is self-contained and deterministic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import Verdict
from littleboy.core.models import ActionCase


class _CalBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpusEntry(_CalBase):
    """One labelled case in the calibration corpus."""

    id: str
    label: str = Field(description="'adversarial' (flags expected) or 'clean' (no red flags).")
    description: str = ""
    case: ActionCase
    policy: str = "standard"
    expect_findings: list[str] = Field(
        default_factory=list,
        description="finding_ids that SHOULD be present (a miss if absent).",
    )
    forbid_findings: list[str] = Field(
        default_factory=list,
        description="finding_ids that must NOT be present (a false alarm if present).",
    )
    expect_judgment_stable: bool | None = Field(
        default=None, description="Expected audit stability, or None to not check."
    )


class AuditCorpus(_CalBase):
    """A labelled corpus of cases for calibrating the adversarial audit."""

    title: str = ""
    description: str = ""
    entries: list[CorpusEntry] = Field(default_factory=list)


class CaseDigest(_CalBase):
    """A deterministic digest of one case's audit, pinned by golden-file tests."""

    id: str
    label: str
    judgment_stable: bool
    red_flags: list[str] = Field(default_factory=list)
    all_findings: list[str] = Field(default_factory=list)
    max_severity: str = "info"
    adversarial_max_risk: float = 0.0
    bias_max_risk: float = 0.0


class CalibrationOutcome(_CalBase):
    """How one corpus entry scored against its expectations."""

    id: str
    label: str
    passed: bool
    missing_expected: list[str] = Field(default_factory=list)
    false_alarms: list[str] = Field(default_factory=list)
    stability_ok: bool = True


class CalibrationReport(_CalBase):
    """Aggregate calibration result over the whole corpus."""

    n_cases: int = 0
    n_adversarial: int = 0
    n_clean: int = 0
    n_passed: int = 0
    miss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    false_alarm_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    outcomes: list[CalibrationOutcome] = Field(default_factory=list)
    digests: list[CaseDigest] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# =============================================================================
# Scoring-layer calibration (v0.10): coercion / data-sufficiency / temporal
# =============================================================================


class LayerExpectation(_CalBase):
    """Per-layer labels for one case (each optional; only labelled layers are scored).

    Each layer is a binary detector with a known answer, so a *miss* (labelled
    positive but not detected) and a *false alarm* (labelled negative but detected)
    are well-defined.
    """

    coercive: bool | None = Field(
        default=None, description="Should the coercion layer score this at least moderate?"
    )
    adequate_data: bool | None = Field(
        default=None, description="Is there enough trustworthy data to reach a verdict?"
    )
    rising_coercion: bool | None = Field(
        default=None, description="Should the temporal layer see a rising-coercion trend?"
    )
    verdict: Verdict | None = Field(default=None, description="Expected end-to-end verdict.")


class ScoringCorpusEntry(_CalBase):
    """One labelled case for calibrating the scoring layers (not the audit)."""

    id: str
    description: str = ""
    case: ActionCase
    policy: str = "standard"
    expect: LayerExpectation = Field(default_factory=LayerExpectation)


class ScoringCorpus(_CalBase):
    """A labelled corpus for calibrating LittleBoy's scoring layers."""

    title: str = ""
    description: str = ""
    entries: list[ScoringCorpusEntry] = Field(default_factory=list)


class ConfidenceInterval(_CalBase):
    """A deterministic (Wilson score) confidence interval for a proportion."""

    low: float = Field(default=0.0, ge=0.0, le=1.0)
    high: float = Field(default=1.0, ge=0.0, le=1.0)


class LayerMetrics(_CalBase):
    """A confusion matrix, the two rates, and their confidence intervals for one layer."""

    layer: str
    n_labelled: int = 0
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    miss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    miss_rate_ci: ConfidenceInterval = Field(default_factory=ConfidenceInterval)
    false_alarm_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    false_alarm_rate_ci: ConfidenceInterval = Field(default_factory=ConfidenceInterval)


class PolicyScoringMetrics(_CalBase):
    """Per-layer metrics for the corpus run under one forced policy mode."""

    policy: str
    layers: list[LayerMetrics] = Field(default_factory=list)


class ScoringCalibrationReport(_CalBase):
    """Aggregate scoring-layer calibration over the corpus, with per-policy breakdown."""

    n_cases: int = 0
    layers: list[LayerMetrics] = Field(default_factory=list)
    verdict_labelled: int = 0
    verdict_correct: int = 0
    verdict_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict_mismatches: list[str] = Field(default_factory=list)
    per_policy: list[PolicyScoringMetrics] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# =============================================================================
# External-validity reliability (v0.13): held-out, human-labelled outcomes
# =============================================================================


class LabelerVerdict(_CalBase):
    """One labeler's verdict for a case (the panel of independent human labelers)."""

    labeler: str
    verdict: Verdict


class OutcomeEntry(_CalBase):
    """One case with held-out, human-authored verdict labels (not from the heuristics).

    ``split`` is ``"dev"`` (where you may tune) or ``"holdout"`` (reported reliability,
    never tuned against). ``human_verdict`` is the panel **consensus** (majority);
    ``labels`` carries each independent labeler's verdict, so inter-labeller
    agreement can be measured -- the ceiling against which engine reliability is read.
    """

    id: str
    description: str = ""
    case: ActionCase
    split: str = "holdout"
    human_verdict: Verdict
    labeler: str = "panel"
    labels: list[LabelerVerdict] = Field(default_factory=list)


class OutcomeCorpus(_CalBase):
    """A held-out, independently-labelled outcome set for external-validity calibration."""

    title: str = ""
    description: str = ""
    entries: list[OutcomeEntry] = Field(default_factory=list)


class PolicyReliability(_CalBase):
    """Agreement of one policy's verdicts with the human labels, with held-out intervals.

    *Exact* agreement compares the verdict directly; *disposition* agreement compares
    the coarser permissible / impermissible / insufficient class (more robust to
    fine distinctions). Both carry a Wilson confidence interval.
    """

    policy: str
    n: int = 0
    exact_correct: int = 0
    exact_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    exact_accuracy_ci: ConfidenceInterval = Field(default_factory=ConfidenceInterval)
    disposition_correct: int = 0
    disposition_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    disposition_accuracy_ci: ConfidenceInterval = Field(default_factory=ConfidenceInterval)
    disagreements: list[str] = Field(default_factory=list)


class InterRaterAgreement(_CalBase):
    """How much the human labelers agree with *each other* -- the reliability ceiling.

    ``percent_agreement`` is the mean pairwise agreement on disposition;
    ``fleiss_kappa`` is the chance-corrected agreement over the disposition classes.
    No policy can be expected to match the human labels more often than the
    labelers match one another.
    """

    n_items: int = 0
    n_labelers: int = 0
    percent_agreement: float = Field(default=0.0, ge=0.0, le=1.0)
    fleiss_kappa: float = Field(default=0.0, ge=-1.0, le=1.0)


class SplitReliability(_CalBase):
    """Per-policy reliability over one split (dev or holdout), with the agreement ceiling."""

    split: str
    n: int = 0
    policies: list[PolicyReliability] = Field(default_factory=list)
    inter_rater: InterRaterAgreement | None = None


class ReliabilityReport(_CalBase):
    """External-validity reliability of the engine against held-out human labels."""

    n_cases: int = 0
    target: str = Field(
        default="consensus", description="Whose labels reliability is measured against."
    )
    splits: list[SplitReliability] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PolicyRecommendation(_CalBase):
    """A recommended policy for a stakeholder, with the trade-offs shown rather than hidden."""

    target: str = Field(description="Whose held-out judgments the recommendation matches.")
    split: str = "holdout"
    metric: str = "disposition"
    recommended_policy: str | None = None
    recommended_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    ranked: list[PolicyReliability] = Field(default_factory=list)
    indistinguishable: list[str] = Field(
        default_factory=list,
        description="Policies whose CI overlaps the best one's -- the data cannot separate them.",
    )
    agreement_ceiling: float | None = Field(
        default=None, description="Inter-labeller agreement: the ceiling reliability can reach."
    )
    notes: list[str] = Field(default_factory=list)
