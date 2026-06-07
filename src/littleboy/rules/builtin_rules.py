"""LittleBoy's built-in rules (v0.3), LB-R001 .. LB-R012.

Each rule encodes one strand of the ethical model as an explicit, self-explaining
check. Together with the policy profile and the engine's synthesis, they make
every verdict traceable to named rules, axioms, thresholds, and evidence.

The rules report; the engine's synthesis (see :mod:`littleboy.rules.engine`)
combines their results into a final verdict. Responsibilities are partitioned so
no single factor is double-counted.
"""

from __future__ import annotations

from littleboy.core.enums import (
    AgentType,
    ConsentStatus,
    EpistemicStatus,
    RuleResultStatus,
    RuleSeverity,
    Verdict,
)
from littleboy.core.models import RuleResult
from littleboy.rules.base import Rule, RuleContext
from littleboy.rules.registry import RuleRegistry

_S = RuleResultStatus
_V = RuleSeverity


class TypeIIDutyRule(Rule):
    rule_id = "LB-R001"
    name = "Type II Duty Rule"
    description = (
        "Type II agents are morally evaluable and can bear duties; Type I agents "
        "cannot bear duties; an unknown agent type lowers confidence."
    )
    axioms_invoked = ("A1", "A4")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        agent_type = ctx.case.effective_agent_type()
        if agent_type == AgentType.TYPE_II:
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="Acting agent is Type II; the action is morally evaluable "
                "and the agent can bear duties (A4).",
            )
        if agent_type == AgentType.TYPE_I:
            return self.result(
                status=_S.NOT_APPLICABLE,
                severity=_V.WARNING,
                message="Acting agent is Type I; moral-duty assignment is not "
                "applicable (A4). Coercion in the world is still assessed.",
            )
        return self.result(
            status=_S.UNKNOWN,
            severity=_V.WARNING,
            message="Acting agent type is unknown; duty-bearing status is "
            "undetermined and confidence is reduced (A4/A5).",
            missing_data=["acting agent type"],
        )


class CoercionDetectionRule(Rule):
    rule_id = "LB-R002"
    name = "Coercion Detection Rule"
    description = (
        "If coercion exceeds the policy threshold, the action is at least "
        "ethically suspicious unless it is established as justified."
    )
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.coercion_present:
            return self.not_applicable("no coercion profile supplied")
        c = ctx.coercion_score
        high = ctx.policy.max_coercion_for_acceptable
        if c >= high:
            if ctx.justification.is_justified is True:
                return self.result(
                    status=_S.PASSED,
                    severity=_V.WARNING,
                    message=f"Coercion is high ({c:.2f} >= {high:.2f}) but a complete "
                    "justification is supplied (see LB-R007).",
                )
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message=f"Coercion exceeds the acceptable threshold "
                f"({c:.2f} >= {high:.2f}) and is not established as justified.",
                verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
            )
        if c >= ctx.policy.coercion_moderate:
            return self.result(
                status=_S.PASSED,
                severity=_V.WARNING,
                message=f"Coercion is moderate ({c:.2f}); scrutiny of alternatives "
                "and justification applies.",
            )
        return self.result(
            status=_S.PASSED, severity=_V.INFO, message=f"Coercion is low ({c:.2f})."
        )


class ConsentRule(Rule):
    rule_id = "LB-R003"
    name = "Consent Rule"
    description = (
        "Relevant consent that is unknown, disputed, refused, or coerced "
        "downgrades or blocks approval according to policy."
    )
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        status = ctx.consent.effective_status
        if status == ConsentStatus.NOT_APPLICABLE:
            return self.not_applicable("consent is not applicable to this action")
        if status == ConsentStatus.GIVEN:
            if ctx.consent.valid is True:
                return self.result(
                    status=_S.PASSED,
                    severity=_V.INFO,
                    message="Consent was given and is adequately established.",
                )
            return self.result(
                status=_S.UNKNOWN,
                severity=_V.WARNING,
                message="Consent is given but not fully established "
                "(informed/voluntary/specific/revocable).",
                confidence_delta=-0.05,
            )
        if status == ConsentStatus.UNKNOWN:
            if ctx.policy.unknown_consent_is_blocker:
                return self.result(
                    status=_S.FAILED,
                    severity=_V.BLOCKER,
                    message="Consent is unknown; this policy treats unknown consent "
                    "as a blocker to confident approval.",
                    verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
                    missing_data=["consent status of affected agents"],
                )
            return self.result(
                status=_S.UNKNOWN,
                severity=_V.WARNING,
                message="Consent is unknown; confidence is reduced (resolve before approval).",
                missing_data=["consent status of affected agents"],
            )
        if status == ConsentStatus.REFUSED:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="Consent was refused; acting against refusal is presumptively coercive.",
                verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
            )
        if status == ConsentStatus.COERCED:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="Consent was coerced; coerced consent is not valid consent.",
                verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
            )
        # DISPUTED
        return self.result(
            status=_S.FAILED,
            severity=_V.DOWNGRADE,
            message="Consent is disputed; confident approval is withheld (downgraded).",
            verdict_delta=1,
            confidence_delta=-0.15,
        )


class DataQualityRule(Rule):
    rule_id = "LB-R004"
    name = "Data Quality Rule"
    description = (
        "If the epistemic basis is below the policy minimum, confident approval is prevented."
    )
    axioms_invoked = ("A5",)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.has_epistemic_basis:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="Neither a data-quality profile nor evidence was provided.",
                verdict_cap=Verdict.INSUFFICIENT_DATA,
                missing_data=["source reliability / supporting evidence"],
            )
        if not ctx.coercion_present:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="No coercion profile was provided; the central question "
                "cannot be assessed.",
                verdict_cap=Verdict.INSUFFICIENT_DATA,
                missing_data=["coercion profile"],
            )
        floor = ctx.policy.min_data_quality_for_approval
        if ctx.epistemic_score < floor:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message=f"Epistemic basis {ctx.epistemic_score:.2f} is below the policy "
                f"minimum {floor:.2f}.",
                verdict_cap=Verdict.INSUFFICIENT_DATA,
            )
        if ctx.epistemic_score < ctx.policy.data_quality_good:
            return self.result(
                status=_S.PASSED,
                severity=_V.WARNING,
                message=f"Epistemic basis {ctx.epistemic_score:.2f} is adequate but not strong.",
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message=f"Epistemic basis is good ({ctx.epistemic_score:.2f}).",
        )


class EvidenceQualityRule(Rule):
    rule_id = "LB-R005"
    name = "Evidence Quality Rule"
    description = "Weak, contested, or unsupported evidence lowers confidence and is listed."
    axioms_invoked = ("A5",)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        ev = ctx.evidence
        if not ev.provided:
            return self.not_applicable("no structured evidence supplied")
        weak = [*ev.contested_claims, *ev.unsupported_claims]
        floor = ctx.policy.min_evidence_quality_for_approval
        if ev.score < floor:
            return self.result(
                status=_S.FAILED,
                severity=_V.WARNING,
                message=f"Evidence quality {ev.score:.2f} is below the policy minimum {floor:.2f}.",
                confidence_delta=-0.10,
                evidence_used=weak,
                missing_data=weak,
            )
        if weak:
            return self.result(
                status=_S.FAILED,
                severity=_V.WARNING,
                message="Some evidence is contested or unsupported.",
                confidence_delta=-0.10,
                evidence_used=weak,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message=f"Supporting evidence is adequate ({ev.score:.2f}).",
        )


class LessCoerciveAlternativeRule(Rule):
    rule_id = "LB-R006"
    name = "Less-Coercive Alternative Rule"
    description = (
        "A feasible less-coercive alternative downgrades the action; unknown "
        "alternatives block confident approval of a coercive action."
    )
    axioms_invoked = ("A2",)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        aa = ctx.alternatives
        if not aa.evaluated:
            if ctx.coercion_score >= ctx.policy.coercion_moderate:
                return self.result(
                    status=_S.UNKNOWN,
                    severity=_V.BLOCKER,
                    message="Alternatives were not analysed for a coercive action; "
                    "confident approval is blocked.",
                    verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
                    missing_data=["possible less-coercive alternatives"],
                )
            return self.result(
                status=_S.UNKNOWN,
                severity=_V.WARNING,
                message="Alternatives were not analysed.",
                missing_data=["possible less-coercive alternatives"],
            )
        if aa.has_feasible_less_coercive:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message="A feasible less coercive alternative exists: "
                + "; ".join(aa.feasible_less_coercive),
                verdict_delta=ctx.policy.alternative_downgrade_steps,
            )
        notes = list(aa.infeasible_less_coercive)
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message="No feasible less coercive alternative was found.",
            trace_notes=[f"less coercive but infeasible: {n}" for n in notes],
        )


class JustifiedCoercionRule(Rule):
    rule_id = "LB-R007"
    name = "Justified Coercion Rule"
    description = (
        "High coercion may be justified only when every Axiom 3 condition is "
        "established; a false condition blocks approval, an unknown one withholds it."
    )
    axioms_invoked = ("A2", "A3")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.coercion_present or ctx.coercion_score < ctx.policy.max_coercion_for_acceptable:
            return self.not_applicable("coercion is not high enough to require justification")
        if ctx.case.justification is None:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="Coercion is high and no Axiom 3 justification was supplied.",
                verdict_cap=Verdict.NOT_ACCEPTABLE,
                missing_data=["formal coercion justification"],
            )
        j = ctx.justification
        if j.is_justified is False:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="Justification fails Axiom 3 condition(s): "
                + "; ".join(j.failed_conditions),
                verdict_cap=Verdict.NOT_ACCEPTABLE,
            )
        if j.is_justified is None:
            return self.result(
                status=_S.UNKNOWN,
                severity=_V.DOWNGRADE,
                message="Justification is incomplete (unknown: "
                + "; ".join(j.unknown_conditions)
                + "); confident approval is withheld.",
                verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
                missing_data=list(j.unknown_conditions),
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message="All Axiom 3 conditions are established; coercion may be "
            "justified (acceptable only with reservations).",
        )


class VulnerabilityProtectionRule(Rule):
    rule_id = "LB-R008"
    name = "Vulnerability Protection Rule"
    description = (
        "High vulnerability of affected agents raises scrutiny; unknown or "
        "disputed consent under high vulnerability is severe."
    )
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        ag = ctx.agency
        if not ag.high_vulnerability:
            return self.not_applicable("subject vulnerability is not high")
        penalty = ctx.policy.vulnerability_confidence_penalty
        if ctx.consent.valid is not True:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message=f"Affected subject is highly vulnerable ({ag.vulnerability_level:.2f}) "
                "and consent is not clearly valid; scrutiny is raised.",
                verdict_delta=1,
                confidence_delta=-penalty,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.WARNING,
            message=f"Affected subject is highly vulnerable ({ag.vulnerability_level:.2f}); "
            "consent appears valid, but scrutiny is raised.",
            confidence_delta=-penalty,
        )


class InformationalManipulationRule(Rule):
    rule_id = "LB-R009"
    name = "Informational Manipulation Rule"
    description = "Informational manipulation is counted as coercion, not mere bad communication."
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.coercion_present or ctx.informational_manipulation <= 0.0:
            return self.not_applicable("no informational manipulation present")
        return self.result(
            status=_S.FAILED,
            severity=_V.WARNING,
            message=f"Informational manipulation is present "
            f"({ctx.informational_manipulation:.2f}); it is counted as coercion "
            "(A0/A2), not treated as mere bad communication.",
        )


class IrreversibilityRule(Rule):
    rule_id = "LB-R010"
    name = "Irreversibility Rule"
    description = "An irreversible action on a weak epistemic basis is blocked or insufficient."
    axioms_invoked = ("A5",)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.irreversible:
            return self.not_applicable("the action is not (known to be) irreversible")
        bar = ctx.policy.irreversible_min_epistemic
        if ctx.policy.irreversible_requires_high_certainty and ctx.epistemic_score < bar:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="The action is effectively irreversible and the epistemic basis "
                f"is weak ({ctx.epistemic_score:.2f} < {bar:.2f}); irreversible acts "
                "demand stronger evidence.",
                verdict_cap=Verdict.INSUFFICIENT_DATA,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.WARNING,
            message="The action is effectively irreversible; strong evidence is required.",
        )


class CessationRule(Rule):
    rule_id = "LB-R011"
    name = "Cessation Rule"
    description = "Justified coercion must define a stop condition; otherwise it is downgraded."
    axioms_invoked = ("A3",)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.coercion_present or ctx.coercion_score < ctx.policy.coercion_moderate:
            return self.not_applicable("coercion is not significant enough to require cessation")
        j = ctx.case.justification
        if j is None:
            return self.not_applicable("no justification offered")
        if j.cessation_condition_defined.is_affirmative:
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="A cessation condition for the coercion is defined.",
            )
        return self.result(
            status=_S.FAILED,
            severity=_V.DOWNGRADE,
            message="Coercion is exerted without a clearly defined cessation/stop condition.",
            verdict_delta=1,
            missing_data=["a defined cessation condition for the coercion"],
        )


class ContradictionRule(Rule):
    rule_id = "LB-R012"
    name = "Contradiction Rule"
    description = (
        "Flags internally incompatible claims in the case (e.g. justified vs. alternative exists)."
    )
    axioms_invoked = ("A1", "A3")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        contradictions: list[str] = []
        j = ctx.case.justification
        aa = ctx.alternatives

        if (
            j is not None
            and j.no_less_coercive_alternative_available.is_affirmative
            and aa.has_feasible_less_coercive
        ):
            contradictions.append(
                "the justification asserts no less coercive alternative is available, "
                "yet a feasible less coercive alternative was identified"
            )
        if (
            j is not None
            and ctx.case.responds_to_existing_coercion is False
            and j.responds_to_existing_or_imminent_coercion.is_affirmative
        ):
            contradictions.append(
                "the case states the action does not respond to prior/imminent coercion, "
                "yet the justification claims that it does"
            )
        cp = ctx.case.consent_profile
        if (
            cp is not None
            and cp.status == ConsentStatus.GIVEN
            and cp.voluntary == EpistemicStatus.DISPUTED
        ):
            contradictions.append("consent is reported as GIVEN but its voluntariness is disputed")

        if contradictions:
            return self.result(
                status=_S.FAILED,
                severity=_V.CONTRADICTION,
                message="Incompatible claims detected: " + "; ".join(contradictions),
                verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
                trace_notes=contradictions,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message="No internal contradictions detected among the case's claims.",
        )


# The canonical, ordered list of built-in rules.
BUILTIN_RULES: tuple[type[Rule], ...] = (
    TypeIIDutyRule,
    CoercionDetectionRule,
    ConsentRule,
    DataQualityRule,
    EvidenceQualityRule,
    LessCoerciveAlternativeRule,
    JustifiedCoercionRule,
    VulnerabilityProtectionRule,
    InformationalManipulationRule,
    IrreversibilityRule,
    CessationRule,
    ContradictionRule,
)


def default_registry() -> RuleRegistry:
    """Build a registry populated with all built-in rules."""
    registry = RuleRegistry()
    registry.register_all([rule_cls() for rule_cls in BUILTIN_RULES])
    return registry
