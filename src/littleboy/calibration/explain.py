"""Case-level explanation of disagreements: the minimal difference, made inspectable.

A reliability table says *how often* the engine disagrees with a labeller; this
module says *why*, case by case, building on the existing ``ReasoningTrace`` (it
re-derives nothing). Two kinds of explanation:

- **policy-vs-policy** -- both sides are engine evaluations, so a true diff exists:
  which rules changed outcome (``TraceDelta``), which policy-independent score
  crossed a threshold under one policy only (``ThresholdFlip``), and -- the rigorous
  part -- the **minimal parameter account**: the smallest set(s) of policy
  parameters that, moved from side A's values to side B's, make the engine produce
  side B's verdict. Every account is engine-verified (the hybrid profile is
  actually evaluated), exactly like the deliberation layer's minimal flip sets but
  over policy parameters instead of facts.
- **engine-vs-label** -- the human side has no trace, so the honest explanation is
  the engine's decisive factors plus the two possible *routes to agreement*, both
  engine-verified: the **policy route** (which built-in policies agree with the
  label; the parameter account toward the nearest one, the *bridge*) and the
  **fact route** (``minimal_fact_accounts``: the smallest resolutions of the
  case's genuine unknowns -- via the deliberation layer's probes -- that make the
  engine produce the label's verdict exactly). ``bridge_classification`` names
  what exists: ``policy-bridgeable`` / ``fact-bridgeable`` / ``both`` /
  ``neither`` -- the ``neither`` cases are the ones worth a human look.

Deterministic, typed, evaluation-only: nothing here changes any verdict.
"""

from __future__ import annotations

from itertools import combinations, product

from littleboy.calibration.models import (
    DisagreementExplanation,
    OutcomeCorpus,
    OutcomeEntry,
    ThresholdFlip,
    TraceDelta,
)
from littleboy.calibration.reliability import disposition
from littleboy.core.enums import PolicyMode, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase, EvaluationReport, RuleResult
from littleboy.deliberation.voi import build_probe_specs
from littleboy.rules.policy import PolicyProfile, get_policy

_PARAM_FIELDS: tuple[str, ...] = tuple(PolicyProfile.model_fields.keys())

# (score field on the report, threshold field on the profile); these scores are
# computed before any policy applies, so the value is identical on both sides.
_THRESHOLD_PAIRS: tuple[tuple[str, str], ...] = (
    ("coercion_score", "coercion_moderate"),
    ("coercion_score", "max_coercion_for_acceptable"),
    ("data_quality_score", "min_data_quality_for_approval"),
    ("data_quality_score", "data_quality_good"),
    ("evidence_score", "min_evidence_quality_for_approval"),
)

_MODES = tuple(PolicyMode)


def _param_repr(value: object) -> str:
    return value.value if isinstance(value, PolicyMode) else repr(value)


def _differing_params(a: PolicyProfile, b: PolicyProfile) -> list[str]:
    return [f for f in _PARAM_FIELDS if getattr(a, f) != getattr(b, f)]


def _parameter_changes(a: PolicyProfile, b: PolicyProfile) -> dict[str, str]:
    return {
        f: f"{_param_repr(getattr(a, f))} -> {_param_repr(getattr(b, f))}"
        for f in _differing_params(a, b)
    }


def minimal_policy_accounts(
    case: ActionCase,
    policy_a: PolicyMode | PolicyProfile | str,
    policy_b: PolicyMode | PolicyProfile | str,
    *,
    max_size: int = 3,
    max_accounts: int = 8,
) -> list[list[str]]:
    """The smallest sets of policy parameters that flip A's verdict to B's.

    Searches subsets of the differing parameters in increasing size and stops at
    the first size with hits, so every returned set is minimal (no smaller subset
    flips at all). Each candidate is verified by actually evaluating the hybrid
    profile -- nothing is inferred from the trace. Returns ``[]`` if the two
    policies already agree, or if no account exists within ``max_size`` (the full
    differing set always reproduces B's verdict by construction).
    """
    profile_a = get_policy(policy_a)
    profile_b = get_policy(policy_b)
    verdict_a = EthicalEvaluator(profile_a).evaluate(case).verdict
    verdict_b = EthicalEvaluator(profile_b).evaluate(case).verdict
    if verdict_a == verdict_b:
        return []
    diffs = _differing_params(profile_a, profile_b)
    for size in range(1, min(max_size, len(diffs)) + 1):
        hits: list[list[str]] = []
        for combo in combinations(diffs, size):
            hybrid = profile_a.model_copy(update={f: getattr(profile_b, f) for f in combo})
            if EthicalEvaluator(hybrid).evaluate(case).verdict == verdict_b:
                hits.append(list(combo))
                if len(hits) >= max_accounts:
                    break
        if hits:
            return hits
    return []


def minimal_fact_accounts(
    case: ActionCase,
    policy: PolicyMode | PolicyProfile | str,
    target: Verdict,
    *,
    max_size: int = 2,
    max_accounts: int = 8,
) -> list[list[str]]:
    """The smallest joint fact resolutions that make the engine produce ``target`` exactly.

    The unknowns and their candidate resolutions come from the deliberation
    layer's probes (``build_probe_specs`` -- only genuine unknowns get probes), so
    this is the targeted counterpart of a minimal flip set: instead of flipping to
    *any* other verdict, the joint resolution must land on the labeller's verdict.
    Each account is a list of self-describing resolution labels (e.g.
    ``'consent = REFUSED'``), verified by actually re-evaluating the transformed
    case, and minimal by increasing-size search.
    Returns ``[]`` when the engine already agrees, the case has no genuine
    unknowns, or no account exists within ``max_size``.
    """
    evaluator = EthicalEvaluator(get_policy(policy))
    if evaluator.evaluate(case).verdict == target:
        return []
    specs = build_probe_specs(case)
    if not specs:
        return []
    for size in range(1, min(max_size, len(specs)) + 1):
        hits: list[list[str]] = []
        for combo in combinations(range(len(specs)), size):
            for choice in product(*(specs[i].resolutions for i in combo)):
                resolved = case
                for _label, transform in choice:
                    resolved = transform(resolved)
                if evaluator.evaluate(resolved).verdict == target:
                    # the probe labels are already self-describing ('consent = REFUSED',
                    # 'long-term consequences are benign', ...)
                    hits.append([label for label, _t in choice])
                    break  # the first satisfying joint resolution accounts for this combo
            if len(hits) >= max_accounts:
                break
        if hits:
            return hits
    return []


def _decisive_factors(report: EvaluationReport) -> list[str]:
    """The trace elements that pinned this verdict (blockers, caps, downgrades, the gate)."""
    trace = report.reasoning_trace
    if trace is None:
        return []
    out: list[str] = []
    for rr in trace.applied:
        if rr.rule_id in trace.blockers:
            out.append(f"{rr.rule_id} {rr.name} [blocker]: {rr.message}")
        elif rr.verdict_cap is not None:
            out.append(f"{rr.rule_id} {rr.name} [cap -> {rr.verdict_cap.value}]: {rr.message}")
        elif rr.verdict_delta > 0:
            out.append(f"{rr.rule_id} {rr.name} [downgrade x{rr.verdict_delta}]: {rr.message}")
    for contradiction in trace.contradictions:
        out.append(f"contradiction flagged: {contradiction}")
    if report.verdict == Verdict.INSUFFICIENT_DATA and report.missing_data:
        out.append("data gate: missing " + "; ".join(report.missing_data[:4]))
    return out


def _rule_outcome(rr: RuleResult | None, blocker: bool) -> tuple:
    """(status, severity, blocker, verdict_delta, verdict_cap); absent rules read as skipped."""
    if rr is None:
        return ("skipped", "info", False, 0, None)
    return (rr.status.value, rr.severity.value, blocker, rr.verdict_delta, rr.verdict_cap)


def _trace_deltas(report_a: EvaluationReport, report_b: EvaluationReport) -> list[TraceDelta]:
    """Rules whose *outcome* differs between the two evaluations (messages alone never count)."""
    trace_a, trace_b = report_a.reasoning_trace, report_b.reasoning_trace
    if trace_a is None or trace_b is None:
        return []
    by_id_a = {rr.rule_id: rr for rr in trace_a.applied}
    by_id_b = {rr.rule_id: rr for rr in trace_b.applied}
    deltas: list[TraceDelta] = []
    for rule_id in sorted(by_id_a.keys() | by_id_b.keys()):
        ra = by_id_a.get(rule_id)
        rb = by_id_b.get(rule_id)
        outcome_a = _rule_outcome(ra, rule_id in trace_a.blockers)
        outcome_b = _rule_outcome(rb, rule_id in trace_b.blockers)
        if outcome_a == outcome_b:
            continue
        deltas.append(
            TraceDelta(
                rule_id=rule_id,
                name=(ra.name if ra else "") or (rb.name if rb else ""),
                status_a=outcome_a[0],
                status_b=outcome_b[0],
                severity_a=outcome_a[1],
                severity_b=outcome_b[1],
                blocker_a=outcome_a[2],
                blocker_b=outcome_b[2],
                verdict_delta_a=outcome_a[3],
                verdict_delta_b=outcome_b[3],
                verdict_cap_a=outcome_a[4].value if outcome_a[4] else None,
                verdict_cap_b=outcome_b[4].value if outcome_b[4] else None,
                message_a=ra.message if ra else "",
                message_b=rb.message if rb else "",
            )
        )
    return deltas


def _threshold_flips(
    report: EvaluationReport, profile_a: PolicyProfile, profile_b: PolicyProfile
) -> list[ThresholdFlip]:
    """Policy-independent scores that cross a threshold under exactly one of the policies."""
    flips: list[ThresholdFlip] = []
    for quantity, threshold in _THRESHOLD_PAIRS:
        value = getattr(report, quantity)
        limit_a = getattr(profile_a, threshold)
        limit_b = getattr(profile_b, threshold)
        crossed_a = value >= limit_a
        crossed_b = value >= limit_b
        if crossed_a != crossed_b:
            flips.append(
                ThresholdFlip(
                    quantity=quantity,
                    value=round(value, 4),
                    threshold=threshold,
                    limit_a=limit_a,
                    limit_b=limit_b,
                    crossed_a=crossed_a,
                    crossed_b=crossed_b,
                )
            )
    return flips


def explain_policy_disagreement(
    case: ActionCase,
    policy_a: PolicyMode | PolicyProfile | str,
    policy_b: PolicyMode | PolicyProfile | str,
    *,
    case_id: str = "",
    max_size: int = 3,
    label_a: str = "",
    label_b: str = "",
) -> DisagreementExplanation:
    """Diff two policies' evaluations of one case down to the minimal account.

    ``label_a`` / ``label_b`` name custom profiles in the output (named policies
    are never displayed as their base mode).
    """
    profile_a = get_policy(policy_a)
    profile_b = get_policy(policy_b)
    display_a = label_a or profile_a.mode.value
    display_b = label_b or profile_b.mode.value
    report_a = EthicalEvaluator(profile_a).evaluate(case)
    report_b = EthicalEvaluator(profile_b).evaluate(case)
    agree = report_a.verdict == report_b.verdict
    accounts = (
        [] if agree else minimal_policy_accounts(case, profile_a, profile_b, max_size=max_size)
    )
    notes: list[str] = []
    if agree:
        notes.append("no disagreement: both policies reach the same verdict on this case")
    elif accounts:
        notes.append(
            f"minimal account verified by re-evaluation: changing {len(accounts[0])} "
            f"parameter(s) of '{display_a}' to '{display_b}' values "
            "reproduces the other verdict; no smaller change does"
        )
    else:
        notes.append(
            f"no parameter account of size <= {max_size}; the divergence needs a larger "
            f"combination (the full set of {len(_differing_params(profile_a, profile_b))} "
            "differing parameters reproduces it by construction)"
        )
    return DisagreementExplanation(
        case_id=case_id,
        kind="policy-vs-policy",
        side_a=display_a,
        side_b=display_b,
        verdict_a=report_a.verdict,
        verdict_b=report_b.verdict,
        disposition_a=disposition(report_a.verdict),
        disposition_b=disposition(report_b.verdict),
        agree=agree,
        coercion_score=round(report_a.coercion_score, 4),
        data_quality_score=round(report_a.data_quality_score, 4),
        evidence_score=round(report_a.evidence_score, 4),
        confidence_a=round(report_a.confidence, 4),
        confidence_b=round(report_b.confidence, 4),
        engine_decisive=_decisive_factors(report_a),
        other_decisive=_decisive_factors(report_b),
        agreeing_policies_exact=[],
        agreeing_policies_disposition=[],
        minimal_parameter_accounts=accounts,
        parameter_changes=_parameter_changes(profile_a, profile_b),
        trace_deltas=_trace_deltas(report_a, report_b),
        threshold_flips=_threshold_flips(report_a, profile_a, profile_b),
        notes=notes,
    )


def _label_of(entry: OutcomeEntry, labeler: str | None) -> Verdict:
    if labeler is None or labeler == "consensus":
        return entry.human_verdict
    for lv in entry.labels:
        if lv.labeler == labeler:
            return lv.verdict
    known = ", ".join(sorted({lv.labeler for lv in entry.labels})) or "none"
    raise ValueError(f"no label by {labeler!r} on case {entry.id!r} (labelers: {known})")


def explain_label_disagreement(
    entry: OutcomeEntry,
    labeler: str | None = None,
    *,
    policy: PolicyMode | PolicyProfile | str = "standard",
    policy_label: str = "",
    max_size: int = 3,
    max_fact_size: int = 2,
) -> DisagreementExplanation:
    """Explain why the engine's verdict diverges from one labeller's (or the consensus).

    The human side has no trace, so the explanation gives the engine's decisive
    factors and then the two possible routes to agreement, both engine-verified:
    the **policy route** (the nearest built-in policy that agrees with the label,
    with the minimal parameter account toward it) and the **fact route** (the
    smallest fact resolutions that make the engine produce the label's verdict).
    ``bridge_classification`` says which routes exist: 'policy-bridgeable',
    'fact-bridgeable', 'both', or 'neither' -- the 'neither' cases are the ones
    worth a human look.
    """
    label = _label_of(entry, labeler)
    profile = get_policy(policy)
    report = EthicalEvaluator(profile).evaluate(entry.case)
    agree = report.verdict == label

    by_mode = {m: EthicalEvaluator(m).evaluate(entry.case).verdict for m in _MODES}
    exact = [m for m in _MODES if by_mode[m] == label]
    disp_only = [
        m for m in _MODES if disposition(by_mode[m]) == disposition(label) and by_mode[m] != label
    ]

    bridge: PolicyMode | None = None
    accounts: list[list[str]] = []
    fact_accounts: list[list[str]] = []
    trace_deltas: list[TraceDelta] = []
    flips: list[ThresholdFlip] = []
    notes: list[str] = []
    target_name = labeler or "consensus"

    if not agree:
        fact_accounts = minimal_fact_accounts(entry.case, profile, label, max_size=max_fact_size)

    if agree:
        notes.append(f"no disagreement: the engine matches {target_name}'s verdict")
    elif exact or (disposition(report.verdict) != disposition(label) and disp_only):
        candidates = exact or disp_only
        bridge = min(
            candidates,
            key=lambda m: (
                len(_differing_params(profile, get_policy(m))),
                _MODES.index(m),
            ),
        )
        bridge_profile = get_policy(bridge)
        bridge_report = EthicalEvaluator(bridge_profile).evaluate(entry.case)
        accounts = minimal_policy_accounts(entry.case, profile, bridge_profile, max_size=max_size)
        trace_deltas = _trace_deltas(report, bridge_report)
        flips = _threshold_flips(report, profile, bridge_profile)
        if bridge in exact:
            notes.append(
                f"'{bridge.value}' reproduces {target_name}'s verdict exactly; the "
                "parameter account shows the smallest policy change that aligns the engine"
            )
        else:
            notes.append(
                f"no built-in policy reproduces {target_name}'s exact verdict; "
                f"'{bridge.value}' matches its disposition "
                f"({disposition(label)}), so the account aligns disposition only"
            )
    elif disposition(report.verdict) == disposition(label):
        notes.append(
            f"within-disposition disagreement: the engine already matches {target_name}'s "
            f"disposition ({disposition(label)}) and no built-in policy reproduces the exact "
            "verdict -- the difference is in degree, not in kind"
        )
    else:
        notes.append(
            f"no built-in policy agrees with {target_name} even on disposition: this "
            "disagreement is not a threshold question within the built-in policy family"
        )

    classification = ""
    if not agree:
        policy_route = bool(exact)
        fact_route = bool(fact_accounts)
        if policy_route and fact_route:
            classification = "both"
        elif policy_route:
            classification = "policy-bridgeable"
        elif fact_route:
            classification = "fact-bridgeable"
        else:
            classification = "neither"
        if fact_route:
            notes.append(
                f"fact route (verified by re-evaluation): resolving "
                f"{'; '.join(fact_accounts[0])} makes the engine produce {target_name}'s "
                "verdict exactly"
            )
        if classification == "both":
            notes.append(
                "two routes to agreement: change the policy (parameter account) or establish "
                "the facts (fact account) -- which is right depends on whether the labeller "
                "weighs values differently or knows something the case does not state"
            )
        elif classification == "neither":
            notes.append(
                "neither a policy parameter nor a fact resolution (within search limits) "
                "aligns the engine with this label -- worth a human look"
            )

    return DisagreementExplanation(
        case_id=entry.id,
        kind="engine-vs-label",
        side_a=f"engine[{policy_label or profile.mode.value}]",
        side_b=f"label[{target_name}]",
        verdict_a=report.verdict,
        verdict_b=label,
        disposition_a=disposition(report.verdict),
        disposition_b=disposition(label),
        agree=agree,
        coercion_score=round(report.coercion_score, 4),
        data_quality_score=round(report.data_quality_score, 4),
        evidence_score=round(report.evidence_score, 4),
        confidence_a=round(report.confidence, 4),
        confidence_b=None,
        engine_decisive=_decisive_factors(report),
        other_decisive=[],
        bridge_policy=bridge.value if bridge is not None else None,
        agreeing_policies_exact=[m.value for m in exact],
        agreeing_policies_disposition=[m.value for m in disp_only],
        minimal_parameter_accounts=accounts,
        parameter_changes=(
            _parameter_changes(profile, get_policy(bridge)) if bridge is not None else {}
        ),
        minimal_fact_accounts=fact_accounts,
        bridge_classification=classification,
        trace_deltas=trace_deltas,
        threshold_flips=flips,
        notes=notes,
    )


def explain_reliability_disagreements(
    corpus: OutcomeCorpus,
    labeler: str | None = None,
    *,
    policy: PolicyMode | PolicyProfile | str = "standard",
    policy_label: str = "",
    split: str | None = None,
    max_size: int = 2,
    max_fact_size: int = 2,
) -> list[DisagreementExplanation]:
    """Explain every engine-vs-label disagreement behind a reliability table.

    One explanation per corpus case where the engine's verdict (under ``policy``)
    differs from the labeller's, in corpus order -- the inspectable counterpart of
    ``PolicyReliability.disagreements``. ``split`` restricts to one split.
    """
    out: list[DisagreementExplanation] = []
    for entry in corpus.entries:
        if split is not None and entry.split != split:
            continue
        explanation = explain_label_disagreement(
            entry,
            labeler,
            policy=policy,
            policy_label=policy_label,
            max_size=max_size,
            max_fact_size=max_fact_size,
        )
        if not explanation.agree:
            out.append(explanation)
    return out


def explanation_golden_payload(explanation: DisagreementExplanation) -> dict:
    """The stable digest of one explanation, for golden-file regression."""
    return explanation.model_dump(mode="json")
