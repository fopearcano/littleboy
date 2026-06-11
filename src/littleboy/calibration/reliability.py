"""External-validity reliability: agreement with a held-out, human-labelled set.

Stronger and more honest than the scoring corpora: how often does the engine's
**verdict** agree with *independent human judgment*, on a **held-out** split, **per
policy** -- and, crucially, how much do the humans agree with *each other*? The
inter-labeller agreement is the **ceiling**: no policy can be expected to match the
labels more often than the labelers match one another.

Verdicts are compared *exactly* and on a coarser **disposition** (permissible /
impermissible / insufficient). Reliability can be measured against the panel
**consensus** or against a single **stakeholder**'s labels, and a recommendation
layer picks the policy that best matches a stakeholder -- with the trade-offs (and
the agreement ceiling) shown rather than hidden.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import resources
from pathlib import Path

from littleboy.calibration.labels import apply_labels, parse_labels_csv
from littleboy.calibration.models import (
    InterRaterAgreement,
    OutcomeCorpus,
    OutcomeEntry,
    PolicyRecommendation,
    PolicyReliability,
    ReliabilityReport,
    SplitReliability,
)
from littleboy.calibration.scoring import wilson_ci
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.rules.policy import NamedPolicy, PolicyProfile

_OUTCOME_RESOURCE = "outcome_corpus.json"
_INDEPENDENT_RESOURCE = "independent_labels.csv"
_EXTERNAL_RESOURCE = "external_labels.csv"
_SPLITS = ("dev", "holdout")
_DISPOSITION_CLASSES = ("permissible", "impermissible", "insufficient")

_DISPOSITION = {
    Verdict.ACCEPTABLE: "permissible",
    Verdict.ACCEPTABLE_WITH_RESERVATIONS: "permissible",
    Verdict.ETHICALLY_SUSPICIOUS: "impermissible",
    Verdict.NOT_ACCEPTABLE: "impermissible",
    Verdict.INSUFFICIENT_DATA: "insufficient",
}

_LabelOf = Callable[[OutcomeEntry], Verdict]


def disposition(verdict: Verdict) -> str:
    """Map a verdict to a coarse permissible / impermissible / insufficient class."""
    return _DISPOSITION[verdict]


def load_outcome_corpus(path: str | Path) -> OutcomeCorpus:
    """Load an outcome corpus from a JSON file."""
    return OutcomeCorpus.model_validate_json(Path(path).read_text(encoding="utf-8"))


def default_outcome_corpus() -> OutcomeCorpus:
    """Load the packaged held-out, human-labelled outcome corpus (single-label, v0.13)."""
    text = (
        resources.files("littleboy.calibration")
        .joinpath(_OUTCOME_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return OutcomeCorpus.model_validate_json(text)


def default_independent_outcome_corpus() -> OutcomeCorpus:
    """The packaged v0.13 cases relabelled by an independent three-person panel (v0.16).

    The labels live in ``independent_labels.csv`` and were hand-authored as plausible
    *independent human judgments* -- written without consulting the engine's output,
    and disagreeing more messily than the rule-based personas. They are imported via
    the v0.15 CSV path and inherit the v0.13 dev/holdout split, so the holdout is
    never inspected during tuning.
    """
    text = (
        resources.files("littleboy.calibration")
        .joinpath(_INDEPENDENT_RESOURCE)
        .read_text(encoding="utf-8")
    )
    labels_by_case, split_by_case = parse_labels_csv(text)
    return apply_labels(
        default_outcome_corpus(),
        labels_by_case,
        split_by_case,
        title="Independent hand-authored multi-labeller outcome set (v0.16)",
    )


def default_external_outcome_corpus() -> OutcomeCorpus:
    """The packaged external set: 40 diverse cases x 5 hand-authored labellers (v0.17).

    The case structures come from the deterministic ``external_case_bank``; the
    labels live in ``external_labels.csv`` and were hand-authored per case against
    the case facts -- five labellers with different temperaments, written without
    consulting the engine's output and not computed by any rule in this codebase.
    Imported via the v0.15 CSV path; splits alternate dev/holdout, holdout never
    inspected during tuning. Still maintainer-authored stand-ins for genuinely
    external labels (the docs say so plainly).
    """
    from littleboy.calibration.generator import external_case_bank

    text = (
        resources.files("littleboy.calibration")
        .joinpath(_EXTERNAL_RESOURCE)
        .read_text(encoding="utf-8")
    )
    labels_by_case, split_by_case = parse_labels_csv(text)
    return apply_labels(
        external_case_bank(),
        labels_by_case,
        split_by_case,
        title="External hand-authored outcome set (v0.17, 40 cases x 5 labellers)",
    )


def _rate(numer: int, denom: int) -> float:
    return round(numer / denom, 4) if denom else 0.0


# =============================================================================
# Inter-labeller agreement (the reliability ceiling)
# =============================================================================


def inter_rater_agreement(entries: list[OutcomeEntry]) -> InterRaterAgreement | None:
    """Mean pairwise agreement and Fleiss' kappa over the labelers' dispositions.

    Returns ``None`` if the entries do not carry a consistent panel of >= 2 labelers.
    """
    labelled = [e for e in entries if e.labels]
    if not labelled:
        return None
    counts = {len(e.labels) for e in labelled}
    if len(counts) != 1:
        return None  # Fleiss' kappa needs a constant number of raters per item
    n_raters = counts.pop()
    if n_raters < 2:
        return None

    # Per-item category counts over dispositions.
    per_item: list[dict[str, int]] = []
    for e in labelled:
        c = dict.fromkeys(_DISPOSITION_CLASSES, 0)
        for lv in e.labels:
            c[disposition(lv.verdict)] += 1
        per_item.append(c)

    n_items = len(per_item)
    pairs = n_raters * (n_raters - 1)

    # Mean pairwise agreement.
    agreement_sum = sum(sum(v * (v - 1) for v in c.values()) / pairs for c in per_item)
    percent_agreement = round(agreement_sum / n_items, 4)

    # Fleiss' kappa.
    p_bar = agreement_sum / n_items
    totals = {cls: sum(c[cls] for c in per_item) for cls in _DISPOSITION_CLASSES}
    p_e = sum((t / (n_items * n_raters)) ** 2 for t in totals.values())
    kappa = 1.0 if p_e >= 1.0 else (p_bar - p_e) / (1.0 - p_e)

    return InterRaterAgreement(
        n_items=n_items,
        n_labelers=n_raters,
        percent_agreement=percent_agreement,
        fleiss_kappa=round(kappa, 4),
    )


# =============================================================================
# Per-policy reliability (vs consensus or a chosen stakeholder)
# =============================================================================


def _policy_reliability(
    entries,
    policy: PolicyMode | PolicyProfile,
    label_of: _LabelOf,
    *,
    name: str | None = None,
) -> PolicyReliability:
    """Agreement of one policy (built-in mode or a custom profile) with the labels."""
    evaluator = EthicalEvaluator(policy)
    display = name or (policy.value if isinstance(policy, PolicyMode) else policy.mode.value)
    n = len(entries)
    exact = 0
    disp = 0
    disagreements: list[str] = []
    for entry in entries:
        target = label_of(entry)
        verdict = evaluator.evaluate(entry.case).verdict
        if verdict == target:
            exact += 1
        else:
            disagreements.append(f"{entry.id}: label {target.value} vs engine {verdict.value}")
        if disposition(verdict) == disposition(target):
            disp += 1
    return PolicyReliability(
        policy=display,
        n=n,
        exact_correct=exact,
        exact_accuracy=_rate(exact, n),
        exact_accuracy_ci=wilson_ci(exact, n),
        disposition_correct=disp,
        disposition_accuracy=_rate(disp, n),
        disposition_accuracy_ci=wilson_ci(disp, n),
        disagreements=disagreements,
    )


def _label_for(labeler: str | None) -> _LabelOf:
    if labeler is None:
        return lambda e: e.human_verdict
    return lambda e: next((lv.verdict for lv in e.labels if lv.labeler == labeler), e.human_verdict)


def run_reliability(
    corpus: OutcomeCorpus,
    *,
    labeler: str | None = None,
    extra_policies: Sequence[NamedPolicy] = (),
) -> ReliabilityReport:
    """Per-policy agreement with the labels (consensus, or a stakeholder ``labeler``).

    Splits into ``dev`` and ``holdout`` and attaches the inter-labeller agreement
    ceiling per split. Report and trust the holdout; the dev split is for tuning.
    ``extra_policies`` adds named custom policies as additional rows alongside the
    four built-ins -- each under its own name, never conflated with its base mode
    (a name that collides with a built-in is rejected).
    """
    builtin_names = {m.value for m in PolicyMode}
    seen: set[str] = set()
    for named in extra_policies:
        if named.name in builtin_names:
            raise ValueError(f"named policy {named.name!r} collides with a built-in policy name")
        if named.name in seen:
            raise ValueError(f"duplicate named policy {named.name!r}")
        seen.add(named.name)

    label_of = _label_for(labeler)
    splits: list[SplitReliability] = []
    for split_name in _SPLITS:
        entries = [e for e in corpus.entries if e.split == split_name]
        policies = (
            [_policy_reliability(entries, mode, label_of) for mode in PolicyMode]
            + [
                _policy_reliability(entries, named.profile, label_of, name=named.name)
                for named in extra_policies
            ]
            if entries
            else []
        )
        splits.append(
            SplitReliability(
                split=split_name,
                n=len(entries),
                policies=policies,
                inter_rater=inter_rater_agreement(entries),
            )
        )
    return ReliabilityReport(
        n_cases=len(corpus.entries),
        target=labeler or "consensus",
        splits=splits,
        notes=[
            "reliability = agreement of the engine's verdict with the human label(s)",
            "exact compares verdicts; disposition compares the coarse "
            "permissible/impermissible/insufficient class",
            "report and trust the HOLDOUT split; the dev split is where thresholds may be tuned",
            "inter-labeller agreement is the ceiling: no policy can beat how often the labelers "
            "agree with one another",
            "accuracies carry deterministic Wilson 95% confidence intervals",
        ],
    )


# =============================================================================
# Policy recommendation (trade-offs shown, not hidden)
# =============================================================================


def _accuracy(policy: PolicyReliability, metric: str) -> float:
    return policy.exact_accuracy if metric == "exact" else policy.disposition_accuracy


def _ci(policy: PolicyReliability, metric: str):
    return policy.exact_accuracy_ci if metric == "exact" else policy.disposition_accuracy_ci


def recommend_policy(
    report: ReliabilityReport, *, split: str = "holdout", metric: str = "disposition"
) -> PolicyRecommendation:
    """Recommend the policy that best matches the labels, showing every trade-off.

    The ranking is by ``metric`` accuracy on ``split``; policies whose confidence
    interval overlaps the leader's are reported as *indistinguishable* (the data
    cannot separate them), and the inter-labeller agreement ceiling is reported so
    a high score is read against what the humans themselves achieve.
    """
    target_split = next((s for s in report.splits if s.split == split), None)
    if target_split is None or not target_split.policies:
        return PolicyRecommendation(
            target=report.target,
            split=split,
            metric=metric,
            notes=[f"no '{split}' split with policy results to recommend from"],
        )

    ranked = sorted(target_split.policies, key=lambda p: _accuracy(p, metric), reverse=True)
    best = ranked[0]
    best_ci = _ci(best, metric)
    indistinguishable = [
        p.policy
        for p in ranked[1:]
        if not (_ci(p, metric).high < best_ci.low or best_ci.high < _ci(p, metric).low)
    ]
    ceiling = (
        target_split.inter_rater.percent_agreement if target_split.inter_rater is not None else None
    )

    notes = [
        f"recommended for target '{report.target}' by {metric} accuracy on the {split} split",
    ]
    if indistinguishable:
        notes.append(
            "the data cannot separate the top policy from: "
            + ", ".join(indistinguishable)
            + " (their confidence intervals overlap)"
        )
    if ceiling is not None:
        notes.append(
            f"inter-labeller agreement ceiling is {ceiling:.2f}; a policy matching the labels "
            "more often than that would be over-fitting one labeller's idiosyncrasy"
        )
    notes.append(
        "trade-off: stricter policies decline or flag more (safer for cautious stakeholders, "
        "lower agreement with permissive ones); read the full ranking, not just the winner"
    )

    return PolicyRecommendation(
        target=report.target,
        split=split,
        metric=metric,
        recommended_policy=best.policy,
        recommended_accuracy=_accuracy(best, metric),
        ranked=ranked,
        indistinguishable=indistinguishable,
        agreement_ceiling=ceiling,
        notes=notes,
    )


def recommend_policy_for_stakeholder(
    corpus: OutcomeCorpus,
    labeler: str | None = None,
    *,
    split: str = "holdout",
    metric: str = "disposition",
    extra_policies: Sequence[NamedPolicy] = (),
) -> PolicyRecommendation:
    """Recommend the policy best matching one stakeholder's (or the consensus) labels.

    ``extra_policies`` enters named custom policies into the ranking alongside the
    built-ins; the recommendation can legitimately be a named policy.
    """
    report = run_reliability(corpus, labeler=labeler, extra_policies=extra_policies)
    return recommend_policy(report, split=split, metric=metric)


def reliability_golden_payload(report: ReliabilityReport) -> dict:
    """The stable subset of a reliability report compared by golden-file regression tests."""

    def _policy(p: PolicyReliability) -> dict:
        return {
            "policy": p.policy,
            "n": p.n,
            "exact_correct": p.exact_correct,
            "exact_accuracy": p.exact_accuracy,
            "exact_accuracy_ci": p.exact_accuracy_ci.model_dump(mode="json"),
            "disposition_correct": p.disposition_correct,
            "disposition_accuracy": p.disposition_accuracy,
            "disposition_accuracy_ci": p.disposition_accuracy_ci.model_dump(mode="json"),
            "disagreements": p.disagreements,
        }

    def _split(s: SplitReliability) -> dict:
        return {
            "split": s.split,
            "n": s.n,
            "policies": [_policy(p) for p in s.policies],
            "inter_rater": (s.inter_rater.model_dump(mode="json") if s.inter_rater else None),
        }

    return {
        "n_cases": report.n_cases,
        "target": report.target,
        "splits": [_split(s) for s in report.splits],
    }
