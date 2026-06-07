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
    LanguageMedium,
    PolicyMode,
    RuleResultStatus,
    RuleSeverity,
    Verdict,
)
from littleboy.core.models import RuleResult
from littleboy.rules.base import Rule, RuleContext
from littleboy.rules.registry import RuleRegistry

# LB-R024 confidence penalty for high-impact, weakly-evidenced temporal claims.
_TEMPORAL_UNCERTAINTY_DELTA = {
    PolicyMode.PERMISSIVE: -0.05,
    PolicyMode.STANDARD: -0.10,
    PolicyMode.STRICT: -0.15,
    PolicyMode.PRECAUTIONARY: -0.20,
}

# Media in which clarity carries a heightened ethical duty (used by LB-R018).
_CLARITY_REQUIRED_MEDIA = (
    LanguageMedium.MEDICAL_CONSENT,
    LanguageMedium.LEGAL_NOTICE,
    LanguageMedium.CONTRACT,
    LanguageMedium.EDUCATIONAL,
)

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


class LinguisticCoercionRule(Rule):
    rule_id = "LB-R013"
    name = "Linguistic Coercion Rule"
    description = (
        "If language significantly restricts agency, consent, alternatives, or "
        "self-expression, it is flagged as coercion."
    )
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.language_present:
            return self.not_applicable("the case contains no language act")
        p = ctx.language_profile
        restricts = ctx.linguistic_coercion >= ctx.policy.coercion_moderate or (
            p is not None and (p.agency_respect < 0.4 or p.silencing_effect >= 0.5)
        )
        if restricts:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message=(
                    "Language significantly restricts agency/consent/alternatives/"
                    f"self-expression (linguistic coercion {ctx.linguistic_coercion:.2f}); "
                    "counted as coercion (A0/A2)."
                ),
                verdict_delta=1,
                confidence_delta=-0.05,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message=f"Language does not significantly restrict agency (linguistic "
            f"coercion {ctx.linguistic_coercion:.2f}).",
        )


class ManipulativeFramingRule(Rule):
    rule_id = "LB-R014"
    name = "Manipulative Framing Rule"
    description = (
        "False necessity, false dichotomy, shame pressure, or fear pressure in the "
        "language downgrades the action."
    )
    axioms_invoked = ("A0", "A2")

    _LABELS = (
        ("false_necessity", "false necessity"),
        ("false_dichotomy", "false dichotomy"),
        ("shame_pressure", "shame pressure"),
        ("fear_pressure", "fear pressure"),
    )

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.language_present or ctx.language_profile is None:
            return self.not_applicable("the case contains no language act")
        p = ctx.language_profile
        present = [label for field, label in self._LABELS if getattr(p, field) >= 0.5]
        framing = max(p.false_necessity, p.false_dichotomy, p.shame_pressure, p.fear_pressure)
        if present:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message="Manipulative framing detected: " + ", ".join(present) + ".",
                verdict_delta=1,
                confidence_delta=-0.05,
            )
        if framing > 0.0:
            return self.result(
                status=_S.PASSED,
                severity=_V.WARNING,
                message="Mild manipulative framing is present but below the downgrade threshold.",
            )
        return self.result(
            status=_S.PASSED, severity=_V.INFO, message="No manipulative framing detected."
        )


class ConsentLanguageIntegrityRule(Rule):
    rule_id = "LB-R015"
    name = "Consent-Language Integrity Rule"
    description = (
        "If consent is sought or affected through unclear, manipulative, incomplete, "
        "or high-pressure language, consent quality is reduced and confident approval "
        "is withheld."
    )
    axioms_invoked = ("A0", "A2", "A3")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.language_present or ctx.language_profile is None:
            return self.not_applicable("the case contains no language act")
        if not ctx.language_affects_consent:
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="The language does not bear on consent.",
            )
        p = ctx.language_profile
        poor = (
            p.clarity < 0.5
            or p.manipulation_risk >= 0.5
            or p.context_completeness < 0.5
            or ctx.linguistic_coercion >= ctx.policy.coercion_moderate
        )
        if not poor:
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="Consent-bearing language is clear and non-manipulative.",
            )
        # Consent already 'given' on top of manipulative language must not yield
        # confident approval.
        cap = (
            Verdict.ETHICALLY_SUSPICIOUS
            if ctx.consent.effective_status == ConsentStatus.GIVEN
            else None
        )
        extra = (
            " Consent rests on manipulative language; confident approval is withheld."
            if cap
            else ""
        )
        return self.result(
            status=_S.FAILED,
            severity=_V.DOWNGRADE if cap is None else _V.BLOCKER,
            message="Consent is sought or affected through unclear/manipulative/high-pressure "
            "language; consent quality is reduced." + extra,
            verdict_delta=1,
            verdict_cap=cap,
            confidence_delta=-0.1,
            missing_data=["whether consent would stand under clear, non-manipulative language"],
        )


class TestimonialInjusticeRule(Rule):
    rule_id = "LB-R016"
    name = "Testimonial Injustice Rule"
    description = (
        "If the language dismisses or compresses the testimony of a vulnerable or "
        "low-status agent, warn or downgrade."
    )
    axioms_invoked = ("A0", "A1")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.language_present:
            return self.not_applicable("the case contains no language act")
        if not ctx.language_replaces_framing:
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="The language does not appear to dismiss or compress the "
                "subject's testimony.",
            )
        if ctx.agency.high_vulnerability:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message="Language dismisses or compresses the testimony of a vulnerable agent "
                "(testimonial injustice); their own framing of their will is being replaced.",
                verdict_delta=1,
                confidence_delta=-0.05,
            )
        return self.result(
            status=_S.FAILED,
            severity=_V.WARNING,
            message="Language may dismiss or compress the subject's own testimony/framing; "
            "examine the fuller meaning-field before judging.",
        )


class ConstructiveLanguageDutyRule(Rule):
    rule_id = "LB-R017"
    name = "Constructive Language Duty Rule"
    description = (
        "For Type II agents, when the action centrally involves language at moderate/high "
        "stakes, there is a duty to use language consciously and constructively."
    )
    axioms_invoked = ("A1", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.language_present:
            return self.not_applicable("the case contains no language act")
        stakes = ctx.language_context.stakes if ctx.language_context else 0.0
        if ctx.case.effective_agent_type() != AgentType.TYPE_II or stakes < 0.5:
            return self.not_applicable(
                "the constructive-language duty applies to Type II agents at moderate/high stakes"
            )
        score = ctx.constructive.constructive_score if ctx.constructive else 0.0
        if score < 0.5:
            return self.result(
                status=_S.FAILED,
                severity=_V.WARNING,
                message="A Type II agent has a duty to use language consciously and "
                f"constructively at these stakes; the constructive score is low ({score:.2f}).",
                confidence_delta=-0.05,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message="The constructive-language duty is satisfied "
            f"(constructive score {score:.2f}).",
        )


class ObfuscationUnderHighStakesRule(Rule):
    rule_id = "LB-R018"
    name = "Obfuscation Under High Stakes Rule"
    description = (
        "If language is obscure in a high-stakes context where clarity is ethically "
        "required, downgrade."
    )
    axioms_invoked = ("A1", "A5")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.language_present or ctx.language_profile is None:
            return self.not_applicable("the case contains no language act")
        context = ctx.language_context
        clarity_required = context is not None and (
            context.medium in _CLARITY_REQUIRED_MEDIA or context.stakes >= 0.6
        )
        p = ctx.language_profile
        obscure = p.ambiguity_level >= 0.5 or p.clarity < 0.4
        if clarity_required and obscure:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message="Language is obscure in a high-stakes context where clarity is "
                "ethically required (Axiom 5).",
                verdict_delta=1,
                confidence_delta=-0.05,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message="Clarity is adequate for the context.",
        )


class TemporalConsequenceRule(Rule):
    rule_id = "LB-R019"
    name = "Temporal Consequence Rule"
    description = (
        "If long-term consequences plausibly increase coercion, downgrade even when "
        "immediate coercion is low."
    )
    axioms_invoked = ("A2", "A5")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.temporal_present or ctx.temporal is None:
            return self.not_applicable("the case contains no temporal data")
        t = ctx.temporal
        if t.long_term_coercion >= ctx.policy.max_coercion_for_acceptable:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message=f"Long-term coercion is high ({t.long_term_coercion:.2f}) even though "
                f"immediate coercion is {t.immediate_coercion:.2f}; judged across time (A2).",
                verdict_delta=2,
                confidence_delta=-0.05,
            )
        if t.long_term_coercion >= ctx.policy.coercion_moderate and t.trend == "rising":
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message=f"Coercion rises over time (immediate {t.immediate_coercion:.2f} -> "
                f"long-term {t.long_term_coercion:.2f}); downgraded (A2).",
                verdict_delta=1,
            )
        if t.trend == "rising":
            return self.result(
                status=_S.PASSED,
                severity=_V.WARNING,
                message="Coercion trends upward over time, but stays below the moderate threshold.",
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message=(
                f"Long-term coercion ({t.long_term_coercion:.2f}) does not exceed "
                "the immediate level."
            ),
        )


class ReversibilityRuleV2(Rule):
    rule_id = "LB-R020"
    name = "Reversibility Rule v2"
    description = (
        "An irreversible action, or one whose reversibility is unknown, requires stronger "
        "evidence and justification (complements LB-R010)."
    )
    axioms_invoked = ("A3", "A5")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        rp = ctx.reversibility_profile
        irreversible = ctx.irreversible or (
            rp is not None
            and (rp.is_reversible == EpistemicStatus.DISPUTED or rp.reversibility_score < 0.3)
        )
        unknown = ctx.reversibility_unknown or (rp is not None and rp.is_reversible.is_unresolved)
        if not (irreversible or unknown or rp is not None):
            return self.not_applicable("reversibility is known and the action is reversible")

        if (
            irreversible
            and ctx.coercion_score >= ctx.policy.coercion_moderate
            and (ctx.justification.is_justified is not True)
        ):
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message="The action is effectively irreversible and coercive without an "
                "established justification; irreversible coercion demands strong "
                "justification (A3).",
                verdict_delta=1,
            )
        if irreversible:
            return self.result(
                status=_S.PASSED,
                severity=_V.WARNING,
                message="The action is effectively irreversible; stronger evidence and "
                "justification are expected (A5).",
            )
        if unknown:
            return self.result(
                status=_S.UNKNOWN,
                severity=_V.WARNING,
                message="Reversibility is unknown; confidence is reduced and irreversible acts "
                "would demand stronger evidence (A5).",
                missing_data=["reversibility of the action over time"],
            )
        return self.result(
            status=_S.PASSED, severity=_V.INFO, message="The action is adequately reversible."
        )


class CumulativeCoercionRule(Rule):
    rule_id = "LB-R021"
    name = "Cumulative Coercion Rule"
    description = (
        "If a repeated or normalised action creates significant cumulative coercion, downgrade."
    )
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.temporal_present or ctx.temporal is None:
            return self.not_applicable("the case contains no temporal data")
        cum = ctx.temporal.cumulative_coercion
        if cum <= 0.0:
            return self.not_applicable("no cumulative-coercion profile was supplied")
        if cum >= ctx.policy.max_coercion_for_acceptable:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message=f"Repeated/normalised, the action creates high cumulative coercion "
                f"({cum:.2f}); a small coercion becomes systemic (A0/A2).",
                verdict_delta=2,
                confidence_delta=-0.05,
            )
        if cum >= ctx.policy.coercion_moderate:
            return self.result(
                status=_S.FAILED,
                severity=_V.DOWNGRADE,
                message=f"Cumulative coercion is moderate ({cum:.2f}) once repetition/"
                "normalisation are considered; downgraded (A2).",
                verdict_delta=1,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.WARNING,
            message=f"Cumulative coercion is present but low ({cum:.2f}).",
        )


class InactionIsNotNeutralRule(Rule):
    rule_id = "LB-R022"
    name = "Inaction Is Not Neutral Rule"
    description = (
        "If inaction allows existing coercion to continue, worsen, or become irreversible, "
        "it is evaluated as a coercive choice, not a neutral default."
    )
    axioms_invoked = ("A0", "A2")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.case.is_inaction:
            return self.not_applicable("this case is not an inaction")
        t = ctx.temporal
        permits = t is not None and (
            t.expected_total_coercion >= ctx.policy.coercion_moderate
            or t.trend == "rising"
            or t.expected_coercion_delta > 0.0
        )
        if permits:
            return self.result(
                status=_S.FAILED,
                severity=_V.BLOCKER,
                message="Inaction here permits existing coercion to continue or grow; it is "
                "evaluated as a coercive choice and cannot be confidently approved (A0/A2).",
                verdict_cap=Verdict.ETHICALLY_SUSPICIOUS,
            )
        return self.result(
            status=_S.PASSED,
            severity=_V.INFO,
            message="Inaction does not appear to permit ongoing or growing coercion here.",
        )


class FutureCoercionPreventionRule(Rule):
    rule_id = "LB-R023"
    name = "Future Coercion Prevention Rule"
    description = (
        "Temporary coercion may be qualifiedly justified only if it credibly prevents greater "
        "future coercion and meets the Axiom 3 conditions."
    )
    axioms_invoked = ("A2", "A3")

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.temporal_present or ctx.temporal is None:
            return self.not_applicable("the case contains no temporal data")
        if ctx.coercion_score < ctx.policy.max_coercion_for_acceptable:
            return self.not_applicable(
                "no high present coercion that would need this justification"
            )
        if not ctx.temporal.prevents_greater_future_coercion:
            return self.not_applicable("no credible future-coercion prevention is claimed")
        if ctx.justification.is_justified is True:
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="Temporary coercion is qualifiedly justified: it credibly prevents "
                "greater future coercion and the Axiom 3 conditions are met.",
            )
        return self.result(
            status=_S.FAILED,
            severity=_V.WARNING,
            message="The action claims to prevent greater future coercion, but the Axiom 3 "
            "justification is incomplete; future prevention does not auto-justify "
            "present coercion.",
        )


class TemporalUncertaintyRule(Rule):
    rule_id = "LB-R024"
    name = "Temporal Uncertainty Rule"
    description = (
        "If temporal consequences are high-impact but weakly evidenced, confidence drops and the "
        "missing data is exposed."
    )
    axioms_invoked = ("A5",)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.temporal_present or ctx.temporal is None:
            return self.not_applicable("the case contains no temporal data")
        t = ctx.temporal
        material = t.long_term_coercion >= ctx.policy.coercion_moderate or (
            t.expected_total_coercion >= ctx.policy.coercion_moderate
        )
        if not (t.high_risk_unknowns or (t.uncertainty >= 0.5 and material)):
            return self.result(
                status=_S.PASSED,
                severity=_V.INFO,
                message="Temporal consequences are adequately evidenced for the stakes.",
            )
        delta = _TEMPORAL_UNCERTAINTY_DELTA[ctx.policy.mode]
        # Precautionary policy also downgrades, not merely lowers confidence.
        verdict_delta = 1 if ctx.policy.mode == PolicyMode.PRECAUTIONARY else 0
        return self.result(
            status=_S.FAILED,
            severity=_V.WARNING,
            message="Temporal consequences are high-impact but weakly evidenced; confidence is "
            "reduced and the missing data is exposed (A5).",
            confidence_delta=delta,
            verdict_delta=verdict_delta,
            missing_data=list(t.missing_data) + list(t.high_risk_unknowns),
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
    LinguisticCoercionRule,
    ManipulativeFramingRule,
    ConsentLanguageIntegrityRule,
    TestimonialInjusticeRule,
    ConstructiveLanguageDutyRule,
    ObfuscationUnderHighStakesRule,
    TemporalConsequenceRule,
    ReversibilityRuleV2,
    CumulativeCoercionRule,
    InactionIsNotNeutralRule,
    FutureCoercionPreventionRule,
    TemporalUncertaintyRule,
)


def default_registry() -> RuleRegistry:
    """Build a registry populated with all built-in rules."""
    registry = RuleRegistry()
    registry.register_all([rule_cls() for rule_cls in BUILTIN_RULES])
    return registry
