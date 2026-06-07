"""Value of information: which single unknown would most change the verdict?

The method is deliberately simple and fully auditable: for each thing LittleBoy
does not currently know, we *resolve it to each plausible value*, re-run the
**deterministic** evaluator, and measure how far the verdict and confidence move.
The unknown whose resolution moves the outcome most has the highest value of
information. No probabilities are invented and no model is consulted; every number
traces to an explicit counterfactual re-evaluation.

A "probe" is one unknown plus the concrete resolutions to try. Probes only fire
when the fact is genuinely unknown, so a fully-specified case yields no probes
(its verdict is already information-stable).
"""

from __future__ import annotations

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
    InformationValue,
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
# Probe construction
# =============================================================================

# A probe: (field, question, why_it_matters, axioms, [(label, mutated_case), ...]).
_Probe = tuple[str, str, str, list[str], list[tuple[str, ActionCase]]]


def _with_coercion(case: ActionCase, **updates) -> ActionCase:
    cp = case.coercion_profile.model_copy(update=updates)
    return case.model_copy(update={"coercion_profile": cp})


def _with_consent(case: ActionCase, status: ConsentStatus) -> ActionCase:
    if case.consent_profile is not None:
        cp = case.consent_profile.model_copy(update={"status": status})
        return case.model_copy(update={"consent_profile": cp})
    return case.model_copy(update={"consent": status})


def _probe_agent_type(case: ActionCase) -> _Probe | None:
    if case.effective_agent_type() is not None:
        return None
    base = case.acting_agent or MoralAgent(name="acting agent")
    muts = [
        (
            "acting agent is Type II (duty-bearing)",
            case.model_copy(
                update={"acting_agent": base.model_copy(update={"agent_type": AgentType.TYPE_II})}
            ),
        ),
        (
            "acting agent is Type I (cannot bear duties)",
            case.model_copy(
                update={"acting_agent": base.model_copy(update={"agent_type": AgentType.TYPE_I})}
            ),
        ),
    ]
    return (
        "acting_agent.agent_type",
        "Is the acting agent a Type II (duty-bearing) agent?",
        "Duties bind only Type II agents (A4); the type changes whether the action is morally "
        "evaluable at all.",
        ["A4"],
        muts,
    )


def _probe_consent(case: ActionCase) -> _Probe | None:
    if case.effective_consent_status() != ConsentStatus.UNKNOWN:
        return None
    muts = [
        ("consent = GIVEN", _with_consent(case, ConsentStatus.GIVEN)),
        ("consent = REFUSED", _with_consent(case, ConsentStatus.REFUSED)),
    ]
    return (
        "consent",
        "Did the affected agent give, or refuse, valid consent?",
        "Consent bears directly on coercion (A0/A2): refusal makes the action presumptively "
        "coercive, while valid consent supports it.",
        ["A0", "A2"],
        muts,
    )


def _probe_reversibility(case: ActionCase) -> _Probe | None:
    cp = case.coercion_profile
    if cp is None or cp.reversibility_is_known:
        return None
    muts = [
        ("coercion is fully reversible (1.0)", _with_coercion(case, reversibility=1.0)),
        ("coercion is irreversible (0.0)", _with_coercion(case, reversibility=0.0)),
    ]
    return (
        "coercion.reversibility",
        "Is the coercion reversible, and at what cost?",
        "Irreversibility raises the evidential bar (A3/A5) and, on weak data, can block approval.",
        ["A3", "A5"],
        muts,
    )


def _probe_alternatives(case: ActionCase) -> _Probe | None:
    if case.available_alternatives is not None:
        return None
    feasible = AlternativeAction(
        title="a feasible, clearly less-coercive option",
        estimated_coercion_score=0.05,
        feasibility=1.0,
    )
    muts = [
        (
            "a feasible less-coercive alternative exists",
            case.model_copy(update={"available_alternatives": [feasible]}),
        ),
        (
            "no less-coercive alternative exists",
            case.model_copy(update={"available_alternatives": []}),
        ),
    ]
    return (
        "available_alternatives",
        "Was there a feasible, less-coercive alternative?",
        "Axiom 2 requires the least-coercive feasible path; a feasible less-coercive option "
        "downgrades the verdict.",
        ["A2"],
        muts,
    )


def _probe_data_quality(case: ActionCase) -> _Probe | None:
    if case.data_quality is not None or case.evidence is not None:
        return None
    good = DataQualityProfile(
        completeness=0.85,
        source_reliability=0.85,
        specificity=0.85,
        recency=0.85,
        corroboration=0.8,
        ambiguity=0.15,
    )
    muts = [
        (
            "the information is complete, reliable, and corroborated",
            case.model_copy(update={"data_quality": good}),
        )
    ]
    return (
        "data_quality",
        "Is the underlying information complete, reliable, and corroborated?",
        "A confident verdict requires an adequate epistemic basis (A5); missing data can force "
        "INSUFFICIENT_DATA.",
        ["A5"],
        muts,
    )


_JUSTIFICATION_CONDITIONS = (
    "responds_to_existing_or_imminent_coercion",
    "no_less_coercive_alternative_available",
    "necessity",
    "proportionality",
    "cessation_condition_defined",
    "reversibility",
)


def _probe_justification(case: ActionCase) -> _Probe | None:
    j = case.justification
    if j is None:
        return None
    unresolved = [c for c in _JUSTIFICATION_CONDITIONS if getattr(j, c).is_unresolved]
    if not unresolved:
        return None
    confirmed_updates = {c: EpistemicStatus.CONFIRMED for c in _JUSTIFICATION_CONDITIONS}
    if j.expected_total_coercion_reduction is None or j.expected_total_coercion_reduction <= 0:
        confirmed_updates["expected_total_coercion_reduction"] = 0.6
    confirmed = j.model_copy(update=confirmed_updates)
    refuted = j.model_copy(
        update={
            "necessity": EpistemicStatus.DISPUTED,
            "no_less_coercive_alternative_available": EpistemicStatus.DISPUTED,
            "expected_total_coercion_reduction": -0.2,
        }
    )
    muts = [
        (
            "the Axiom 3 justification is fully established",
            case.model_copy(update={"justification": confirmed}),
        ),
        ("the Axiom 3 justification fails", case.model_copy(update={"justification": refuted})),
    ]
    return (
        "justification",
        "Are all six Axiom 3 conditions for justified coercion established?",
        "Coercion is justified only if every A3 condition holds; resolving them can flip a "
        "coercive action between acceptable and not.",
        ["A3"],
        muts,
    )


def _probe_consequences(case: ActionCase) -> _Probe | None:
    if case.coercion_profile is None:
        return None
    if case.consequences is not None or case.temporal_profile is not None:
        return None
    worse = ConsequenceSet(
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
    better = ConsequenceSet(
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
    muts = [
        (
            "long-term consequences are worse than described",
            case.model_copy(update={"consequences": worse}),
        ),
        ("long-term consequences are benign", case.model_copy(update={"consequences": better})),
    ]
    return (
        "consequences",
        "What are the medium and long-term consequences?",
        "An action can look acceptable now yet accumulate hidden, delayed, or cumulative "
        "coercion later (temporal instability).",
        ["A2"],
        muts,
    )


_PROBE_BUILDERS = (
    _probe_agent_type,
    _probe_consent,
    _probe_reversibility,
    _probe_alternatives,
    _probe_data_quality,
    _probe_justification,
    _probe_consequences,
)


def build_probes(case: ActionCase) -> list[_Probe]:
    """Return the applicable counterfactual probes for a case's genuine unknowns."""
    return [p for builder in _PROBE_BUILDERS if (p := builder(case)) is not None]


# =============================================================================
# Value-of-information computation
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
    """Rank the case's unknowns by how much resolving each would change the verdict."""
    base = evaluator.evaluate(case)
    out: list[InformationValue] = []
    for field, question, why, axioms, muts in build_probes(case):
        resolutions: list[ResolutionOutcome] = []
        max_vdist = 0.0
        max_cdist = 0.0
        changes = False
        for label, mcase in muts:
            r = evaluator.evaluate(mcase)
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
                field=field,
                question=question,
                why_it_matters=why,
                value=value,
                changes_verdict=changes,
                swing=_swing_summary(base.verdict, resolutions),
                resolutions=resolutions,
                related_axioms=axioms,
            )
        )
    out.sort(key=lambda iv: (iv.value, iv.changes_verdict), reverse=True)
    return out


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
