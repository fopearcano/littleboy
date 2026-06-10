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


# =============================================================================
# Fitted threshold policies (v0.15): a custom policy fitted to one stakeholder
# =============================================================================


class ThresholdSet(_CalBase):
    """The tunable thresholds of a policy, fitted to a stakeholder.

    The two coercion thresholds are always fitted. The data-quality gate and the
    irreversibility floor are *optional* extra dimensions: ``None`` means "keep the
    ``base_mode`` profile's value" (so a two-dimensional fit serialises them as
    null). Every other operational parameter is held at the base profile's value.
    A fitted set is turned back into a full ``PolicyProfile`` to run the *real*
    engine -- nothing about the verdict logic is duplicated or changed.
    """

    coercion_moderate: float = Field(ge=0.0, le=1.0)
    max_coercion_for_acceptable: float = Field(ge=0.0, le=1.0)
    min_data_quality_for_approval: float | None = Field(default=None, ge=0.0, le=1.0)
    irreversible_min_epistemic: float | None = Field(default=None, ge=0.0, le=1.0)
    base_mode: str = "standard"


class FittedPolicy(_CalBase):
    """A threshold set fitted on the dev split and honestly scored on the holdout.

    The fit *never* sees the holdout: thresholds are chosen to best match the
    stakeholder on ``fit_split``, then their agreement is reported on
    ``report_split``. The nearest built-in policy is shown alongside so the *gain*
    from fitting is auditable, and the inter-labeller ceiling bounds the claim.
    """

    target: str
    metric: str = "disposition"
    thresholds: ThresholdSet
    fit_split: str = "dev"
    report_split: str = "holdout"
    n_fit: int = 0
    n_report: int = 0
    fit_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    report_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    report_accuracy_ci: ConfidenceInterval = Field(default_factory=ConfidenceInterval)
    nearest_builtin: str = ""
    nearest_builtin_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    nearest_builtin_accuracy_ci: ConfidenceInterval = Field(default_factory=ConfidenceInterval)
    gain_over_nearest: float = Field(default=0.0, ge=-1.0, le=1.0)
    distinguishable_from_nearest: bool = Field(
        default=False,
        description="True only if the fitted CI does not overlap the nearest built-in's.",
    )
    agreement_ceiling: float | None = None
    notes: list[str] = Field(default_factory=list)


# =============================================================================
# Cross-validated fitting (v0.16): a gain estimate with a variance, not one point
# =============================================================================


class FoldResult(_CalBase):
    """One cross-validation fold: thresholds fit on the train part, scored on the test part."""

    fold: int
    n_train: int
    n_test: int
    thresholds: ThresholdSet
    fitted_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    nearest_builtin: str = ""
    nearest_builtin_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    gain: float = Field(default=0.0, ge=-1.0, le=1.0)


class CrossValidatedFit(_CalBase):
    """k-fold CV of the fitting procedure: its gain over the nearest built-in, mean ± spread.

    Each fold fits thresholds on its training part and scores them on its held-out
    part, so the reported gain is the *generalisation* of the fitting procedure --
    a claim with a variance, not one lucky holdout. ``modal_thresholds`` is the most
    frequently selected set across folds, and ``threshold_stability`` how often it
    won; an unstable fit (low stability, wide spread) is a sign fitting is chasing
    noise.
    """

    target: str
    metric: str = "disposition"
    k: int = 0
    n_cases: int = 0
    folds: list[FoldResult] = Field(default_factory=list)
    mean_fitted_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_nearest_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_gain: float = Field(default=0.0, ge=-1.0, le=1.0)
    gain_std: float = Field(default=0.0, ge=0.0, le=1.0)
    gain_min: float = Field(default=0.0, ge=-1.0, le=1.0)
    gain_max: float = Field(default=0.0, ge=-1.0, le=1.0)
    fitting_helps: bool = Field(
        default=False,
        description="True only if the mean gain stays positive one standard deviation down.",
    )
    modal_thresholds: ThresholdSet | None = None
    threshold_stability: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Fraction of folds that selected the modal set."
    )
    agreement_ceiling: float | None = None
    notes: list[str] = Field(default_factory=list)


class CVGainInference(_CalBase):
    """Calibrated inference on the fitting gain: a real p-value, not a rule of thumb.

    Over ``repeats`` repetitions of stratified ``k``-fold CV, the per-fold gains
    (fitted minus nearest built-in, both scored on the fold's held-out part) are
    tested with the **Nadeau-Bengio corrected resampled t-test**, whose variance
    correction ``(1/m + 1/(k-1))`` accounts for the overlap between folds' training
    sets -- repeating CV cannot manufacture confidence. The **exact sign test** over
    paired out-of-fold predictions (first repetition) is the assumption-light
    cross-check. ``fitting_helps`` is true only when the corrected p-value clears
    ``alpha`` *and* the mean gain is positive.
    """

    target: str
    metric: str = "disposition"
    k: int = 0
    repeats: int = 0
    stratified: bool = True
    n_cases: int = 0
    n_fold_gains: int = 0
    mean_gain: float = Field(default=0.0, ge=-1.0, le=1.0)
    fold_gain_std: float = Field(default=0.0, ge=0.0, le=1.0)
    corrected_se: float = Field(default=0.0, ge=0.0)
    t_statistic: float = 0.0
    df: int = 0
    p_value: float = Field(default=1.0, ge=0.0, le=1.0)
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    ci_low: float = Field(default=0.0, ge=-1.0, le=1.0)
    ci_high: float = Field(default=0.0, ge=-1.0, le=1.0)
    ci_width: float = Field(default=0.0, ge=0.0, le=2.0)
    sign_fitted_only: int = Field(
        default=0, description="Out-of-fold cases only the fitted policy judged correctly."
    )
    sign_nearest_only: int = Field(
        default=0, description="Out-of-fold cases only the nearest built-in judged correctly."
    )
    sign_test_p: float = Field(default=1.0, ge=0.0, le=1.0)
    fitting_helps: bool = False
    per_repetition_mean_gain: list[float] = Field(default_factory=list)
    agreement_ceiling: float | None = None
    notes: list[str] = Field(default_factory=list)
