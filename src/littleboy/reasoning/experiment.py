"""Ethical Experiment Runner v0.1 for LittleBoy.

An *ethical experiment* is a theoretical simulation with two functions:

* **falsificatory**: test the logical consistency of the case against the axioms
  (does the case assert things that contradict one another?);
* **heuristic / applicative**: identify whether and how the action can be judged
  under the current data, and what would need to be known to judge it.

This runner does not pretend to solve every case. Its job is to expose whether
an :class:`~littleboy.core.models.ActionCase` *can* be judged under current data,
to surface contradictions, and to name the open questions. It builds on the
evaluator rather than duplicating it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import ConsentStatus, EpistemicStatus, Verdict
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.gates import detect_missing_critical_data, recommended_next_questions
from littleboy.core.models import ActionCase


class EthicalExperimentResult(BaseModel):
    """The auditable output of running an :class:`EthicalExperiment`."""

    model_config = ConfigDict(extra="forbid")

    tested_axioms: list[str] = Field(default_factory=list)
    derived_findings: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    insufficient_data_points: list[str] = Field(default_factory=list)
    risk_of_coercion: float = Field(default=0.0, ge=0.0, le=1.0)
    recommended_next_questions: list[str] = Field(default_factory=list)
    provisional_verdict: Verdict
    can_be_judged: bool = True


class EthicalExperiment:
    """Run a falsificatory + heuristic experiment over a single action case."""

    def __init__(self, evaluator: EthicalEvaluator | None = None) -> None:
        self.evaluator = evaluator or EthicalEvaluator()

    def run(self, case: ActionCase) -> EthicalExperimentResult:
        report = self.evaluator.evaluate(case)

        derived = self._derive_findings(case, report)
        contradictions = self._find_contradictions(case, report)

        return EthicalExperimentResult(
            tested_axioms=list(report.axioms_invoked),
            derived_findings=derived,
            contradictions=contradictions,
            insufficient_data_points=detect_missing_critical_data(case),
            risk_of_coercion=report.coercion_score,
            recommended_next_questions=recommended_next_questions(case),
            provisional_verdict=report.verdict,
            can_be_judged=report.verdict != Verdict.INSUFFICIENT_DATA,
        )

    # -- internals ------------------------------------------------------------

    def _derive_findings(self, case: ActionCase, report) -> list[str]:
        findings = [
            f"Coercion score is {report.coercion_score:.2f}.",
            f"Epistemic basis (data quality {report.data_quality_score:.2f}, "
            f"evidence {report.evidence_score:.2f}); confidence {report.confidence:.2f}.",
            f"Effective consent: {report.consent_status}.",
            f"Agency: {report.agency_status}.",
        ]
        if report.justification_result is not None:
            findings.append(
                f"Axiom 3 justification: is_justified={report.justification_result.is_justified}, "
                f"confidence {report.justification_result.confidence:.2f}."
            )
        if report.alternatives_analysis is not None:
            aa = report.alternatives_analysis
            if not aa.evaluated:
                findings.append("Alternatives were not analysed.")
            else:
                findings.append(
                    f"{len(aa.feasible_less_coercive)} feasible less-coercive "
                    f"alternative(s) identified out of {aa.count}."
                )
        if report.main_reasons:
            findings.append(f"Decisive reason: {report.main_reasons[0]}")
        return findings

    def _find_contradictions(self, case: ActionCase, report) -> list[str]:
        """Falsificatory pass: surface internal inconsistencies in the case."""
        contradictions: list[str] = []
        just = case.justification
        aa = report.alternatives_analysis

        if (
            just is not None
            and just.no_less_coercive_alternative_available.is_affirmative
            and aa is not None
            and aa.has_feasible_less_coercive
        ):
            contradictions.append(
                "The justification asserts no less coercive alternative is available, but a "
                "feasible less coercive alternative was identified."
            )

        if (
            just is not None
            and case.responds_to_existing_coercion is False
            and just.responds_to_existing_or_imminent_coercion.is_affirmative
        ):
            contradictions.append(
                "The case states the action does not respond to prior/imminent coercion, yet "
                "the justification claims that it does."
            )

        profile = case.consent_profile
        if profile is not None:
            if (
                profile.status == ConsentStatus.GIVEN
                and profile.voluntary == EpistemicStatus.DISPUTED
            ):
                contradictions.append(
                    "Consent is reported as GIVEN but its voluntariness is disputed."
                )
            if profile.status == ConsentStatus.COERCED and profile.voluntary.is_affirmative:
                contradictions.append("Consent is marked COERCED yet also claimed to be voluntary.")

        return contradictions
