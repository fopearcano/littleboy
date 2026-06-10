"""Corpus-level diagnosis: where the disagreement with a labeller comes from.

The v0.18/v0.19 explanations make each disagreement inspectable; this module
aggregates them into one auditable report per (labeller x policy): what fraction
of the disagreement is a **threshold question** (policy-bridgeable), an
**epistemic question** (fact-bridgeable), **ambiguous between the two** (both), or
**genuine divergence** (neither) -- each fraction with a Wilson interval -- and
which bridging parameters and facts **recur**, ranked, as a concrete tuning
agenda. Nothing new is inferred: the diagnosis is a deterministic aggregation of
engine-verified per-case explanations, and the per-case classification index is
included so every number can be drilled back down.
"""

from __future__ import annotations

from collections import Counter

from littleboy.calibration.explain import explain_label_disagreement
from littleboy.calibration.models import (
    DiagnosisFraction,
    DisagreementDiagnosis,
    DisagreementExplanation,
    OutcomeCorpus,
    RecurringAccount,
)
from littleboy.calibration.reliability import inter_rater_agreement
from littleboy.calibration.scoring import wilson_ci
from littleboy.core.enums import PolicyMode
from littleboy.rules.policy import PolicyProfile, get_policy

_CLASSIFICATIONS = ("policy-bridgeable", "fact-bridgeable", "both", "neither")

_CLASS_GLOSS = {
    "policy-bridgeable": "a threshold question: a built-in policy reproduces the label",
    "fact-bridgeable": "an epistemic question: resolving the case's unknowns reaches the label",
    "both": "ambiguous between values and facts: either route aligns the engine",
    "neither": "genuine divergence: no modelled policy or fact change reaches the label",
}


def _recurring(explanations: list[DisagreementExplanation], *, kind: str) -> list[RecurringAccount]:
    """Rank the bridging parameters or facts by how many disagreements each appears in."""
    cases_by_account: dict[str, list[str]] = {}
    for exp in explanations:
        accounts = (
            exp.minimal_parameter_accounts if kind == "parameter" else exp.minimal_fact_accounts
        )
        seen: set[str] = set()
        for account in accounts:
            seen.update(account)
        for item in sorted(seen):
            cases_by_account.setdefault(item, []).append(exp.case_id)
    ranked = sorted(cases_by_account.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [
        RecurringAccount(account=item, kind=kind, count=len(cases), cases=cases)
        for item, cases in ranked
    ]


def diagnose_disagreements(
    corpus: OutcomeCorpus,
    labeler: str | None = None,
    *,
    policy: PolicyMode | PolicyProfile | str = "standard",
    split: str | None = None,
    max_size: int = 2,
    max_fact_size: int = 2,
) -> DisagreementDiagnosis:
    """Aggregate the per-case disagreement explanations into one diagnosis report.

    Runs ``explain_label_disagreement`` over every considered case (``split``
    restricts to one split), then reports: agreement with its Wilson interval, the
    classification fractions over the disagreements (each with its interval), the
    recurring bridging parameters and facts ranked by frequency, the per-case
    classification index, and a ranked, human-readable tuning agenda.
    """
    profile = get_policy(policy)
    target = labeler or "consensus"
    entries = [e for e in corpus.entries if split is None or e.split == split]
    if not entries:
        raise ValueError(f"no cases to diagnose (split={split!r})")

    explanations: list[DisagreementExplanation] = []
    n_agree = 0
    for entry in entries:
        exp = explain_label_disagreement(
            entry, labeler, policy=profile, max_size=max_size, max_fact_size=max_fact_size
        )
        if exp.agree:
            n_agree += 1
        else:
            explanations.append(exp)

    n_cases = len(entries)
    n_disagree = len(explanations)
    tally = Counter(exp.bridge_classification for exp in explanations)
    fractions = [
        DiagnosisFraction(
            classification=cls,
            count=tally.get(cls, 0),
            fraction=round(tally.get(cls, 0) / n_disagree, 4) if n_disagree else 0.0,
            fraction_ci=wilson_ci(tally.get(cls, 0), n_disagree),
        )
        for cls in _CLASSIFICATIONS
    ]

    recurring_parameters = _recurring(explanations, kind="parameter")
    recurring_facts = _recurring(explanations, kind="fact")

    agenda: list[str] = []
    for ra in recurring_parameters[:5]:
        agenda.append(
            f"policy: '{ra.account}' bridges {ra.count}/{n_disagree} disagreement(s) "
            f"({', '.join(ra.cases[:4])}{', ...' if len(ra.cases) > 4 else ''})"
        )
    for ra in recurring_facts[:5]:
        agenda.append(
            f"facts: establishing '{ra.account}' aligns {ra.count}/{n_disagree} "
            f"disagreement(s) ({', '.join(ra.cases[:4])}{', ...' if len(ra.cases) > 4 else ''})"
        )
    neither_cases = [exp.case_id for exp in explanations if exp.bridge_classification == "neither"]
    if neither_cases:
        agenda.append(
            f"review: {len(neither_cases)}/{n_disagree} disagreement(s) are genuine divergence "
            f"({', '.join(neither_cases[:4])}{', ...' if len(neither_cases) > 4 else ''}) -- "
            "candidates for human review; no modelled policy or fact change reaches the label"
        )

    ir = inter_rater_agreement(entries)
    ceiling = ir.percent_agreement if ir is not None else None

    notes = [
        "the diagnosis aggregates engine-verified per-case explanations; the per-case "
        "classification index is included so every number can be drilled back down",
        "fractions are over the disagreements (not all cases) and carry Wilson 95% intervals",
    ]
    for cls in _CLASSIFICATIONS:
        if tally.get(cls):
            notes.append(f"{cls}: {_CLASS_GLOSS[cls]}")
    if ceiling is not None:
        notes.append(
            f"inter-labeller agreement over the considered cases is {ceiling:.2f}; agreement "
            "with one labeller cannot be expected to exceed it without over-fitting"
        )

    return DisagreementDiagnosis(
        target=target,
        policy=profile.mode.value,
        split=split,
        corpus_title=corpus.title,
        n_cases=n_cases,
        n_agree=n_agree,
        n_disagree=n_disagree,
        agreement=round(n_agree / n_cases, 4),
        agreement_ci=wilson_ci(n_agree, n_cases),
        fractions=fractions,
        recurring_parameters=recurring_parameters,
        recurring_facts=recurring_facts,
        case_classifications={exp.case_id: exp.bridge_classification for exp in explanations},
        tuning_agenda=agenda,
        agreement_ceiling=ceiling,
        notes=notes,
    )


def diagnosis_golden_payload(diagnosis: DisagreementDiagnosis) -> dict:
    """The stable digest of one diagnosis, for golden-file regression."""
    return diagnosis.model_dump(mode="json")
