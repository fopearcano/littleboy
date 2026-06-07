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

import statistics
from collections import Counter

from littleboy.calibration.models import (
    CrossValidatedFit,
    FittedPolicy,
    FoldResult,
    OutcomeCorpus,
    ThresholdSet,
)
from littleboy.calibration.reliability import (
    _label_for,
    _policy_reliability,
    disposition,
    inter_rater_agreement,
)
from littleboy.core.enums import PolicyMode
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.rules.policy import DEFAULT_PROFILES, PolicyProfile


def _grid(lo: float, hi: float, step: float) -> tuple[float, ...]:
    """A closed, inclusive, float-drift-free grid from ``lo`` to ``hi``."""
    n = round((hi - lo) / step)
    return tuple(round(lo + i * step, 2) for i in range(n + 1))


# Deterministic default grids over the two coercion thresholds (the tunable part).
DEFAULT_MODERATE_GRID = _grid(0.10, 0.45, 0.05)
DEFAULT_MAX_GRID = _grid(0.35, 0.80, 0.05)


def _profile_from_thresholds(ts: ThresholdSet) -> PolicyProfile:
    """A real ``PolicyProfile``: the base mode with the fitted thresholds applied.

    The two coercion thresholds are always applied; the data-quality gate and the
    irreversibility floor are applied only when fitted (non-``None``), else the base
    profile's value is kept.
    """
    base = DEFAULT_PROFILES[PolicyMode(ts.base_mode)]
    update: dict[str, float] = {
        "coercion_moderate": ts.coercion_moderate,
        "max_coercion_for_acceptable": ts.max_coercion_for_acceptable,
    }
    if ts.min_data_quality_for_approval is not None:
        update["min_data_quality_for_approval"] = ts.min_data_quality_for_approval
    if ts.irreversible_min_epistemic is not None:
        update["irreversible_min_epistemic"] = ts.irreversible_min_epistemic
    return base.model_copy(update=update)


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


def _order_key(ts: ThresholdSet, acc: float) -> tuple:
    """A total order for picking the best candidate: max accuracy, then most central."""
    dist = _threshold_distance(ts, DEFAULT_PROFILES[PolicyMode.STANDARD])
    return (
        -acc,
        dist,
        ts.coercion_moderate,
        ts.max_coercion_for_acceptable,
        -1.0 if ts.min_data_quality_for_approval is None else ts.min_data_quality_for_approval,
        -1.0 if ts.irreversible_min_epistemic is None else ts.irreversible_min_epistemic,
    )


def _candidate_thresholds(
    base_mode: str,
    moderate_grid: tuple[float, ...],
    max_grid: tuple[float, ...],
    data_gate_grid: tuple[float | None, ...] = (None,),
    reversibility_grid: tuple[float | None, ...] = (None,),
) -> list[ThresholdSet]:
    """The deterministic candidate grid (coercion dims always; the other two optional)."""
    candidates: list[ThresholdSet] = []
    for m in moderate_grid:
        for x in max_grid:
            if m > x:
                continue
            for dg in data_gate_grid:
                for rev in reversibility_grid:
                    candidates.append(
                        ThresholdSet(
                            coercion_moderate=m,
                            max_coercion_for_acceptable=x,
                            min_data_quality_for_approval=dg,
                            irreversible_min_epistemic=rev,
                            base_mode=base_mode,
                        )
                    )
    return candidates


def _ts_key(ts: ThresholdSet) -> tuple:
    """A hashable identity for a threshold set (for counting modal fits)."""
    return (
        ts.coercion_moderate,
        ts.max_coercion_for_acceptable,
        ts.min_data_quality_for_approval,
        ts.irreversible_min_epistemic,
        ts.base_mode,
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
    data_gate_grid: tuple[float | None, ...] = (None,),
    reversibility_grid: tuple[float | None, ...] = (None,),
) -> FittedPolicy:
    """Fit thresholds on the dev split; score honestly on the holdout.

    Returns a :class:`FittedPolicy` with the fitted thresholds, their held-out
    agreement (with interval), the nearest built-in policy's held-out agreement, the
    gain from fitting, and the inter-labeller ceiling. By default only the two
    coercion thresholds are fitted; pass ``data_gate_grid`` / ``reversibility_grid``
    to also fit the data-quality gate and the irreversibility floor.
    """
    label_of = _label_for(labeler)
    target = labeler or "consensus"
    fit_entries = [e for e in corpus.entries if e.split == fit_split]
    report_entries = [e for e in corpus.entries if e.split == report_split]
    if not fit_entries or not report_entries:
        raise ValueError(
            f"need both a '{fit_split}' and a '{report_split}' split to fit and report"
        )

    def _acc(pr) -> float:
        return pr.disposition_accuracy if metric == "disposition" else pr.exact_accuracy

    # Grid search on the dev split only. Ties are broken toward the more central
    # (closest-to-standard) thresholds so the fit is stable and deterministic.
    best_ts: ThresholdSet | None = None
    best_key: tuple | None = None
    for ts in _candidate_thresholds(
        base_mode, moderate_grid, max_grid, data_gate_grid, reversibility_grid
    ):
        pr = _policy_reliability(fit_entries, _profile_from_thresholds(ts), label_of, name="fit")
        key = _order_key(ts, _acc(pr))
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


# =============================================================================
# k-fold cross-validation: the fitting procedure's gain, with a variance
# =============================================================================


def _match_matrix(cases, profiles, label_of, metric: str) -> list[list[bool]]:
    """``m[i][j]`` = did ``profiles[j]`` match the target label for ``cases[i]``?

    Computed once; every fold then reduces to counting over index subsets, so CV
    costs one full grid evaluation regardless of ``k`` (and stays deterministic).
    """
    targets = [label_of(c) for c in cases]
    exact = metric == "exact"
    target_keys = [t if exact else disposition(t) for t in targets]
    evaluators = [EthicalEvaluator(p) for p in profiles]
    matrix: list[list[bool]] = []
    for i, c in enumerate(cases):
        row = []
        for ev in evaluators:
            v = ev.evaluate(c.case).verdict
            row.append((v if exact else disposition(v)) == target_keys[i])
        matrix.append(row)
    return matrix


def _accuracy_over(matrix: list[list[bool]], idxs: list[int], col: int) -> float:
    if not idxs:
        return 0.0
    return sum(1 for i in idxs if matrix[i][col]) / len(idxs)


def cross_validate_threshold_policy(
    corpus: OutcomeCorpus,
    labeler: str | None = None,
    *,
    k: int = 5,
    metric: str = "disposition",
    base_mode: str = "standard",
    moderate_grid: tuple[float, ...] = DEFAULT_MODERATE_GRID,
    max_grid: tuple[float, ...] = DEFAULT_MAX_GRID,
    data_gate_grid: tuple[float | None, ...] = (None,),
    reversibility_grid: tuple[float | None, ...] = (None,),
) -> CrossValidatedFit:
    """k-fold CV of the fitting procedure: gain over the nearest built-in, mean ± spread.

    Pools all cases into ``k`` deterministic folds (stride assignment ``i % k``).
    Each fold fits thresholds on its training part and scores them -- and the
    nearest built-in -- on its held-out part, so the gain reported is the
    procedure's *generalisation*, not one lucky holdout.
    """
    if k < 2:
        raise ValueError("k-fold CV needs k >= 2")
    label_of = _label_for(labeler)
    target = labeler or "consensus"
    cases = list(corpus.entries)
    n = len(cases)
    if n < k:
        raise ValueError(f"need at least k={k} cases to cross-validate; got {n}")

    candidates = _candidate_thresholds(
        base_mode, moderate_grid, max_grid, data_gate_grid, reversibility_grid
    )
    cand_match = _match_matrix(
        cases, [_profile_from_thresholds(ts) for ts in candidates], label_of, metric
    )

    builtin_modes = list(PolicyMode)
    builtin_match = _match_matrix(
        cases, [DEFAULT_PROFILES[m] for m in builtin_modes], label_of, metric
    )

    folds: list[FoldResult] = []
    for f in range(k):
        test_idxs = [i for i in range(n) if i % k == f]
        train_idxs = [i for i in range(n) if i % k != f]
        if not test_idxs or not train_idxs:
            continue
        # fit on the training part
        best_j, best_key = 0, None
        for j, ts in enumerate(candidates):
            key = _order_key(ts, _accuracy_over(cand_match, train_idxs, j))
            if best_key is None or key < best_key:
                best_key, best_j = key, j
        best_ts = candidates[best_j]
        fitted_acc = _accuracy_over(cand_match, test_idxs, best_j)
        nearest_mode = _nearest_builtin(best_ts)
        nearest_acc = _accuracy_over(builtin_match, test_idxs, builtin_modes.index(nearest_mode))
        folds.append(
            FoldResult(
                fold=f,
                n_train=len(train_idxs),
                n_test=len(test_idxs),
                thresholds=best_ts,
                fitted_accuracy=round(fitted_acc, 4),
                nearest_builtin=nearest_mode.value,
                nearest_builtin_accuracy=round(nearest_acc, 4),
                gain=round(fitted_acc - nearest_acc, 4),
            )
        )

    gains = [fr.gain for fr in folds]
    mean_gain = statistics.fmean(gains)
    gain_std = statistics.pstdev(gains) if len(gains) > 1 else 0.0

    # the modal fitted threshold set (and how often it won) -- a stability read.
    # ties broken toward the most central (closest-to-standard) set, deterministically.
    ts_by_key = {_ts_key(fr.thresholds): fr.thresholds for fr in folds}
    counts = Counter(_ts_key(fr.thresholds) for fr in folds)
    modal_n = max(counts.values())
    modal_key = min(
        (key for key, c in counts.items() if c == modal_n),
        key=lambda key: _order_key(ts_by_key[key], 0.0),
    )
    modal_ts = ts_by_key[modal_key]

    ir = inter_rater_agreement(cases)
    ceiling = ir.percent_agreement if ir is not None else None
    fitting_helps = mean_gain > 0.0 and (mean_gain - gain_std) > 0.0

    notes = [
        f"{k}-fold CV of fitting to '{target}' by {metric} agreement; each fold fits on its "
        "training part and scores on its held-out part",
        (
            f"fitting helps: mean gain over the nearest built-in is {mean_gain:+.3f} "
            f"(± {gain_std:.3f}), positive even one standard deviation down"
            if fitting_helps
            else f"fitting does NOT robustly help: mean gain {mean_gain:+.3f} (± {gain_std:.3f}) "
            "is within a standard deviation of zero -- prefer the simpler built-in"
        ),
        f"fitted thresholds were stable across {modal_n}/{len(folds)} folds; low stability or a "
        "wide spread means the fit is chasing noise",
    ]
    if ceiling is not None:
        notes.append(
            f"inter-labeller agreement over all cases is {ceiling:.2f}; the ceiling for matching "
            "the consensus"
        )

    return CrossValidatedFit(
        target=target,
        metric=metric,
        k=k,
        n_cases=n,
        folds=folds,
        mean_fitted_accuracy=round(statistics.fmean(fr.fitted_accuracy for fr in folds), 4),
        mean_nearest_accuracy=round(
            statistics.fmean(fr.nearest_builtin_accuracy for fr in folds), 4
        ),
        mean_gain=round(mean_gain, 4),
        gain_std=round(gain_std, 4),
        gain_min=round(min(gains), 4),
        gain_max=round(max(gains), 4),
        fitting_helps=fitting_helps,
        modal_thresholds=modal_ts,
        threshold_stability=round(modal_n / len(folds), 4),
        agreement_ceiling=ceiling,
        notes=notes,
    )


def cross_validated_fit_golden_payload(cv: CrossValidatedFit) -> dict:
    """The stable digest of a cross-validated fit, for golden-file regression."""
    return cv.model_dump(mode="json")
