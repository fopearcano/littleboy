"""The LittleBoy ethical evaluator (v0.3, rule-engine driven).

:class:`EthicalEvaluator` takes an :class:`~littleboy.core.models.ActionCase` and
produces an :class:`~littleboy.core.models.EvaluationReport`. As of v0.3 the
verdict is determined by an explicit, inspectable rule engine under a chosen
:class:`~littleboy.rules.policy.PolicyProfile`, and every report carries a full
:class:`~littleboy.core.models.ReasoningTrace`.

The evaluator's job is now narrow and legible:

1. compute the base scores (coercion, data quality, evidence) and assessments
   (consent, agency, justification, alternatives) -- reusing the v0.1/v0.2 logic;
2. run the rule engine over those facts;
3. read the synthesized verdict, confidence, and trace back out;
4. assemble a fully-explained report.

No reasoning is hidden: the rule trace shows which rule lowered confidence, which
blocked approval, which axiom was invoked, and what was missing. Cases that use
only v0.1/v0.2 fields evaluate, under the default STANDARD policy, exactly as in
v0.2.
"""

from __future__ import annotations

from littleboy.case_builder.completeness import completeness_report
from littleboy.core import axioms as ax
from littleboy.core.agency import assess_agency, assess_consent
from littleboy.core.alternatives import analyse_alternatives
from littleboy.core.enums import ConsentStatus, RuleResultStatus, RuleSeverity, Verdict
from littleboy.core.gates import detect_missing_critical_data, recommended_next_questions
from littleboy.core.models import (
    ActionCase,
    EvaluationReport,
    ExperimentSummary,
)
from littleboy.core.scoring import score_coercion
from littleboy.data.evidence import assess_evidence
from littleboy.data.quality import (
    assess_data_quality,
    classify_uncertainty,
    combine_epistemic_score,
    compute_confidence,
)
from littleboy.language.analyzer import (
    analyze_language,
    language_to_coercion_profile,
    merge_coercion_profiles,
)
from littleboy.rules.base import RuleContext
from littleboy.rules.engine import RuleEngine
from littleboy.rules.policy import PolicyMode, PolicyProfile, get_policy

# An action is treated as "irreversible" below this reversibility value. This is a
# structural fact about the action; the *consequences* of irreversibility are
# governed by policy (see PolicyProfile.irreversible_*).
IRREVERSIBLE_THRESHOLD = 0.30

SCOPE_DISCLAIMER = (
    "LittleBoy produces a transparent heuristic judgment, not absolute moral truth. "
    "It is NOT a legal, medical, or emergency decision-maker."
)

_SURFACED_SEVERITIES = {RuleSeverity.WARNING, RuleSeverity.BLOCKER, RuleSeverity.CONTRADICTION}


class EthicalEvaluator:
    """Evaluate an :class:`ActionCase` against the LittleBoy axioms via the rule engine."""

    def __init__(
        self,
        policy: PolicyMode | PolicyProfile | str | None = None,
        *,
        engine: RuleEngine | None = None,
        include_completeness: bool = True,
    ) -> None:
        self.policy: PolicyProfile = get_policy(policy)
        self.engine = engine or RuleEngine(self.policy)
        self.include_completeness = include_completeness

    # -- public API -----------------------------------------------------------

    def evaluate(self, case: ActionCase) -> EvaluationReport:
        """Evaluate a case and return a fully-explained, fully-traced report."""
        # 0. Language analysis (v0.5): if the case centres on a language act,
        #    analyse it and fold its linguistic coercion into the coercion model.
        language_analysis = (
            analyze_language(case.language_act) if case.language_act is not None else None
        )
        language_coercion = (
            language_to_coercion_profile(language_analysis)
            if language_analysis is not None
            else None
        )
        effective_profile = merge_coercion_profiles(case.coercion_profile, language_coercion)

        # 1. Base scores and assessments (reused from v0.1/v0.2).
        if effective_profile is not None:
            coercion = score_coercion(effective_profile)
            coercion_score = coercion.score
            coercion_reasoning = list(coercion.reasoning)
            if language_coercion is not None:
                coercion_reasoning.append(
                    "includes a linguistic-coercion contribution "
                    f"(linguistic coercion {language_analysis.linguistic_coercion_score:.2f}; "
                    "informational_manipulation/psychological_pressure raised accordingly)"
                )
        else:
            coercion_score = 0.0
            coercion_reasoning = [
                "no coercion profile supplied; coercion could not be characterised"
            ]

        dq = assess_data_quality(case.data_quality)
        evidence = assess_evidence(case.evidence)
        epistemic_score = combine_epistemic_score(
            dq.score, evidence_provided=evidence.provided, evidence_score=evidence.score
        )

        consent = assess_consent(case)
        agency = assess_agency(case)
        justification = ax.evaluate_coercion_justification(case.justification)
        alternatives = analyse_alternatives(case.available_alternatives, coercion_score)

        # 2. Unknowns, missing data, base confidence (Axiom 5).
        n_unknowns, missing_data = self._collect_unknowns(
            case, coercion_score, consent, agency, effective_profile
        )
        for fact in dq.missing_facts:
            missing_data.append(f"missing critical fact: {fact}")
        for item in detect_missing_critical_data(case):
            missing_data.append(f"critical data missing: {item}")
        if language_analysis is not None:
            missing_data.extend(f"language: {m}" for m in language_analysis.missing_data)
        missing_data = _unique(missing_data)
        base_confidence = compute_confidence(epistemic_score, n_unknowns)

        # 3. Build the rule context and run the engine.
        profile = effective_profile
        irreversible = (
            profile is not None
            and profile.reversibility_is_known
            and profile.reversibility < IRREVERSIBLE_THRESHOLD
        )
        ctx = RuleContext(
            case=case,
            policy=self.policy,
            coercion_score=coercion_score,
            coercion_present=profile is not None,
            informational_manipulation=(profile.informational_manipulation if profile else 0.0),
            irreversible=irreversible,
            epistemic_score=epistemic_score,
            has_epistemic_basis=(case.data_quality is not None or evidence.provided),
            data_quality_score=dq.score,
            evidence=evidence,
            consent=consent,
            agency=agency,
            justification=justification,
            alternatives=alternatives,
            n_unknowns=n_unknowns,
            base_confidence=base_confidence,
            language_present=language_analysis is not None,
            language_profile=(language_analysis.profile if language_analysis else None),
            language_context=(language_analysis.context if language_analysis else None),
            linguistic_coercion=(
                language_analysis.linguistic_coercion_score if language_analysis else 0.0
            ),
            constructive=(language_analysis.constructive if language_analysis else None),
            language_affects_consent=(
                language_analysis.affects_consent if language_analysis else False
            ),
            language_replaces_framing=(
                language_analysis.replaces_subject_framing if language_analysis else False
            ),
        )
        outcome = self.engine.evaluate(ctx, missing_data=missing_data)

        verdict = outcome.verdict
        confidence = outcome.final_confidence
        uncertainty = classify_uncertainty(confidence)

        # 4. Assemble narratives from the rule results + sub-assessments.
        main_reasons = self._build_main_reasons(outcome, consent, agency)
        warnings = self._build_warnings(
            outcome, consent, agency, justification, alternatives, language_analysis
        )

        data_quality_reasoning = list(dq.reasoning)
        data_quality_reasoning.append(
            f"epistemic basis = {epistemic_score:.2f} "
            f"(data quality {dq.score:.2f}"
            + (f" + evidence {evidence.score:.2f}" if evidence.provided else "")
            + f"); base confidence after {n_unknowns} unknown(s) = {base_confidence:.2f}; "
            f"final confidence after rule adjustments = {confidence:.2f} "
            f"(uncertainty: {uncertainty.value})"
        )

        axiom_ids = self._collect_axioms(outcome)

        experiment = ExperimentSummary(
            can_be_judged=verdict != Verdict.INSUFFICIENT_DATA,
            provisional_verdict=verdict,
            tested_axioms=axiom_ids,
            open_questions=recommended_next_questions(case),
            notes=[
                f"coercion {coercion_score:.2f}, epistemic basis {epistemic_score:.2f}, "
                f"confidence {confidence:.2f}, policy {self.policy.mode.value}"
            ],
        )

        explanation = self._build_explanation(
            verdict=verdict,
            coercion_score=coercion_score,
            confidence=confidence,
            uncertainty=uncertainty.value,
            reasons=main_reasons,
            missing_data=missing_data,
        )

        # Optional completeness report: what is missing and what to ask next.
        completeness = None
        recommended_questions: list = []
        if self.include_completeness:
            completeness = completeness_report(case, policy=self.policy)
            recommended_questions = completeness.recommended_next_questions
            if completeness.warnings and verdict != Verdict.INSUFFICIENT_DATA:
                warnings = _unique([*warnings, *completeness.warnings])

        return EvaluationReport(
            verdict=verdict,
            coercion_score=round(coercion_score, 4),
            data_quality_score=round(dq.score, 4),
            evidence_score=round(evidence.score, 4),
            confidence=round(confidence, 4),
            uncertainty_level=uncertainty,
            policy_mode=self.policy.mode,
            consent_status=consent.summary,
            agency_status=agency.summary,
            main_reasons=main_reasons,
            coercion_reasoning=coercion_reasoning,
            data_quality_reasoning=data_quality_reasoning,
            evidence_reasoning=list(evidence.reasoning),
            missing_data=missing_data,
            less_coercive_alternatives=alternatives.feasible_less_coercive,
            axioms_invoked=[ax.cite(i) for i in axiom_ids],
            warnings=warnings,
            justification_result=justification if case.justification is not None else None,
            alternatives_analysis=alternatives,
            ethical_experiment=experiment,
            reasoning_trace=outcome.trace,
            language_analysis=language_analysis,
            case_completeness=completeness,
            recommended_questions=recommended_questions,
            explanation=explanation,
        )

    # -- narrative assembly ---------------------------------------------------

    def _build_main_reasons(self, outcome, consent, agency) -> list[str]:
        """Main reasons: the duty finding, the decisive rule messages, and context."""
        reasons: list[str] = []
        duty = next((r for r in outcome.rule_results if r.rule_id == "LB-R001"), None)
        if duty is not None:
            reasons.append(duty.message)
        reasons.extend(outcome.primary_reasons)
        reasons.extend(consent.reasons)
        reasons.extend(agency.reasons)
        return _unique(reasons)

    def _build_warnings(
        self, outcome, consent, agency, justification, alternatives, language_analysis=None
    ) -> list[str]:
        """Warnings: surfaced rule findings plus sub-assessment warnings."""
        warnings: list[str] = [
            f"[{r.rule_id}] {r.message}"
            for r in outcome.rule_results
            if r.severity in _SURFACED_SEVERITIES
        ]
        warnings.extend(consent.warnings)
        warnings.extend(agency.warnings)
        warnings.extend(justification.warnings)
        if language_analysis is not None:
            warnings.extend(f"[language] {w}" for w in language_analysis.warnings)
        if alternatives.infeasible_less_coercive:
            warnings.append(
                "less coercive but infeasible option(s) noted (do not defeat the action): "
                + "; ".join(alternatives.infeasible_less_coercive)
            )
        if alternatives.unquantified:
            warnings.append(
                "alternative(s) with unquantified coercion: " + "; ".join(alternatives.unquantified)
            )
        warnings.append(SCOPE_DISCLAIMER)
        return _unique(warnings)

    def _collect_axioms(self, outcome) -> list[str]:
        """All axioms invoked by rules that actually applied, with A0 first."""
        axiom_ids: list[str] = ["A0"]
        for r in outcome.rule_results:
            if r.status != RuleResultStatus.NOT_APPLICABLE:
                axiom_ids.extend(r.axioms_invoked)
        return _unique(axiom_ids)

    # -- unknowns -------------------------------------------------------------

    def _collect_unknowns(self, case, coercion_score, consent, agency, effective_profile=None):
        """Return ``(count, missing_notes)``. Counts each distinct unknown once.

        The first six are the v0.1 structural unknowns; the last two are extra
        granular penalties that only apply when a structured consent/agency
        profile is supplied. ``effective_profile`` is the coercion profile after
        any language contribution is merged in (so a language act can supply
        reversibility). Drives the base confidence.
        """
        unknowns: list[str] = []
        missing: list[str] = []
        profile = effective_profile if effective_profile is not None else case.coercion_profile

        if case.effective_agent_type() is None:
            unknowns.append("agent_type")
            missing.append("acting agent type is unknown (cannot assign duties under Axiom 4)")
        if consent.effective_status == ConsentStatus.UNKNOWN:
            unknowns.append("consent")
            missing.append("consent status of affected agents is unknown")
        if case.available_alternatives is None:
            unknowns.append("alternatives")
            missing.append("less-coercive alternatives were not analysed")
        if case.expected_consequences is None:
            unknowns.append("consequences")
            missing.append("expected consequences of the action are unknown")
        if profile is None or not profile.reversibility_is_known:
            unknowns.append("reversibility")
            missing.append("reversibility of the coercion is unknown")
        moderate = self.policy.coercion_moderate
        if coercion_score >= moderate and case.responds_to_existing_coercion is None:
            unknowns.append("coercion_source")
            missing.append("the coercion source is unknown (is this a response to prior coercion?)")

        if case.consent_profile is not None and consent.n_unknown_dimensions >= 2:
            unknowns.append("consent_dimensions")
            missing.append("several consent dimensions (informed/voluntary/...) are unresolved")
        if case.agency_profile is not None and agency.n_unknowns > 0:
            unknowns.append("agency_capacity")
            missing.append("the subject's decision/symbolic capacity is unresolved")

        return len(unknowns), missing

    # -- explanation ----------------------------------------------------------

    def _build_explanation(
        self, *, verdict, coercion_score, confidence, uncertainty, reasons, missing_data
    ) -> str:
        """Compose a clear, non-rhetorical summary paragraph."""
        parts = [
            f"Verdict: {verdict.value} (coercion {coercion_score:.2f}, "
            f"confidence {confidence:.2f}, uncertainty {uncertainty}, "
            f"policy {self.policy.mode.value})."
        ]
        if reasons:
            parts.append("Primary basis: " + reasons[0])
        if verdict == Verdict.INSUFFICIENT_DATA:
            parts.append(
                "LittleBoy is not asserting the action is acceptable or unacceptable; it is "
                "reporting that the available information does not support a confident judgment."
            )
        if missing_data:
            shown = "; ".join(missing_data[:3])
            more = "" if len(missing_data) <= 3 else f" (+{len(missing_data) - 3} more)"
            parts.append(f"Key missing information: {shown}{more}.")
        return " ".join(parts)


def _unique(items: list[str]) -> list[str]:
    """Return items with duplicates removed, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
