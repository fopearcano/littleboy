"""Fit a custom coercion-threshold policy to one stakeholder -- honestly.

The four built-in policies are coarse postures. Given a stakeholder's labels, we
can do better: search a deterministic grid of coercion thresholds for the set that
best matches them. The discipline that keeps this honest:

- the search runs **only on the dev split**; the chosen thresholds are then scored
  on the **holdout**, which the fit never saw (no peeking, no over-fitting);
- the fitted policy is shown **side-by-side with the nearest built-in** so the
  *gain* from fitting is auditable, with confidence intervals on both;
- the inter-labeller agreement **ceiling** bounds the claim -- beating it is a sign
  of over-fitting one labeller's idiosyncrasy, not of a better policy.

A fitted threshold set is turned back into a real ``PolicyProfile`` and run through
the *real* engine, so nothing about the verdict logic is duplicated or changed.
"""

from __future__ import annotations

from littleboy.calibration.models import (
    FittedPolicy,
    OutcomeCorpus,
    ThresholdSet,
)
from littleboy.calibration.reliability import (
    _label_for,
    _policy_reliability,
    inter_rater_agreement,
)
from littleboy.core.enums import PolicyMode
from littleboy.rules.policy import DEFAULT_PROFILES, PolicyProfile


def _grid(lo: float, hi: float, step: float) -> tuple[float, ...]:
    """A closed, inclusive, float-drift-free grid from ``lo`` to ``hi``."""
    n = round((hi - lo) / step)
    return tuple(round(lo + i * step, 2) for i in range(n + 1))


# Deterministic default grids over the two coercion thresholds (the tunable part).
DEFAULT_MODERATE_GRID = _grid(0.10, 0.45, 0.05)
DEFAULT_MAX_GRID = _grid(0.35, 0.80, 0.05)


def _profile_from_thresholds(ts: ThresholdSet) -> PolicyProfile:
    """A real ``PolicyProfile``: the base mode with the two coercion thresholds fitted."""
    base = DEFAULT_PROFILES[PolicyMode(ts.base_mode)]
    return base.model_copy(
        update={
            "coercion_moderate": ts.coercion_moderate,
            "max_coercion_for_acceptable": ts.max_coercion_for_acceptable,
        }
    )


def _threshold_distance(ts: ThresholdSet, profile: PolicyProfile) -> float:
    return (ts.coercion_moderate - profile.coercion_moderate) ** 2 + (
        ts.max_coercion_for_acceptable - profile.max_coercion_for_acceptable
    ) ** 2


def _nearest_builtin(ts: ThresholdSet) -> PolicyMode:
    """The built-in policy whose coercion thresholds are closest to the fitted set."""
    return min(
        DEFAULT_PROFILES,
        key=lambda mode: (_threshold_distance(ts, DEFAULT_PROFILES[mode]), mode.value),
    )


def fit_threshold_policy(
    corpus: OutcomeCorpus,
    labeler: str | None = None,
    *,
    metric: str = "disposition",
    fit_split: str = "dev",
    report_split: str = "holdout",
    base_mode: str = "standard",
    moderate_grid: tuple[float, ...] = DEFAULT_MODERATE_GRID,
    max_grid: tuple[float, ...] = DEFAULT_MAX_GRID,
) -> FittedPolicy:
    """Fit coercion thresholds on the dev split; score honestly on the holdout.

    Returns a :class:`FittedPolicy` with the fitted thresholds, their held-out
    agreement (with interval), the nearest built-in policy's held-out agreement, the
    gain from fitting, and the inter-labeller ceiling.
    """
    label_of = _label_for(labeler)
    target = labeler or "consensus"
    fit_entries = [e for e in corpus.entries if e.split == fit_split]
    report_entries = [e for e in corpus.entries if e.split == report_split]
    if not fit_entries or not report_entries:
        raise ValueError(
            f"need both a '{fit_split}' and a '{report_split}' split to fit and report"
        )

    standard = DEFAULT_PROFILES[PolicyMode.STANDARD]

    def _acc(pr) -> float:
        return pr.disposition_accuracy if metric == "disposition" else pr.exact_accuracy

    # Grid search on the dev split only. Ties are broken toward the more central
    # (closest-to-standard) thresholds so the fit is stable and deterministic.
    best_ts: ThresholdSet | None = None
    best_key: tuple[float, float, float, float] | None = None
    for m in moderate_grid:
        for x in max_grid:
            if m > x:
                continue
            ts = ThresholdSet(
                coercion_moderate=m, max_coercion_for_acceptable=x, base_mode=base_mode
            )
            pr = _policy_reliability(
                fit_entries, _profile_from_thresholds(ts), label_of, name="fit"
            )
            # maximise accuracy; then minimise distance-to-standard; then (m, x) order
            key = (-_acc(pr), _threshold_distance(ts, standard), m, x)
            if best_key is None or key < best_key:
                best_key, best_ts = key, ts

    assert best_ts is not None  # grids are non-empty and include m <= x pairs

    fitted_profile = _profile_from_thresholds(best_ts)
    fit_pr = _policy_reliability(fit_entries, fitted_profile, label_of, name="fit")
    report_pr = _policy_reliability(report_entries, fitted_profile, label_of, name="fitted")

    nearest_mode = _nearest_builtin(best_ts)
    nearest_pr = _policy_reliability(report_entries, nearest_mode, label_of)

    fitted_ci = (
        report_pr.disposition_accuracy_ci
        if metric == "disposition"
        else report_pr.exact_accuracy_ci
    )
    nearest_ci = (
        nearest_pr.disposition_accuracy_ci
        if metric == "disposition"
        else nearest_pr.exact_accuracy_ci
    )
    report_acc = _acc(report_pr)
    nearest_acc = _acc(nearest_pr)
    distinguishable = fitted_ci.low > nearest_ci.high or nearest_ci.low > fitted_ci.high

    ir = inter_rater_agreement(report_entries)
    ceiling = ir.percent_agreement if ir is not None else None

    notes = [
        f"thresholds fitted to '{target}' on the '{fit_split}' split by {metric} agreement, "
        f"then scored on the never-fitted '{report_split}' split",
        f"nearest built-in policy is '{nearest_mode.value}' "
        f"(by coercion-threshold distance); shown alongside so the gain is auditable",
    ]
    if distinguishable:
        notes.append(
            f"fitting helped: held-out agreement {report_acc:.2f} vs "
            f"{nearest_acc:.2f} for '{nearest_mode.value}', and their intervals do not overlap"
        )
    else:
        notes.append(
            f"fitting did NOT clearly beat '{nearest_mode.value}' on the holdout "
            f"({report_acc:.2f} vs {nearest_acc:.2f}); the intervals overlap, so prefer the "
            "simpler built-in policy"
        )
    if ceiling is not None:
        if target == "consensus" and report_acc > ceiling:
            notes.append(
                f"held-out agreement {report_acc:.2f} exceeds the inter-labeller ceiling "
                f"{ceiling:.2f} for the consensus target; treat the excess as over-fitting the "
                "panel's noise, not real skill"
            )
        else:
            notes.append(
                f"inter-labeller agreement is {ceiling:.2f}; matching a single self-consistent "
                "stakeholder can legitimately exceed how often the labellers agree with each other"
            )

    return FittedPolicy(
        target=target,
        metric=metric,
        thresholds=best_ts,
        fit_split=fit_split,
        report_split=report_split,
        n_fit=len(fit_entries),
        n_report=len(report_entries),
        fit_accuracy=_acc(fit_pr),
        report_accuracy=report_acc,
        report_accuracy_ci=fitted_ci,
        nearest_builtin=nearest_mode.value,
        nearest_builtin_accuracy=nearest_acc,
        nearest_builtin_accuracy_ci=nearest_ci,
        gain_over_nearest=round(report_acc - nearest_acc, 4),
        distinguishable_from_nearest=distinguishable,
        agreement_ceiling=ceiling,
        notes=notes,
    )


def fitted_policy_golden_payload(fitted: FittedPolicy) -> dict:
    """The stable digest of a fitted policy, for golden-file regression."""
    return fitted.model_dump(mode="json")
