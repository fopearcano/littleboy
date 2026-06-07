"""The first LittleBoy ethical evaluator.

:class:`EthicalEvaluator` takes an :class:`~littleboy.core.models.ActionCase` and
produces an :class:`~littleboy.core.models.EvaluationReport`. The decision rule
is deliberately simple and fully legible -- it is a *first* evaluator, not the
final word. Its guiding commitments:

* It applies the LittleBoy axioms (see :mod:`littleboy.core.axioms`).
* It never feigns certainty: poor data or unresolved unknowns push it toward
  ``INSUFFICIENT_DATA`` and always lower confidence (Axiom 5).
* It is never a black box: every report exposes the axioms invoked, the
  coercion reasoning, the data-quality reasoning, what is missing, and which
  alternatives were considered.
"""

from __future__ import annotations

from littleboy.core import axioms as ax
from littleboy.core.enums import ConsentStatus, Verdict
from littleboy.core.models import ActionCase, EvaluationReport
from littleboy.core.scoring import score_coercion
from littleboy.data.quality import (
    assess_data_quality,
    classify_uncertainty,
    compute_confidence,
)

# --- Decision thresholds (all transparent and overridable per evaluator) -----
DEFAULT_COERCION_HIGH = 0.60
DEFAULT_COERCION_MODERATE = 0.30
DEFAULT_DATA_QUALITY_FLOOR = 0.35
DEFAULT_DATA_QUALITY_GOOD = 0.70
DEFAULT_MIN_CONFIDENCE = 0.30

# A standing disclaimer attached to every report.
SCOPE_DISCLAIMER = (
    "LittleBoy produces a transparent heuristic judgment, not absolute moral truth. "
    "It is NOT a legal, medical, or emergency decision-maker."
)


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
        # 1. Score coercion (the central ethical quantity).
        if case.coercion_profile is not None:
            coercion = score_coercion(case.coercion_profile)
            coercion_score = coercion.score
            coercion_reasoning = list(coercion.reasoning)
        else:
            coercion_score = 0.0
            coercion_reasoning = [
                "no coercion profile supplied; coercion could not be characterised"
            ]

        # 2. Assess data quality.
        dq = assess_data_quality(case.data_quality)
        data_quality_score = dq.score

        # 3. Identify structural unknowns and assemble missing-data notes.
        unknowns, missing_data = self._collect_unknowns(case, coercion_score)
        missing_data.extend(f"missing critical fact: {fact}" for fact in dq.missing_facts)

        # 4. Confidence and uncertainty (Axiom 5 in action).
        confidence = compute_confidence(data_quality_score, len(unknowns))
        uncertainty = classify_uncertainty(confidence)
        data_quality_reasoning = list(dq.reasoning)
        data_quality_reasoning.append(
            f"confidence = data_quality_score {data_quality_score:.2f} reduced for "
            f"{len(unknowns)} structural unknown(s) -> {confidence:.2f} "
            f"(uncertainty: {uncertainty.value})"
        )

        # 5. Check any Axiom 3 justification.
        justification = ax.check_coercion_justification(case.justification)

        # 6. Compare alternatives.
        less_coercive, alt_warnings = self._analyse_alternatives(case, coercion_score)

        # 7. Decide.
        verdict, reasons, axiom_ids, warnings = self._decide(
            case=case,
            coercion_score=coercion_score,
            data_quality_score=data_quality_score,
            confidence=confidence,
            unknowns=unknowns,
            justification=justification,
            less_coercive=less_coercive,
        )
        warnings.extend(alt_warnings)
        warnings.append(SCOPE_DISCLAIMER)

        # 8. Assemble the report.
        return EvaluationReport(
            verdict=verdict,
            coercion_score=round(coercion_score, 4),
            data_quality_score=round(data_quality_score, 4),
            confidence=round(confidence, 4),
            uncertainty_level=uncertainty,
            main_reasons=reasons,
            coercion_reasoning=coercion_reasoning,
            data_quality_reasoning=data_quality_reasoning,
            missing_data=missing_data,
            less_coercive_alternatives=less_coercive,
            axioms_invoked=[ax.cite(i) for i in _unique(axiom_ids)],
            warnings=warnings,
        )

    # -- internals ------------------------------------------------------------

    def _collect_unknowns(
        self, case: ActionCase, coercion_score: float
    ) -> tuple[list[str], list[str]]:
        """Return ``(unknown_keys, missing_data_notes)`` for the case.

        These are the six structural unknowns that Axiom 5 requires us to track:
        consent, agent type, alternatives, coercion source, consequences, and
        reversibility.
        """
        unknowns: list[str] = []
        missing: list[str] = []

        agent = case.acting_agent
        if agent is None or not agent.type_is_known:
            unknowns.append("agent_type")
            missing.append("acting agent type is unknown (cannot assign duties under Axiom 4)")

        if case.consent == ConsentStatus.UNKNOWN:
            unknowns.append("consent")
            missing.append("consent status of affected agents is unknown")

        if case.available_alternatives is None:
            unknowns.append("alternatives")
            missing.append("less-coercive alternatives were not analysed")

        if case.expected_consequences is None:
            unknowns.append("consequences")
            missing.append("expected consequences of the action are unknown")

        # Reversibility is unknown if there is no profile, or the field is None.
        if case.coercion_profile is None or not case.coercion_profile.reversibility_is_known:
            unknowns.append("reversibility")
            missing.append("reversibility of the coercion is unknown")

        # The coercion source only matters once coercion is non-trivial.
        if coercion_score >= self.coercion_moderate and case.responds_to_existing_coercion is None:
            unknowns.append("coercion_source")
            missing.append("the coercion source is unknown (is this a response to prior coercion?)")

        return unknowns, missing

    def _analyse_alternatives(
        self, case: ActionCase, coercion_score: float
    ) -> tuple[list[str], list[str]]:
        """Identify alternatives that appear less coercive than the action."""
        less_coercive: list[str] = []
        warnings: list[str] = []
        if not case.available_alternatives:
            return less_coercive, warnings

        for alt in case.available_alternatives:
            if alt.coercion_profile is None:
                warnings.append(
                    f"alternative '{alt.description}' has no coercion profile; "
                    "its coercion is unquantified"
                )
                continue
            alt_score = score_coercion(alt.coercion_profile).score
            if alt_score < coercion_score - 0.05:
                less_coercive.append(
                    f"{alt.description} (coercion ~{alt_score:.2f} vs {coercion_score:.2f})"
                )
        return less_coercive, warnings

    def _decide(
        self,
        *,
        case: ActionCase,
        coercion_score: float,
        data_quality_score: float,
        confidence: float,
        unknowns: list[str],
        justification: ax.JustificationResult,
        less_coercive: list[str],
    ) -> tuple[Verdict, list[str], list[str], list[str]]:
        """Apply the decision rule. Returns (verdict, reasons, axiom_ids, warnings)."""
        reasons: list[str] = []
        axiom_ids: list[str] = ["A0", "A1"]  # foundation + duty to interrogate
        warnings: list[str] = []

        # Axiom 4: note the acting agent's duty-bearing status.
        agent = case.acting_agent
        axiom_ids.append("A4")
        if agent is None or not agent.type_is_known:
            warnings.append(
                "Acting agent type is unknown; duty-bearing status (Axiom 4) is undetermined."
            )
        elif agent.can_bear_duties:
            reasons.append(
                f"Acting agent '{agent.name}' is Type II and can bear moral duties (A4)."
            )
        else:
            reasons.append(
                f"Acting agent '{agent.name}' is Type I and cannot bear moral duties (A4); "
                "this evaluation assesses coercion in the world, not the agent's culpability."
            )
            warnings.append("Acting agent is Type I: duties do not bind it (Axiom 4).")

        # Gate 0: is there enough to judge at all? (Axiom 5)
        insufficient = (
            case.data_quality is None
            or case.coercion_profile is None
            or data_quality_score < self.data_quality_floor
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
            if case.data_quality is None:
                reasons.append("No data-quality profile was provided.")
            if case.data_quality is not None and data_quality_score < self.data_quality_floor:
                reasons.append(
                    f"Data-quality score {data_quality_score:.2f} is below the floor "
                    f"{self.data_quality_floor:.2f}."
                )
            if confidence < self.min_confidence:
                reasons.append(
                    f"Confidence {confidence:.2f} is below the minimum {self.min_confidence:.2f}."
                )
            return Verdict.INSUFFICIENT_DATA, reasons, axiom_ids, warnings

        # From here, data are sufficient. Axiom 2 governs: minimise coercion.
        axiom_ids.append("A2")
        verdict = self._decide_by_coercion(
            case=case,
            coercion_score=coercion_score,
            data_quality_score=data_quality_score,
            unknowns=unknowns,
            justification=justification,
            less_coercive=less_coercive,
            reasons=reasons,
            axiom_ids=axiom_ids,
        )

        # Post-adjustment: an action over a refused consent is presumptively coercive.
        if case.consent == ConsentStatus.REFUSED and verdict == Verdict.ACCEPTABLE:
            verdict = Verdict.ACCEPTABLE_WITH_RESERVATIONS
            reasons.append(
                "Consent was refused; an action against refusal is presumptively coercive, "
                "so acceptance is downgraded to 'with reservations'."
            )

        # Honest-uncertainty note (Axiom 5) even when we did reach a verdict.
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
        data_quality_score: float,
        unknowns: list[str],
        justification: ax.JustificationResult,
        less_coercive: list[str],
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
            if not justification.justified:
                reasons.append(
                    f"Coercion is high ({coercion_score:.2f}) and the justification fails "
                    f"Axiom 3 condition(s): {', '.join(justification.failed_conditions)}."
                )
                return Verdict.NOT_ACCEPTABLE
            if case.available_alternatives is None:
                reasons.append(
                    "Coercion is high and claimed justified, but alternatives were not "
                    "analysed, so 'no less coercive alternative' cannot be verified."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            if less_coercive:
                reasons.append(
                    f"Coercion is high and justified only in claim, but less coercive "
                    f"alternatives appear to exist: {'; '.join(less_coercive)}."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            reasons.append(
                "Coercion is high but a complete Axiom 3 justification is supplied and no "
                "less coercive alternative was found; accepted only with reservations."
            )
            return Verdict.ACCEPTABLE_WITH_RESERVATIONS

        if coercion_score >= self.coercion_moderate:
            axiom_ids.append("A3")
            if case.available_alternatives is None:
                reasons.append(
                    f"Coercion is moderate ({coercion_score:.2f}) but alternatives were "
                    "not analysed; less coercive options may exist."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            if less_coercive and not justification.justified:
                reasons.append(
                    f"Coercion is moderate ({coercion_score:.2f}) and less coercive "
                    f"alternatives exist: {'; '.join(less_coercive)}."
                )
                return Verdict.ETHICALLY_SUSPICIOUS
            reasons.append(
                f"Coercion is moderate ({coercion_score:.2f}); alternatives were considered "
                "and either none are less coercive or the act is justified."
            )
            return Verdict.ACCEPTABLE_WITH_RESERVATIONS

        # Low coercion.
        if data_quality_score >= self.data_quality_good and not unknowns:
            reasons.append(
                f"Coercion is low ({coercion_score:.2f}) and data quality is good "
                f"({data_quality_score:.2f}) with no outstanding unknowns."
            )
            return Verdict.ACCEPTABLE
        reasons.append(
            f"Coercion is low ({coercion_score:.2f}); accepted with reservations because of "
            "residual uncertainty or outstanding unknowns."
        )
        return Verdict.ACCEPTABLE_WITH_RESERVATIONS


def _unique(items: list[str]) -> list[str]:
    """Return items with duplicates removed, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
