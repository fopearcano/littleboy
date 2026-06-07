"""The adversarial stress tester: the audit's public orchestration point.

:class:`AdversarialStressTester` composes the red-flag detectors, the bias and
adversarial-risk profiles, the ideological-capture checks, and a set of
adversarial 'what if' stress tests into a single :class:`AuditReport` (or, for a
comparison, a :class:`ComparisonAuditReport`). It never mutates its inputs and
never asserts an adversarial assumption is *true*; it asks whether the judgment
would survive if it were, and exposes the data that would settle it.

``core.models`` / ``comparison.models`` are imported only for type hints. The
few helpers that pull in heavier modules (``analyze_language``,
``project_temporal``, ``get_policy``) are imported lazily, so importing this
module while ``core.models`` is still loading cannot create a cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.audit import red_flags as rf
from littleboy.audit.adversarial import assess_adversarial_risk
from littleboy.audit.bias import assess_bias
from littleboy.audit.models import (
    AdversarialRiskProfile,
    AuditCategory,
    AuditFinding,
    AuditReport,
    AuditSeverity,
    BiasProfile,
    ComparisonAuditReport,
    StressTestResult,
    severity_rank,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.comparison.models import ActionComparisonResult, ActionComparisonSet
    from littleboy.core.models import ActionCase, EvaluationReport
    from littleboy.language.models import LanguageAnalysis
    from littleboy.temporal.models import TemporalProjectionResult

_S = AuditSeverity
_C = AuditCategory


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class AdversarialStressTester:
    """Audit a case, an evaluation, or a comparison for description-level risk."""

    def __init__(self, policy=None) -> None:
        # Resolve the policy lazily: importing ``rules.policy`` at module top would
        # pull in the rule engine (and ``core.models``) before it has finished
        # loading. By call time everything is initialised.
        from littleboy.rules.policy import get_policy

        self.policy = get_policy(policy)

    # -- public API -----------------------------------------------------------

    def audit_case(self, case: ActionCase) -> AuditReport:
        """Audit a bare case (no evaluation): inspect how it is described and evidenced."""
        analysis = self._analyse_language(case)
        temporal = self._project_temporal(case)
        coercion_score = rf.bare_coercion_score(case)
        return self._build_report(
            case,
            target="case",
            analysis=analysis,
            temporal=temporal,
            coercion_score=coercion_score,
            report=None,
        )

    def audit_evaluation(self, case: ActionCase, report: EvaluationReport) -> AuditReport:
        """Audit a completed evaluation: everything in :meth:`audit_case` plus report-aware risk."""
        analysis = report.language_analysis
        temporal = report.temporal_projection
        return self._build_report(
            case,
            target="evaluation",
            analysis=analysis,
            temporal=temporal,
            coercion_score=report.coercion_score,
            report=report,
        )

    def audit_comparison(
        self, comparison_set: ActionComparisonSet, result: ActionComparisonResult
    ) -> ComparisonAuditReport:
        """Audit a whole comparison: per-option audits plus cross-option framing/data risks."""
        options_by_id = {opt.option_id: opt for opt in comparison_set.options}
        option_audits: dict[str, AuditReport] = {}
        for opt in comparison_set.options:
            rep = result.individual_reports.get(opt.option_id)
            option_audits[opt.option_id] = (
                self.audit_evaluation(opt.case, rep)
                if rep is not None
                else self.audit_case(opt.case)
            )

        findings = rf.comparison_red_flags(result, options_by_id)

        # Does the leader benefit from framing / beauty bias?
        if result.ranking:
            top_id = result.ranking[0].option_id
            top_audit = option_audits.get(top_id)
            if top_audit is not None and top_audit.bias_profile.language_beauty_bias_risk >= 0.5:
                findings.append(
                    rf._finding(
                        "AUD-CMP-TOP-BEAUTY-BIAS",
                        "The top option may benefit from persuasive presentation",
                        "The leading option's description shows high language-beauty bias risk; "
                        "its lead may owe something to presentation.",
                        severity=_S.SERIOUS,
                        category=_C.FRAMING,
                        why="A ranking should reward the least coercive option, not the best-"
                        "presented one.",
                        fields=["ranking"],
                        questions=[
                            "Would the leader still win if described as plainly as the others?"
                        ],
                        confidence=0.5,
                    )
                )

        # Is any option blocked for want of data?
        any_insufficient = any(
            r.verdict.value == "INSUFFICIENT_DATA" for r in result.individual_reports.values()
        )
        advantaged_by_missing = any(
            f.finding_id == "AUD-CMP-ADVANTAGED-BY-MISSING-DATA" for f in findings
        )
        unstable_missing = bool(result.data_sensitive or advantaged_by_missing or any_insufficient)

        warnings: list[str] = []
        if unstable_missing:
            warnings.append(
                "the ranking is unstable: it may turn on data that is missing rather than on the "
                "merits of the options"
            )
        critical_options = [oid for oid, a in option_audits.items() if a.has_critical]
        if critical_options:
            warnings.append(
                "option(s) carry a critical audit red flag: " + ", ".join(critical_options)
            )

        reasoning = [
            "comparison audit indicators are risk flags, not proofs",
            f"{len(comparison_set.options)} option(s) audited; "
            f"{len(findings)} cross-option finding(s)",
        ]

        return ComparisonAuditReport(
            option_audits=option_audits,
            findings=findings,
            ranking_unstable_due_to_missing_data=unstable_missing,
            warnings=warnings,
            reasoning=reasoning,
        )

    # -- assembly -------------------------------------------------------------

    def _build_report(
        self,
        case: ActionCase,
        *,
        target: str,
        analysis: LanguageAnalysis | None,
        temporal: TemporalProjectionResult | None,
        coercion_score: float,
        report: EvaluationReport | None,
    ) -> AuditReport:
        moderate = self.policy.coercion_moderate

        findings: list[AuditFinding] = []
        findings += rf.consent_red_flags(case, analysis=analysis)
        findings += rf.coercion_red_flags(case, analysis=analysis, coercion_moderate=moderate)
        findings += rf.evidence_red_flags(
            case, coercion_score=coercion_score, coercion_moderate=moderate
        )
        findings += rf.language_red_flags(case, analysis)
        findings += rf.temporal_red_flags(
            case, temporal, coercion_score=coercion_score, coercion_moderate=moderate
        )

        adversarial, adv_findings = assess_adversarial_risk(
            case,
            analysis=analysis,
            report=report,
            coercion_score=coercion_score,
            coercion_moderate=moderate,
        )
        findings += adv_findings

        bias, bias_findings = assess_bias(
            case, analysis=analysis, report=report, coercion_score=coercion_score
        )
        findings += bias_findings

        stress_tests = self._generate_stress_tests(
            case,
            analysis=analysis,
            temporal=temporal,
            adversarial=adversarial,
            coercion_score=coercion_score,
            moderate=moderate,
        )

        has_critical = any(f.severity == _S.CRITICAL for f in findings)
        unstable_stress = any(
            s.could_change_judgment and s.plausibility >= 0.6 for s in stress_tests
        )
        judgment_stable = not has_critical and adversarial.max_risk < 0.7 and not unstable_stress
        requires_review = (
            has_critical
            or adversarial.ideological_capture_risk >= 0.6
            or bias.language_beauty_bias_risk >= 0.6
        )

        warnings = self._summary_warnings(findings, adversarial, bias, judgment_stable)
        reasoning = [
            "audit indicators are risk flags, not proofs of manipulation or bias",
            "LittleBoy must judge not only the action, but also the description through which the "
            "action becomes visible",
            f"{len(findings)} finding(s); adversarial max-risk {adversarial.max_risk:.2f}; "
            f"bias max-risk {bias.max_risk:.2f}",
        ]

        return AuditReport(
            target=target,
            findings=findings,
            adversarial_risk_profile=adversarial,
            bias_profile=bias,
            stress_tests=stress_tests,
            warnings=warnings,
            judgment_stable=judgment_stable,
            requires_explicit_review=requires_review,
            reasoning=reasoning,
        )

    def _summary_warnings(
        self,
        findings: list[AuditFinding],
        adversarial: AdversarialRiskProfile,
        bias: BiasProfile,
        stable: bool,
    ) -> list[str]:
        warnings: list[str] = []
        red = [f.title for f in findings if severity_rank(f.severity) >= severity_rank(_S.SERIOUS)]
        if not stable:
            warnings.append(
                "this judgment is UNSTABLE under adversarial audit; treat the verdict as "
                "provisional and resolve the red flags first"
            )
        if red:
            warnings.append(f"{len(red)} red flag(s) raised by the audit")
        if adversarial.dominant_risks:
            warnings.append("dominant adversarial risks: " + ", ".join(adversarial.dominant_risks))
        if bias.dominant_risks:
            warnings.append("dominant bias risks: " + ", ".join(bias.dominant_risks))
        return warnings

    # -- adversarial 'what if' stress tests -----------------------------------

    def _generate_stress_tests(
        self,
        case: ActionCase,
        *,
        analysis: LanguageAnalysis | None,
        temporal: TemporalProjectionResult | None,
        adversarial: AdversarialRiskProfile,
        coercion_score: float,
        moderate: float,
    ) -> list[StressTestResult]:
        tests: list[StressTestResult] = []
        cp = case.coercion_profile
        coercive = coercion_score >= moderate or (cp is not None and cp.severity >= 0.4)
        consent_given = case.effective_consent_status().value == "GIVEN"

        def add(
            question: str,
            assumption: str,
            fields: list[str],
            plausibility: float,
            could_change: bool,
            severity: AuditSeverity = _S.WARNING,
            note: str = "",
        ) -> None:
            tests.append(
                StressTestResult(
                    question=question,
                    assumption=assumption,
                    affected_fields=fields,
                    plausibility=round(_clamp(plausibility), 4),
                    could_change_judgment=could_change,
                    severity=severity,
                    note=note,
                )
            )

        # Underreporting coercion (almost always worth asking when coercion is described).
        if cp is not None or coercive or adversarial.leading_language_risk >= 0.4:
            near_threshold = 0.0 < (moderate - coercion_score) <= 0.15
            could = near_threshold or (
                coercion_score < moderate and adversarial.leading_language_risk >= 0.5
            )
            underreport_plausibility = 0.4 + 0.4 * max(
                adversarial.one_sided_description_risk, adversarial.leading_language_risk
            )
            add(
                "What if the acting agent is underreporting the coercion involved?",
                "the supplied coercion profile understates the real pressure",
                ["coercion_profile"],
                underreport_plausibility,
                could,
                _S.SERIOUS if could else _S.WARNING,
            )

        if consent_given:
            add(
                "What if the consent is contaminated (uninformed, involuntary, or coerced)?",
                "the recorded 'yes' is not valid consent",
                ["consent", "consent_profile"],
                max(0.4, adversarial.consent_contamination_risk),
                adversarial.consent_contamination_risk >= 0.5,
                _S.SERIOUS if adversarial.consent_contamination_risk >= 0.5 else _S.WARNING,
            )

        if adversarial.one_sided_description_risk >= 0.4 or case.evidence is None:
            add(
                "What if the affected agent's testimony is missing from the description?",
                "the affected party's account would change the picture",
                ["evidence", "affected_agents"],
                max(0.4, adversarial.one_sided_description_risk),
                adversarial.one_sided_description_risk >= 0.5,
            )

        if adversarial.fake_alternative_risk >= 0.4 or case.available_alternatives is None:
            add(
                "What if less-coercive alternatives exist but were not disclosed?",
                "a feasible, less-coercive option was omitted",
                ["available_alternatives"],
                max(0.4, adversarial.fake_alternative_risk),
                adversarial.fake_alternative_risk >= 0.5,
            )

        if adversarial.leading_language_risk >= 0.4:
            add(
                "What if the description is worded to lead LittleBoy toward a desired verdict?",
                "the language is engineered for a particular conclusion",
                ["language_act", "description"],
                adversarial.leading_language_risk,
                adversarial.leading_language_risk >= 0.5,
                _S.SERIOUS if adversarial.leading_language_risk >= 0.6 else _S.WARNING,
            )

        rising = temporal is not None and temporal.has_temporal_data and temporal.trend == "rising"
        if rising or (coercive and (temporal is None or not temporal.has_temporal_data)):
            add(
                "What if the long-term consequences are worse than described?",
                "delayed or cumulative coercion exceeds the stated immediate cost",
                ["consequences", "temporal_profile"],
                0.6 if rising else 0.45,
                bool(rising),
                _S.SERIOUS if rising else _S.WARNING,
            )

        if (
            adversarial.data_laundering_risk >= 0.4
            or adversarial.missing_counterevidence_risk >= 0.5
        ):
            add(
                "What if an option looks least-coercive only because data about it are missing?",
                "the favourable picture is an artefact of absent negative data",
                ["evidence", "data_quality"],
                max(adversarial.data_laundering_risk, adversarial.missing_counterevidence_risk),
                False,
            )

        return tests

    # -- lazy helpers ---------------------------------------------------------

    def _analyse_language(self, case: ActionCase) -> LanguageAnalysis | None:
        if case.language_act is None:
            return None
        from littleboy.language.analyzer import analyze_language

        return analyze_language(case.language_act)

    def _project_temporal(self, case: ActionCase) -> TemporalProjectionResult | None:
        has_temporal = any(
            (
                case.consequences is not None,
                case.temporal_profile is not None,
                case.reversibility_profile is not None,
                case.cumulative_coercion_profile is not None,
            )
        )
        if not has_temporal:
            return None
        from littleboy.temporal.projection import project_temporal

        return project_temporal(
            base_coercion=rf.bare_coercion_score(case),
            consequences=case.consequences,
            temporal_profile=case.temporal_profile,
            reversibility_profile=case.reversibility_profile,
            cumulative_profile=case.cumulative_coercion_profile,
            is_inaction=case.is_inaction,
        )
