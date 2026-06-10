"""A dry-run tuner: the full before/after impact of a candidate parameter change.

The diagnosis (v0.20) ends in a tuning agenda; this module closes the loop from
agenda to *decision* -- without ever touching the built-in profiles. Given a base
policy and a set of parameter overrides, it builds a validated candidate profile
and reports, with **nothing silent**:

- every case whose verdict would flip (and in which direction);
- agreement with **every** labeller and the consensus, per split, before vs after,
  each with Wilson intervals and deltas -- so the cost to one stakeholder of
  pleasing another is on the table;
- which golden-pinned artefacts **would break** if the change were adopted into
  the base profile (each checked by recomputation over its underlying packaged
  corpus, or honestly marked unchecked).

Strictly dry-run and evaluation-only: ``DEFAULT_PROFILES`` is never modified, and
the verdict of every pre-existing case under the built-in policies is unchanged.
"""

from __future__ import annotations

from collections import Counter

from littleboy.audit.stress import AdversarialStressTester
from littleboy.calibration.corpus import default_corpus
from littleboy.calibration.generator import (
    default_labelled_outcome_corpus,
    generate_outcome_corpus,
    generate_scoring_corpus,
)
from littleboy.calibration.models import (
    CaseFlip,
    GoldenImpact,
    OutcomeCorpus,
    StakeholderImpact,
    TuningImpact,
)
from littleboy.calibration.reliability import (
    default_external_outcome_corpus,
    default_outcome_corpus,
    disposition,
)
from littleboy.calibration.scoring import default_scoring_corpus, wilson_ci
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.rules.policy import PolicyProfile, get_policy

_PERMISSIVENESS = {
    Verdict.NOT_ACCEPTABLE: 0,
    Verdict.ETHICALLY_SUSPICIOUS: 1,
    Verdict.ACCEPTABLE_WITH_RESERVATIONS: 2,
    Verdict.ACCEPTABLE: 3,
}


def candidate_profile(
    base: PolicyMode | PolicyProfile | str, changes: dict[str, object]
) -> PolicyProfile:
    """Build a validated candidate profile: the base with ``changes`` applied.

    Unknown parameter names raise with the valid names listed; values are
    validated (and coerced -- ``"0.25"`` is fine) through the ``PolicyProfile``
    model itself, so out-of-range values are rejected exactly as they would be
    anywhere else. The base profile object is never modified.
    """
    profile = get_policy(base)
    valid = set(PolicyProfile.model_fields.keys())
    unknown = sorted(set(changes) - valid)
    if unknown:
        raise ValueError(
            f"unknown policy parameter(s): {', '.join(unknown)}; valid: {', '.join(sorted(valid))}"
        )
    return PolicyProfile.model_validate({**profile.model_dump(), **changes})


def _direction(before: Verdict, after: Verdict) -> str:
    if before == Verdict.INSUFFICIENT_DATA:
        return "gains a verdict"
    if after == Verdict.INSUFFICIENT_DATA:
        return "declines to insufficient data"
    return (
        "more permissive" if _PERMISSIVENESS[after] > _PERMISSIVENESS[before] else "less permissive"
    )


def _verdicts(cases, profile: PolicyProfile) -> list[Verdict]:
    evaluator = EthicalEvaluator(profile)
    return [evaluator.evaluate(case).verdict for case in cases]


def _outcome_flip_count(corpus: OutcomeCorpus, base: PolicyProfile, cand: PolicyProfile) -> int:
    cases = [e.case for e in corpus.entries]
    return sum(
        1 for b, a in zip(_verdicts(cases, base), _verdicts(cases, cand), strict=True) if b != a
    )


def _scoring_changes(corpus, base: PolicyProfile, cand: PolicyProfile) -> int:
    """Verdict flips OR coercion-detector band flips on a scoring corpus."""
    changed = 0
    eval_base = EthicalEvaluator(base)
    eval_cand = EthicalEvaluator(cand)
    for entry in corpus.entries:
        rb = eval_base.evaluate(entry.case)
        ra = eval_cand.evaluate(entry.case)
        band_b = rb.coercion_score >= base.coercion_moderate
        band_a = ra.coercion_score >= cand.coercion_moderate
        if rb.verdict != ra.verdict or band_b != band_a:
            changed += 1
    return changed


def _audit_changes(base: PolicyProfile, cand: PolicyProfile) -> int:
    """Audit-corpus entries (at the base mode) whose full audit output changes."""
    base_name = base.mode.value
    tester_base = AdversarialStressTester(base)
    tester_cand = AdversarialStressTester(cand)
    changed = 0
    for entry in default_corpus().entries:
        if entry.policy != base_name:
            continue
        before = tester_base.audit_case(entry.case).model_dump(mode="json")
        after = tester_cand.audit_case(entry.case).model_dump(mode="json")
        if before != after:
            changed += 1
    return changed


def _golden_impacts(base: PolicyProfile, cand: PolicyProfile) -> list[GoldenImpact]:
    """Check each golden-pinned artefact by recomputation over its underlying corpus."""
    impacts: list[GoldenImpact] = []

    outcome_backed = (
        ("outcome_reliability.golden.json", default_outcome_corpus()),
        ("labelled_outcome_reliability.golden.json", default_labelled_outcome_corpus()),
        ("cv_gain_inference.golden.json", default_external_outcome_corpus()),
        ("disagreement_diagnosis.golden.json", default_external_outcome_corpus()),
        ("fitted_policy.golden.json", generate_outcome_corpus(n=60, seed=0)),
        ("cross_validated_fit.golden.json", generate_outcome_corpus(n=40, seed=0)),
    )
    for golden, corpus in outcome_backed:
        flips = _outcome_flip_count(corpus, base, cand)
        impacts.append(
            GoldenImpact(
                golden=golden,
                would_break=flips > 0,
                reason=(
                    f"{flips} verdict(s) change on its corpus under the modified "
                    f"'{base.mode.value}'"
                    if flips
                    else "no verdict changes on its corpus"
                ),
            )
        )

    for golden, corpus in (
        ("scoring_corpus.golden.json", default_scoring_corpus()),
        ("scoring_generated.golden.json", generate_scoring_corpus(n=120, seed=0)),
    ):
        changed = _scoring_changes(corpus, base, cand)
        impacts.append(
            GoldenImpact(
                golden=golden,
                would_break=changed > 0,
                reason=(
                    f"{changed} case(s) change verdict or coercion-detector band"
                    if changed
                    else "no verdict or detector-band changes"
                ),
            )
        )

    audit_changed = _audit_changes(base, cand)
    impacts.append(
        GoldenImpact(
            golden="audit_corpus.golden.json",
            would_break=audit_changed > 0,
            reason=(
                f"{audit_changed} audit output(s) change (the audit reads coercion_moderate)"
                if audit_changed
                else "no audit outputs change"
            ),
        )
    )

    impacts.append(
        GoldenImpact(
            golden="disagreement_explanation.golden.json",
            checked=False,
            would_break=False,
            reason="depends on a repository example case, not packaged data; run pytest to check",
        )
    )
    return impacts


def tune_dry_run(
    corpus: OutcomeCorpus,
    changes: dict[str, object],
    *,
    base_policy: PolicyMode | PolicyProfile | str = "standard",
    check_goldens: bool = True,
) -> TuningImpact:
    """Report the full before/after impact of a candidate parameter change. Dry run.

    Evaluates every corpus case under the base and the candidate profile, lists
    every verdict flip, recomputes agreement with every labeller (and the
    consensus) per split, and -- unless ``check_goldens=False`` -- checks every
    golden-pinned artefact for breakage by recomputation. The built-in profiles
    are never modified.
    """
    if not changes:
        raise ValueError("no changes given; pass at least one parameter=value override")
    base = get_policy(base_policy)
    cand = candidate_profile(base, changes)
    changed_params = {
        name: f"{getattr(base, name)!r} -> {getattr(cand, name)!r}"
        for name in PolicyProfile.model_fields
        if getattr(base, name) != getattr(cand, name)
    }

    entries = list(corpus.entries)
    cases = [e.case for e in entries]
    before = _verdicts(cases, base)
    after = _verdicts(cases, cand)

    flips = [
        CaseFlip(
            case_id=entry.id,
            split=entry.split,
            before=b,
            after=a,
            direction=_direction(b, a),
        )
        for entry, b, a in zip(entries, before, after, strict=True)
        if b != a
    ]
    flip_summary = dict(
        sorted(Counter(f"{f.before.value} -> {f.after.value}" for f in flips).items())
    )

    # agreement with every labeller (and the consensus), per split, before vs after
    labelers: list[str | None] = [None] + sorted(
        {lv.labeler for entry in entries for lv in entry.labels}
    )
    splits = sorted({entry.split for entry in entries})
    impacts: list[StakeholderImpact] = []
    net_deltas: dict[str, float] = {}
    for labeler in labelers:
        target = labeler or "consensus"

        def _label(entry, labeler=labeler):
            if labeler is None:
                return entry.human_verdict
            return next(
                (lv.verdict for lv in entry.labels if lv.labeler == labeler),
                entry.human_verdict,
            )

        total_before = total_after = 0
        for split in splits:
            idxs = [i for i, entry in enumerate(entries) if entry.split == split]
            n = len(idxs)
            b_exact = sum(1 for i in idxs if before[i] == _label(entries[i]))
            a_exact = sum(1 for i in idxs if after[i] == _label(entries[i]))
            b_disp = sum(
                1 for i in idxs if disposition(before[i]) == disposition(_label(entries[i]))
            )
            a_disp = sum(
                1 for i in idxs if disposition(after[i]) == disposition(_label(entries[i]))
            )
            total_before += b_exact
            total_after += a_exact
            impacts.append(
                StakeholderImpact(
                    target=target,
                    split=split,
                    n=n,
                    before_correct=b_exact,
                    after_correct=a_exact,
                    before_accuracy=round(b_exact / n, 4) if n else 0.0,
                    before_ci=wilson_ci(b_exact, n),
                    after_accuracy=round(a_exact / n, 4) if n else 0.0,
                    after_ci=wilson_ci(a_exact, n),
                    delta=round((a_exact - b_exact) / n, 4) if n else 0.0,
                    before_disposition_accuracy=round(b_disp / n, 4) if n else 0.0,
                    after_disposition_accuracy=round(a_disp / n, 4) if n else 0.0,
                    disposition_delta=round((a_disp - b_disp) / n, 4) if n else 0.0,
                )
            )
        net_deltas[target] = round((total_after - total_before) / len(entries), 4)

    golden_impacts = _golden_impacts(base, cand) if check_goldens else []

    gains = [t for t, d in net_deltas.items() if d > 0]
    losses = [t for t, d in net_deltas.items() if d < 0]
    notes = [
        "DRY RUN: the built-in profiles are untouched; this report says what WOULD change",
        f"{len(flips)} of {len(entries)} verdicts flip under the candidate",
    ]
    if gains:
        notes.append("net agreement rises for: " + ", ".join(gains))
    if losses:
        notes.append(
            "net agreement falls for: " + ", ".join(losses) + " -- the cost of this change, stated"
        )
    if not gains and not losses:
        notes.append("net agreement is unchanged for every stakeholder")
    if check_goldens:
        broken = [gi.golden for gi in golden_impacts if gi.would_break]
        notes.append(
            "if adopted, golden files to regenerate deliberately: " + ", ".join(broken)
            if broken
            else "no checked golden file would break"
        )
        notes.append(
            "fitting goldens derive candidate grids from the base profile; a base change can "
            "affect them even without verdict flips -- run pytest to be certain"
        )
    notes.append(
        "an improvement in agreement is not by itself a justification: a gate that declines "
        "to judge on poor data may be doing its epistemic job (see docs/CALIBRATION.md)"
    )

    return TuningImpact(
        base_policy=base.mode.value,
        changes=changed_params,
        corpus_title=corpus.title,
        n_cases=len(entries),
        n_flips=len(flips),
        flips=flips,
        flip_summary=flip_summary,
        stakeholder_impacts=impacts,
        net_deltas=net_deltas,
        golden_impacts=golden_impacts,
        notes=notes,
    )


def tuning_golden_payload(impact: TuningImpact) -> dict:
    """The stable digest of one tuning impact, for golden-file regression."""
    return impact.model_dump(mode="json")
