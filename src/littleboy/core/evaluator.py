"""The LittleBoy ethical evaluator (v0.2).

:class:`EthicalEvaluator` takes an :class:`~littleboy.core.models.ActionCase` and
produces an :class:`~littleboy.core.models.EvaluationReport`. The decision rule
is deliberately legible. Its guiding commitments:

* It applies the LittleBoy axioms (see :mod:`littleboy.core.axioms`).
* It never feigns certainty: poor data, irreversibility, or unresolved unknowns
  push it toward ``INSUFFICIENT_DATA`` and always lower confidence (Axiom 5).
* It is never a black box: every report exposes the axioms invoked, the
  coercion, evidence, consent, agency, and data-quality reasoning, what is
  missing, which alternatives were considered, and a plain-language explanation.

v0.2 integrates structured evidence, epistemic consent/agency, an epistemically
honest coercion justification, feasibility-aware alternative comparison, a
critical-data gate, and a built-in ethical-experiment summary. Cases that use
only v0.1 fields evaluate exactly as before.
"""

from __future__ import annotations

from littleboy.core import axioms as ax
from littleboy.core.agency import assess_agency, assess_consent
from littleboy.core.alternatives import analyse_alternatives
from littleboy.core.enums import ConsentStatus, Verdict
from littleboy.core.gates import detect_missing_critical_data, recommended_next_questions
from littleboy.core.models import (
    ActionCase,
    AlternativeAnalysis,
    EvaluationReport,
    ExperimentSummary,
    JustificationResult,
)
from littleboy.core.scoring import score_coercion
from littleboy.data.evidence import assess_evidence
from littleboy.data.quality import (
    assess_data_quality,
    classify_uncertainty,
    combine_epistemic_score,
    compute_confidence,
)

# --- Decision thresholds (all transparent and overridable per evaluator) -----
DEFAULT_COERCION_HIGH = 0.60
DEFAULT_COERCION_MODERATE = 0.30
DEFAULT_DATA_QUALITY_FLOOR = 0.35
DEFAULT_DATA_QUALITY_GOOD = 0.70
DEFAULT_MIN_CONFIDENCE = 0.30

# An action is "irreversible" below this reversibility value; combined with weak
# epistemics it forces INSUFFICIENT_DATA.
IRREVERSIBLE_THRESHOLD = 0.30
IRREVERSIBLE_MIN_EPISTEMIC = 0.50

# Confidence multipliers for specific, named hazards (only applied when present).
DISPUTED_CONSENT_FACTOR = 0.70
HIGH_VULNERABILITY_FACTOR = 0.80
CONTESTED_EVIDENCE_FACTOR = 0.85

# Verdicts ordered from most to least permissible (for one-notch downgrades).
_VERDICT_ORDER = (
    Verdict.ACCEPTABLE,
    Verdict.ACCEPTABLE_WITH_RESERVATIONS,
    Verdict.ETHICALLY_SUSPICIOUS,
    Verdict.NOT_ACCEPTABLE,
)
_POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}

SCOPE_DISCLAIMER = (
    "LittleBoy produces a transparent heuristic judgment, not absolute moral truth. "
    "It is NOT a legal, medical, or emergency decision-maker."
)


def _downgrade(verdict: Verdict, steps: int = 1) -> Verdict:
    """Move a verdict toward less permissible by ``steps`` (never past NOT_ACCEPTABLE)."""
    if verdict not in _VERDICT_ORDER:
        return verdict
    idx = _VERDICT_ORDER.index(verdict)
    return _VERDICT_ORDER[min(idx + steps, len(_VERDICT_ORDER) - 1)]


class EthicalEvaluator:
    """Evaluate an :class:`ActionCase` against the LittleBoy axioms."""

    def __init__(
        self,
        *,
        coercion_high: float = DEFAULT_COERCION_HIGH,
        coercion_moderate: float = DEFAULT_COERCION_MODERATE,
        data_quality_floor: float = DEFAULT_DATA_QUALITY_FLOOR,
        data_quality_good: float = DEFAULT_DATA_QUALITY_GOOD,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self.coercion_high = coercion_high
        self.coercion_moderate = coercion_moderate
        self.data_quality_floor = data_quality_floor
        self.data_quality_good = data_quality_good
        self.min_confidence = min_confidence

    # -- public API -----------------------------------------------------------

    def evaluate(self, case: ActionCase) -> EvaluationReport:
        """Evaluate a case and return a fully-explained report."""
        # 1. Coercion (the central ethical quantity).
        if case.coercion_profile is not None:
            coercion = score_coercion(case.coercion_profile)
            coercion_score = coercion.score
            coercion_reasoning = list(coercion.reasoning)
        else:
            coercion_score = 0.0
            coercion_reasoning = [
                "no coercion profile supplied; coercion could not be characterised"
            ]

        # 2. Epistemics: data quality + evidence -> a single epistemic basis.
        dq = assess_data_quality(case.data_quality)
        evidence = assess_evidence(case.evidence)
        epistemic_score = combine_epistemic_score(
            dq.score, evidence_provided=evidence.provided, evidence_score=evidence.score
        )

        # 3. Consent and agency.
        consent = assess_consent(case)
        agency = assess_agency(case)

        # 4. Justification (Axiom 3) and alternatives (Axiom 2).
        justification = ax.evaluate_coercion_justification(case.justification)
        alternatives = analyse_alternatives(case.available_alternatives, coercion_score)

        # 5. Unknowns, missing data, and confidence (Axiom 5).
        n_unknowns, missing_data = self._collect_unknowns(case, coercion_score, consent, agency)
        for fact in dq.missing_facts:
            missing_data.append(f"missing critical fact: {fact}")
        for item in detect_missing_critical_data(case):
            missing_data.append(f"critical data missing: {item}")
        missing_data = _unique(missing_data)

        confidence = self._compute_confidence(
            epistemic_score, n_unknowns, consent, agency, evidence
        )
        uncertainty = classify_uncertainty(confidence)

        # 6. Decide.
        verdict, reasons, axiom_ids, warnings = self._decide(
            case=case,
            coercion_score=coercion_score,
            epistemic_score=epistemic_score,
            confidence=confidence,
            n_unknowns=n_unknowns,
            justification=justification,
            alternatives=alternatives,
            consent=consent,
            agency=agency,
        )

        # 7. Reasoning narratives and warnings from the sub-assessments.
        reasons.extend(consent.reasons)
        reasons.extend(agency.reasons)
        warnings.extend(consent.warnings)
        warnings.extend(agency.warnings)
        warnings.extend(justification.warnings)
        if alternatives.infeasible_less_coercive:
            warnings.append(
                "less coercive but infeasible option(s) noted (do not defeat the action): "
                + "; ".join(alternatives.infeasible_less_coercive)
            )
        if alternatives.unquantified:
            warnings.append(
                "alternative(s) with unquantified coercion: " + "; ".join(alternatives.unquantified)
            )
        if (
            case.coercion_profile is not None
            and case.coercion_profile.informational_manipulation_present
        ):
            warnings.append(
                "informational manipulation is present; it is counted as coercion (A0/A2), "
                "not treated as mere bad communication"
            )
        warnings.append(SCOPE_DISCLAIMER)

        data_quality_reasoning = list(dq.reasoning)
        data_quality_reasoning.append(
            f"epistemic basis = {epistemic_score:.2f} "
            f"(data quality {dq.score:.2f}"
            + (f" + evidence {evidence.score:.2f}" if evidence.provided else "")
            + f"); confidence after {n_unknowns} unknown(s) and hazards = {confidence:.2f} "
            f"(uncertainty: {uncertainty.value})"
        )

        # 8. Built-in ethical experiment summary.
        experiment = ExperimentSummary(
            can_be_judged=verdict != Verdict.INSUFFICIENT_DATA,
            provisional_verdict=verdict,
            tested_axioms=_unique(axiom_ids),
            open_questions=recommended_next_questions(case),
            notes=[
                f"coercion {coercion_score:.2f}, epistemic basis {epistemic_score:.2f}, "
                f"confidence {confidence:.2f}"
            ],
        )

        explanation = self._build_explanation(
            verdict=verdict,
            coercion_score=coercion_score,
            confidence=confidence,
            uncertainty=uncertainty.value,
            reasons=reasons,
            missing_data=missing_data,
        )

        return EvaluationReport(
            verdict=verdict,
            coercion_score=round(coercion_score, 4),
            data_quality_score=round(dq.score, 4),
            evidence_score=round(evidence.score, 4),
            confidence=round(confidence, 4),
            uncertainty_level=uncertainty,
            consent_status=consent.summary,
            agency_status=agency.summary,
            main_reasons=_unique(reasons),
            coercion_reasoning=coercion_reasoning,
            data_quality_reasoning=data_quality_reasoning,
            evidence_reasoning=list(evidence.reasoning),
            missing_data=missing_data,
            less_coercive_alternatives=alternatives.feasible_less_coercive,
            axioms_invoked=[ax.cite(i) for i in _unique(axiom_ids)],
            warnings=_unique(warnings),
            justification_result=justification if case.justification is not None else None,
            alternatives_analysis=alternatives,
            ethical_experiment=experiment,
            explanation=explanation,
        )

    # -- unknowns and confidence ---------------------------------------------

    def _collect_unknowns(self, case, coercion_score, consent, agency):
        """Return ``(count, missing_notes)``. Counts each distinct unknown once.

        The first six are the v0.1 structural unknowns (unchanged for legacy
        cases). The last two are extra granular penalties that only apply when a
        structured consent/agency profile is supplied.
        """
        unknowns: list[str] = []
        missing: list[str] = []

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
        if case.coercion_profile is None or not case.coercion_profile.reversibility_is_known:
            unknowns.append("reversibility")
            missing.append("reversibility of the coercion is unknown")
        if coercion_score >= self.coercion_moderate and case.responds_to_existing_coercion is None:
            unknowns.append("coercion_source")
            missing.append("the coercion source is unknown (is this a response to prior coercion?)")

        # Granular, profile-only penalties.
        if case.consent_profile is not None and consent.n_unknown_dimensions >= 2:
            unknowns.append("consent_dimensions")
            missing.append("several consent dimensions (informed/voluntary/...) are unresolved")
        if case.agency_profile is not None and agency.n_unknowns > 0:
            unknowns.append("agency_capacity")
            missing.append("the subject's decision/symbolic capacity is unresolved")

        return len(unknowns), missing

    def _compute_confidence(self, epistemic_score, n_unknowns, consent, agency, evidence):
        """Confidence from the epistemic basis, unknowns, and named hazards."""
        confidence = compute_confidence(epistemic_score, n_unknowns)
        if consent.effective_status == ConsentStatus.DISPUTED:
            confidence *= DISPUTED_CONSENT_FACTOR
        if agency.high_vulnerability:
            confidence *= HIGH_VULNERABILITY_FACTOR
        if evidence.provided and (evidence.contested_claims or evidence.unsupported_claims):
            confidence *= CONTESTED_EVIDENCE_FACTOR
        return max(0.0, min(1.0, confidence))

    # -- decision rule --------------------------------------------------------

    def _decide(
        self,
        *,
        case: ActionCase,
        coercion_score: float,
        epistemic_score: float,
        confidence: float,
        n_unknowns: int,
        justification: JustificationResult,
        alternatives: AlternativeAnalysis,
        consent,
        agency,
    ) -> tuple[Verdict, list[str], list[str], list[str]]:
        """Apply the decision rule. Returns (verdict, reasons, axiom_ids, warnings)."""
        reasons: list[str] = []
        axiom_ids: list[str] = ["A0", "A1", "A4"]
        warnings: list[str] = []

        # Gate 0: enough trustworthy information to judge at all? (Axiom 5)
        no_epistemic_basis = case.data_quality is None and case.evidence is None
        insufficient = (
            no_epistemic_basis
            or case.coercion_profile is None
            or epistemic_score < self.data_quality_floor
            or confidence < self.min_confidence
        )
        if insufficient:
            axiom_ids.append("A5")
            reasons.append(
                "Data are insufficient for a confident judgment; per Axiom 5 LittleBoy "
                "declines to feign certainty."
            )
            if case.coercion_profile is None:
                reasons.append("No coercion profile was provided.")
            if no_epistemic_basis:
                reasons.append("Neither a data-quality profile nor evidence was provided.")
            if not no_epistemic_basis and epistemic_score < self.data_quality_floor:
                reasons.append(
                    f"Epistemic basis {epistemic_score:.2f} is below the floor "
                    f"{self.data_quality_floor:.2f}."
                )
            if confidence < self.min_confidence:
                reasons.append(
                    f"Confidence {confidence:.2f} is below the minimum {self.min_confidence:.2f}."
                )
            return Verdict.INSUFFICIENT_DATA, reasons, axiom_ids, warnings

        # Gate 1: irreversible action on weak epistemics is not judgeable. (A5)
        profile = case.coercion_profile
        irreversible = (
            profile is not None
            and profile.reversibility_is_known
            and profile.reversibility < IRREVERSIBLE_THRESHOLD
        )
        if irreversible and epistemic_score < IRREVERSIBLE_MIN_EPISTEMIC:
            axiom_ids.append("A5")
            reasons.append(
                f"The action is effectively irreversible (reversibility "
                f"{profile.reversibility:.2f}) and the epistemic basis is weak "
                f"({epistemic_score:.2f}); irreversible acts demand stronger evidence."
            )
            return Verdict.INSUFFICIENT_DATA, reasons, axiom_ids, warnings

        # Data sufficient: Axiom 2 governs -- minimise coercion.
        axiom_ids.append("A2")
        verdict = self._decide_by_coercion(
            case=case,
            coercion_score=coercion_score,
            epistemic_score=epistemic_score,
            n_unknowns=n_unknowns,
            justification=justification,
            alternatives=alternatives,
            reasons=reasons,
            axiom_ids=axiom_ids,
        )

        verdict = self._apply_downgrades(
            verdict=verdict,
            coercion_score=coercion_score,
            alternatives=alternatives,
            consent=consent,
            agency=agency,
            reasons=reasons,
        )

        if confidence < 0.5:
            axiom_ids.append("A5")
            warnings.append(
                f"Confidence is limited ({confidence:.2f}); treat this verdict as provisional."
            )
        return verdict, reasons, axiom_ids, warnings

    def _decide_by_coercion(
        self,
        *,
        case: ActionCase,
        coercion_score: float,
        epistemic_score: float,
        n_unknowns: int,
        justification: JustificationResult,
        alternatives: AlternativeAnalysis,
        reasons: list[str],
        axiom_ids: list[str],
    ) -> Verdict:
        """The coercion-driven core of the decision rule (data already sufficient)."""
        if coercion_score >= self.coercion_high:
            axiom_ids.append("A3")
            if case.justification is None:
                reasons.append(
                    f"Coercion is high ({coercion_score:.2f}) and no Axiom 3 justification "
                    "was supplied."
                )
                return Verdict.NOT_ACCEPTABLE
            if justification.is_justified is False:
                reasons.append(
                    f"Coercion is high ({coercion_score:.2f}) and the justification fails "
                    f"Axiom 3 condition(s): {', '.join(justification.failed_conditions)}."
                )
                return Verdict.NOT_ACCEPTABLE
            if justification.is_justified is None:
                reasons.append(
                    f"Coercion is high ({coercion_score:.2f}) and the justification is "
                    f"incomplete (unknown: {', '.join(justification.unknown_conditions)}); "
                    "confident approval is withheld."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            if not alternatives.evaluated:
                reasons.append(
                    "Coercion is high and claimed justified, but alternatives were not "
                    "analysed, so 'no less coercive alternative' cannot be verified."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            if alternatives.has_feasible_less_coercive:
                reasons.append(
                    "Coercion is high and justified-in-claim, but a feasible less coercive "
                    f"alternative exists: {'; '.join(alternatives.feasible_less_coercive)}."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            reasons.append(
                "Coercion is high but a complete Axiom 3 justification is supplied and no "
                "feasible less coercive alternative was found; accepted only with reservations."
            )
            return Verdict.ACCEPTABLE_WITH_RESERVATIONS

        if coercion_score >= self.coercion_moderate:
            axiom_ids.append("A3")
            if not alternatives.evaluated:
                reasons.append(
                    f"Coercion is moderate ({coercion_score:.2f}) but alternatives were "
                    "not analysed; less coercive options may exist."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            if alternatives.has_feasible_less_coercive and justification.is_justified is not True:
                options = "; ".join(alternatives.feasible_less_coercive)
                reasons.append(
                    f"Coercion is moderate ({coercion_score:.2f}) and a feasible less "
                    f"coercive alternative exists: {options}."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            reasons.append(
                f"Coercion is moderate ({coercion_score:.2f}); alternatives were considered "
                "and either none are feasibly less coercive or the act is justified."
            )
            return Verdict.ACCEPTABLE_WITH_RESERVATIONS

        # Low coercion.
        if epistemic_score >= self.data_quality_good and n_unknowns == 0:
            reasons.append(
                f"Coercion is low ({coercion_score:.2f}) and the epistemic basis is good "
                f"({epistemic_score:.2f}) with no outstanding unknowns."
            )
            return Verdict.ACCEPTABLE
        reasons.append(
            f"Coercion is low ({coercion_score:.2f}); accepted with reservations because of "
            "residual uncertainty or outstanding unknowns."
        )
        return Verdict.ACCEPTABLE_WITH_RESERVATIONS

    def _apply_downgrades(
        self, *, verdict, coercion_score, alternatives, consent, agency, reasons
    ) -> Verdict:
        """Apply consent/vulnerability/alternative downgrades to a base verdict."""
        # A feasible less coercive alternative should pull any positive verdict down (A2).
        if alternatives.has_feasible_less_coercive and verdict in _POSITIVE:
            verdict = _downgrade(verdict)
            reasons.append(
                "A feasible less coercive alternative exists; the verdict is downgraded (A2)."
            )

        # Invalid consent (refused/coerced) over a positive verdict is suspicious.
        if consent.valid is False and verdict in _POSITIVE:
            verdict = Verdict.ETHICALLY_SUSPICIOUS
            reasons.append(
                "Consent is absent or invalid (refused/coerced); a positive verdict is "
                "downgraded to ethically suspicious."
            )

        # Disputed consent must block confident approval.
        if consent.blocks_confident_approval and verdict == Verdict.ACCEPTABLE:
            verdict = Verdict.ACCEPTABLE_WITH_RESERVATIONS
            reasons.append("Consent is contested; confident approval is withheld.")

        # High vulnerability with non-valid consent raises scrutiny one notch.
        if agency.high_vulnerability and consent.valid is not True and verdict in _POSITIVE:
            verdict = _downgrade(verdict)
            reasons.append(
                "The affected subject is highly vulnerable and consent is not clearly valid; "
                "scrutiny is raised (verdict downgraded)."
            )
        return verdict

    # -- explanation ----------------------------------------------------------

    def _build_explanation(
        self, *, verdict, coercion_score, confidence, uncertainty, reasons, missing_data
    ) -> str:
        """Compose a clear, non-rhetorical summary paragraph."""
        parts = [
            f"Verdict: {verdict.value} (coercion {coercion_score:.2f}, "
            f"confidence {confidence:.2f}, uncertainty {uncertainty})."
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
