"""External-validity reliability: agreement with a held-out, human-labelled set.

The scoring corpus (v0.10-v0.12) measures whether each layer behaves as labelled,
where the labels come from the maintainers or a latent model. This module measures
something stronger and more honest: how often the engine's **verdict** agrees with
an *independent, human-authored* judgment, on a **held-out** split that is never
tuned against, **per policy**, with proper confidence intervals.

Verdicts are compared two ways: *exactly*, and on a coarser **disposition**
(permissible / impermissible / insufficient) that is robust to fine distinctions
(e.g. ACCEPTABLE vs ACCEPTABLE_WITH_RESERVATIONS). Disagreements are listed so a
maintainer can see exactly where, and under which policy, the engine and the human
parted ways -- including which policy tracks human judgment best.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from littleboy.calibration.models import (
    OutcomeCorpus,
    PolicyReliability,
    ReliabilityReport,
    SplitReliability,
)
from littleboy.calibration.scoring import wilson_ci
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator

_OUTCOME_RESOURCE = "outcome_corpus.json"
_SPLITS = ("dev", "holdout")

_DISPOSITION = {
    Verdict.ACCEPTABLE: "permissible",
    Verdict.ACCEPTABLE_WITH_RESERVATIONS: "permissible",
    Verdict.ETHICALLY_SUSPICIOUS: "impermissible",
    Verdict.NOT_ACCEPTABLE: "impermissible",
    Verdict.INSUFFICIENT_DATA: "insufficient",
}


def disposition(verdict: Verdict) -> str:
    """Map a verdict to a coarse permissible / impermissible / insufficient class."""
    return _DISPOSITION[verdict]


def load_outcome_corpus(path: str | Path) -> OutcomeCorpus:
    """Load an outcome corpus from a JSON file."""
    return OutcomeCorpus.model_validate_json(Path(path).read_text(encoding="utf-8"))


def default_outcome_corpus() -> OutcomeCorpus:
    """Load the packaged held-out, human-labelled outcome corpus."""
    text = (
        resources.files("littleboy.calibration")
        .joinpath(_OUTCOME_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return OutcomeCorpus.model_validate_json(text)


def _rate(numer: int, denom: int) -> float:
    return round(numer / denom, 4) if denom else 0.0


def _policy_reliability(entries, mode: PolicyMode) -> PolicyReliability:
    evaluator = EthicalEvaluator(mode)
    n = len(entries)
    exact = 0
    disp = 0
    disagreements: list[str] = []
    for entry in entries:
        verdict = evaluator.evaluate(entry.case).verdict
        if verdict == entry.human_verdict:
            exact += 1
        else:
            disagreements.append(
                f"{entry.id}: human {entry.human_verdict.value} vs engine {verdict.value}"
            )
        if disposition(verdict) == disposition(entry.human_verdict):
            disp += 1
    return PolicyReliability(
        policy=mode.value,
        n=n,
        exact_correct=exact,
        exact_accuracy=_rate(exact, n),
        exact_accuracy_ci=wilson_ci(exact, n),
        disposition_correct=disp,
        disposition_accuracy=_rate(disp, n),
        disposition_accuracy_ci=wilson_ci(disp, n),
        disagreements=disagreements,
    )


def run_reliability(corpus: OutcomeCorpus) -> ReliabilityReport:
    """Compute per-policy agreement with the human labels, split into dev and holdout."""
    splits: list[SplitReliability] = []
    for split_name in _SPLITS:
        entries = [e for e in corpus.entries if e.split == split_name]
        policies = [_policy_reliability(entries, mode) for mode in PolicyMode] if entries else []
        splits.append(SplitReliability(split=split_name, n=len(entries), policies=policies))
    return ReliabilityReport(
        n_cases=len(corpus.entries),
        splits=splits,
        notes=[
            "reliability = agreement of the engine's verdict with an independent human label",
            "exact compares verdicts directly; disposition compares the coarse "
            "permissible/impermissible/insufficient class",
            "report and trust the HOLDOUT split; the dev split is where thresholds may be tuned",
            "accuracies carry deterministic Wilson 95% confidence intervals; the corpus is small, "
            "so the intervals are wide -- they bound, they do not certify",
        ],
    )


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

    return {
        "n_cases": report.n_cases,
        "splits": [
            {"split": s.split, "n": s.n, "policies": [_policy(p) for p in s.policies]}
            for s in report.splits
        ],
    }
