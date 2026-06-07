"""Value of information: which unknowns would change the verdict?

Two questions, both answered by re-running the **deterministic** evaluator under
explicit counterfactual resolutions (no probabilities invented):

1. *Single-fact* VoI (v0.9): for each unknown on its own, how far does resolving
   it move the verdict and confidence?
2. *Multi-fact* VoI (v0.10): what is the **smallest combination** of unknowns
   that, jointly resolved, would change the verdict? Some verdicts survive every
   single resolution yet flip when two facts move together.

A "probe" is one unknown plus the concrete resolutions to try, each expressed as
a *transform* ``case -> case`` so that resolutions of different unknowns can be
**composed** to test combinations. Probes only fire when the fact is genuinely
unknown, so a fully-specified case yields no probes (and is verdict-robust).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations, product
from typing import TYPE_CHECKING

from littleboy.core.enums import (
    AgentType,
    ConsentStatus,
    EpistemicStatus,
    TimeHorizon,
    Verdict,
)
from littleboy.core.models import (
    ActionCase,
    AlternativeAction,
    DataQualityProfile,
    MoralAgent,
)
from littleboy.deliberation.models import (
    ComparisonInformationValue,
    ComparisonResolutionOutcome,
    FactResolution,
    InformationValue,
    MinimalFlipSet,
    ResolutionOutcome,
)
from littleboy.temporal.models import ConsequenceEstimate, ConsequenceSet

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.comparison.engine import ComparisonEngine
    from littleboy.comparison.models import ActionComparisonSet
    from littleboy.core.evaluator import EthicalEvaluator

# Verdict ordering for measuring how far a verdict moved (INSUFFICIENT_DATA stands apart).
_VERDICT_ORDER = {
    Verdict.ACCEPTABLE: 0,
    Verdict.ACCEPTABLE_WITH_RESERVATIONS: 1,
    Verdict.ETHICALLY_SUSPICIOUS: 2,
    Verdict.NOT_ACCEPTABLE: 3,
}


def verdict_distance(base: Verdict, other: Verdict) -> float:
    """A 0..1 distance between two verdicts (resolving the data gate counts as 1.0)."""
    if base == other:
        return 0.0
    if base == Verdict.INSUFFICIENT_DATA or other == Verdict.INSUFFICIENT_DATA:
        return 1.0
    return abs(_VERDICT_ORDER[base] - _VERDICT_ORDER[other]) / 3.0


# =============================================================================
# Probe construction (transform-based, so resolutions can be composed)
# =============================================================================

_Transform = Callable[[ActionCase], ActionCase]


@dataclass(frozen=True)
class ProbeSpec:
    """One unknown plus the concrete resolutions to try, each a ``case -> case`` transform."""

    field: str
    question: str
    why: str
    axioms: tuple[str, ...]
    resolutions: tuple[tuple[str, _Transform], ...]


def _set_agent_type(case: ActionCase, agent_type: AgentType) -> ActionCase:
    base = case.acting_agent or MoralAgent(name="acting agent")
    return case.model_copy(
        update={"acting_agent": base.model_copy(update={"agent_type": agent_type})}
    )


def _set_consent(case: ActionCase, status: ConsentStatus) -> ActionCase:
    if case.consent_profile is not None:
        return case.model_copy(
            update={"consent_profile": case.consent_profile.model_copy(update={"status": status})}
        )
    return case.model_copy(update={"consent": status})


def _set_reversibility(case: ActionCase, value: float) -> ActionCase:
    cp = case.coercion_profile.model_copy(update={"reversibility": value})
    return case.model_copy(update={"coercion_profile": cp})


def _set_alternatives(case: ActionCase, alts: list[AlternativeAction]) -> ActionCase:
    return case.model_copy(update={"available_alternatives": alts})


def _set_data_quality(case: ActionCase, dq: DataQualityProfile) -> ActionCase:
    return case.model_copy(update={"data_quality": dq})


def _set_consequences(case: ActionCase, cs: ConsequenceSet) -> ActionCase:
    return case.model_copy(update={"consequences": cs})


def _set_justification(case: ActionCase, **updates) -> ActionCase:
    return case.model_copy(update={"justification": case.justification.model_copy(update=updates)})


_GOOD_DATA = DataQualityProfile(
    completeness=0.85,
    source_reliability=0.85,
    specificity=0.85,
    recency=0.85,
    corroboration=0.8,
    ambiguity=0.15,
)
_FEASIBLE_ALT = AlternativeAction(
    title="a feasible, clearly less-coercive option",
    estimated_coercion_score=0.05,
    feasibility=1.0,
)
_WORSE_FUTURE = ConsequenceSet(
    consequences=[
        ConsequenceEstimate(
            description="coercion grows and entrenches over the long term",
            horizon=TimeHorizon.LONG_TERM,
            coercion_delta=0.7,
            severity=0.7,
            probability=0.8,
            confidence=0.7,
            reversibility=0.3,
            evidence_quality=0.6,
        )
    ]
)
_BENIGN_FUTURE = ConsequenceSet(
    consequences=[
        ConsequenceEstimate(
            description="the coercion winds down on its own",
            horizon=TimeHorizon.LONG_TERM,
            coercion_delta=-0.3,
            severity=0.3,
            probability=0.7,
            confidence=0.7,
            reversibility=0.9,
            evidence_quality=0.6,
        )
    ]
)

_JUSTIFICATION_CONDITIONS = (
    "responds_to_existing_or_imminent_coercion",
    "no_less_coercive_alternative_available",
    "necessity",
    "proportionality",
    "cessation_condition_defined",
    "reversibility",
)


def build_probe_specs(case: ActionCase) -> list[ProbeSpec]:
    """Return the applicable counterfactual probes for a case's genuine unknowns."""
    specs: list[ProbeSpec] = []

    if case.effective_agent_type() is None:
        specs.append(
            ProbeSpec(
                "acting_agent.agent_type",
                "Is the acting agent a Type II (duty-bearing) agent?",
                "Duties bind only Type II agents (A4); the type changes whether the action is "
                "morally evaluable at all.",
                ("A4",),
                (
                    (
                        "acting agent is Type II (duty-bearing)",
                        lambda c: _set_agent_type(c, AgentType.TYPE_II),
                    ),
                    (
                        "acting agent is Type I (cannot bear duties)",
                        lambda c: _set_agent_type(c, AgentType.TYPE_I),
                    ),
                ),
            )
        )

    if case.effective_consent_status() == ConsentStatus.UNKNOWN:
        specs.append(
            ProbeSpec(
                "consent",
                "Did the affected agent give, or refuse, valid consent?",
                "Consent bears directly on coercion (A0/A2): refusal makes the action "
                "presumptively coercive, while valid consent supports it.",
                ("A0", "A2"),
                (
                    ("consent = GIVEN", lambda c: _set_consent(c, ConsentStatus.GIVEN)),
                    ("consent = REFUSED", lambda c: _set_consent(c, ConsentStatus.REFUSED)),
                ),
            )
        )

    cp = case.coercion_profile
    if cp is not None and not cp.reversibility_is_known:
        specs.append(
            ProbeSpec(
                "coercion.reversibility",
                "Is the coercion reversible, and at what cost?",
                "Irreversibility raises the evidential bar (A3/A5) and, on weak data, can block "
                "approval.",
                ("A3", "A5"),
                (
                    ("coercion is fully reversible (1.0)", lambda c: _set_reversibility(c, 1.0)),
                    ("coercion is irreversible (0.0)", lambda c: _set_reversibility(c, 0.0)),
                ),
            )
        )

    if case.available_alternatives is None:
        specs.append(
            ProbeSpec(
                "available_alternatives",
                "Was there a feasible, less-coercive alternative?",
                "Axiom 2 requires the least-coercive feasible path; a feasible less-coercive "
                "option downgrades the verdict.",
                ("A2",),
                (
                    (
                        "a feasible less-coercive alternative exists",
                        lambda c: _set_alternatives(c, [_FEASIBLE_ALT]),
                    ),
                    ("no less-coercive alternative exists", lambda c: _set_alternatives(c, [])),
                ),
            )
        )

    if case.data_quality is None and case.evidence is None:
        specs.append(
            ProbeSpec(
                "data_quality",
                "Is the underlying information complete, reliable, and corroborated?",
                "A confident verdict requires an adequate epistemic basis (A5); missing data can "
                "force INSUFFICIENT_DATA.",
                ("A5",),
                (
                    (
                        "the information is complete, reliable, and corroborated",
                        lambda c: _set_data_quality(c, _GOOD_DATA),
                    ),
                ),
            )
        )

    j = case.justification
    if j is not None and any(getattr(j, c).is_unresolved for c in _JUSTIFICATION_CONDITIONS):
        confirmed = {c: EpistemicStatus.CONFIRMED for c in _JUSTIFICATION_CONDITIONS}
        if j.expected_total_coercion_reduction is None or j.expected_total_coercion_reduction <= 0:
            confirmed["expected_total_coercion_reduction"] = 0.6
        refuted = {
            "necessity": EpistemicStatus.DISPUTED,
            "no_less_coercive_alternative_available": EpistemicStatus.DISPUTED,
            "expected_total_coercion_reduction": -0.2,
        }
        specs.append(
            ProbeSpec(
                "justification",
                "Are all six Axiom 3 conditions for justified coercion established?",
                "Coercion is justified only if every A3 condition holds; resolving them can flip "
                "a coercive action between acceptable and not.",
                ("A3",),
                (
                    (
                        "the Axiom 3 justification is fully established",
                        lambda c: _set_justification(c, **confirmed),
                    ),
                    ("the Axiom 3 justification fails", lambda c: _set_justification(c, **refuted)),
                ),
            )
        )

    if cp is not None and case.consequences is None and case.temporal_profile is None:
        specs.append(
            ProbeSpec(
                "consequences",
                "What are the medium and long-term consequences?",
                "An action can look acceptable now yet accumulate hidden, delayed, or cumulative "
                "coercion later (temporal instability).",
                ("A2",),
                (
                    (
                        "long-term consequences are worse than described",
                        lambda c: _set_consequences(c, _WORSE_FUTURE),
                    ),
                    (
                        "long-term consequences are benign",
                        lambda c: _set_consequences(c, _BENIGN_FUTURE),
                    ),
                ),
            )
        )

    return specs


# A probe tuple, kept for callers that want pre-built mutated cases.
_Probe = tuple[str, str, str, list[str], list[tuple[str, ActionCase]]]


def build_probes(case: ActionCase) -> list[_Probe]:
    """Return probes as ``(field, question, why, axioms, [(label, mutated_case), ...])``."""
    out: list[_Probe] = []
    for spec in build_probe_specs(case):
        muts = [(label, transform(case)) for label, transform in spec.resolutions]
        out.append((spec.field, spec.question, spec.why, list(spec.axioms), muts))
    return out


# =============================================================================
# Single-fact value of information
# =============================================================================


def _swing_summary(base_verdict: Verdict, resolutions: list[ResolutionOutcome]) -> str:
    verdicts = {r.verdict for r in resolutions}
    if verdicts == {base_verdict}:
        confs = [r.confidence for r in resolutions]
        spread = max(confs) - min(confs) if confs else 0.0
        return f"verdict stays {base_verdict.value}; confidence varies by {spread:.2f}"
    others = " / ".join(sorted({r.verdict.value for r in resolutions if r.verdict != base_verdict}))
    return f"verdict can move from {base_verdict.value} to {others} depending on the resolution"


def value_of_information(case: ActionCase, evaluator: EthicalEvaluator) -> list[InformationValue]:
    """Rank the case's unknowns by how much resolving each *alone* would change the verdict."""
    base = evaluator.evaluate(case)
    out: list[InformationValue] = []
    for spec in build_probe_specs(case):
        resolutions: list[ResolutionOutcome] = []
        max_vdist = 0.0
        max_cdist = 0.0
        changes = False
        for label, transform in spec.resolutions:
            r = evaluator.evaluate(transform(case))
            vd = verdict_distance(base.verdict, r.verdict)
            cd = abs(r.confidence - base.confidence)
            changed = r.verdict != base.verdict
            changes = changes or changed
            max_vdist = max(max_vdist, vd)
            max_cdist = max(max_cdist, cd)
            resolutions.append(
                ResolutionOutcome(
                    label=label,
                    verdict=r.verdict,
                    confidence=round(r.confidence, 4),
                    verdict_changed=changed,
                )
            )
        value = round(min(1.0, 0.7 * max_vdist + 0.3 * max_cdist), 4)
        out.append(
            InformationValue(
                field=spec.field,
                question=spec.question,
                why_it_matters=spec.why,
                value=value,
                changes_verdict=changes,
                swing=_swing_summary(base.verdict, resolutions),
                resolutions=resolutions,
                related_axioms=list(spec.axioms),
            )
        )
    out.sort(key=lambda iv: (iv.value, iv.changes_verdict), reverse=True)
    return out


# =============================================================================
# Multi-fact value of information: the smallest combination that flips the verdict
# =============================================================================


def _best_flip(case, evaluator, specs, combo, base_verdict):
    """Return ``(dist, verdict, labels)`` for the best flipping joint resolution of ``combo``.

    ``labels`` is the chosen resolution label per spec in ``combo`` order. Returns ``None`` if
    no joint resolution of these unknowns changes the verdict.
    """
    best: tuple[float, Verdict, tuple[str, ...]] | None = None
    for choice in product(*(specs[i].resolutions for i in combo)):
        mcase = case
        for _label, transform in choice:
            mcase = transform(mcase)
        result = evaluator.evaluate(mcase)
        if result.verdict != base_verdict:
            dist = verdict_distance(base_verdict, result.verdict)
            if best is None or dist > best[0]:
                best = (dist, result.verdict, tuple(label for label, _t in choice))
    return best


def _flip_set(specs, combo, k, dist, verdict, labels) -> MinimalFlipSet:
    return MinimalFlipSet(
        fields=[specs[i].field for i in combo],
        size=k,
        resolution=[
            FactResolution(field=specs[i].field, question=specs[i].question, label=label)
            for i, label in zip(combo, labels, strict=True)
        ],
        resulting_verdict=verdict,
        verdict_distance=round(dist, 4),
        note=(
            f"jointly resolving {', '.join(specs[i].field for i in combo)} "
            f"can move the verdict to {verdict.value}"
        ),
    )


def minimal_flip_sets(
    case: ActionCase, evaluator: EthicalEvaluator, *, max_size: int = 3
) -> tuple[list[MinimalFlipSet], int | None]:
    """Find the smallest combination(s) of unknowns whose joint resolution flips the verdict.

    Returns ``(flip_sets, smallest_size)``. Searches combinations of increasing size and stops
    at the first size that yields any flip, so every returned set is *minimal* (no proper subset
    flips the verdict). ``smallest_size`` is ``None`` when no combination up to ``max_size`` flips.
    """
    base_verdict = evaluator.evaluate(case).verdict
    specs = build_probe_specs(case)
    if not specs:
        return [], None

    upper = min(max_size, len(specs))
    for k in range(1, upper + 1):
        found: list[MinimalFlipSet] = []
        for combo in combinations(range(len(specs)), k):
            best = _best_flip(case, evaluator, specs, combo, base_verdict)
            if best is not None:
                found.append(_flip_set(specs, combo, k, *best))
        if found:
            found.sort(key=lambda fs: fs.verdict_distance, reverse=True)
            return found, k
    return [], None


def cheapest_flip_set(
    case: ActionCase,
    evaluator: EthicalEvaluator,
    *,
    cost: dict[str, float] | None = None,
    max_size: int = 3,
) -> tuple[MinimalFlipSet, float] | None:
    """Find the *cheapest* sufficient set of unknowns to resolve, by total answer cost.

    Unlike :func:`minimal_flip_sets` (smallest by cardinality), this searches all sufficient
    sets up to ``max_size`` and returns the one with the lowest total cost (ties broken by
    fewer fields, then by ``verdict_distance``). With uniform costs this reduces to the
    smallest set. Returns ``(flip_set, total_cost)`` or ``None`` if no set flips the verdict.
    """
    base_verdict = evaluator.evaluate(case).verdict
    specs = build_probe_specs(case)
    if not specs:
        return None
    costs = cost or {}

    upper = min(max_size, len(specs))
    best: tuple[tuple[float, int, float], MinimalFlipSet, float] | None = None
    for k in range(1, upper + 1):
        for combo in combinations(range(len(specs)), k):
            flip = _best_flip(case, evaluator, specs, combo, base_verdict)
            if flip is None:
                continue
            dist, verdict, labels = flip
            total = round(sum(costs.get(specs[i].field, 1.0) for i in combo), 4)
            key = (total, k, -dist)  # cheapest, then smallest, then most decisive
            if best is None or key < best[0]:
                best = (key, _flip_set(specs, combo, k, dist, verdict, labels), total)
    if best is None:
        return None
    return best[1], best[2]


# =============================================================================
# Comparison value of information
# =============================================================================


def comparison_value_of_information(
    comparison_set: ActionComparisonSet, engine: ComparisonEngine
) -> list[ComparisonInformationValue]:
    """Rank each option's unknowns by how much resolving them would change the winner."""
    base = engine.compare(comparison_set)
    base_best = base.best_option_id
    base_order = [e.option_id for e in base.ranking]
    options = list(comparison_set.options)
    out: list[ComparisonInformationValue] = []

    for idx, option in enumerate(options):
        for field, question, why, _axioms, muts in build_probes(option.case):
            resolutions: list[ComparisonResolutionOutcome] = []
            changes_best = False
            order_changed = False
            for label, mcase in muts:
                new_options = list(options)
                new_options[idx] = option.model_copy(update={"case": mcase})
                new_set = comparison_set.model_copy(update={"options": new_options})
                res = engine.compare(new_set)
                best_changed = res.best_option_id != base_best
                changes_best = changes_best or best_changed
                order_changed = order_changed or ([e.option_id for e in res.ranking] != base_order)
                resolutions.append(
                    ComparisonResolutionOutcome(
                        label=f"{option.option_id}: {label}",
                        best_option_id=res.best_option_id,
                        best_option_changed=best_changed,
                    )
                )
            if changes_best:
                value = 1.0
                swing = f"resolving this changes the winner away from '{base_best}'"
            elif order_changed:
                value = 0.4
                swing = "resolving this reorders the ranking but not the winner"
            else:
                value = 0.0
                swing = "resolving this does not change the ranking"
            out.append(
                ComparisonInformationValue(
                    option_id=option.option_id,
                    field=field,
                    question=question,
                    why_it_matters=why,
                    value=value,
                    changes_best_option=changes_best,
                    swing=swing,
                    resolutions=resolutions,
                )
            )
    out.sort(key=lambda iv: (iv.value, iv.changes_best_option), reverse=True)
    return out
