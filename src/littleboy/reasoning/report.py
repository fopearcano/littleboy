"""Rendering helpers for an :class:`~littleboy.core.models.EvaluationReport`.

These functions turn a structured report into something a human can read --
either pretty JSON (for machines and logs) or an indented text block (for a
terminal). They add no judgment of their own; they only present what the
evaluator already decided.
"""

from __future__ import annotations

import json

from littleboy.core.models import (
    CaseCompletenessReport,
    EvaluationReport,
    QuestionSet,
)
from littleboy.language.models import LanguageAnalysis


def report_to_dict(report: EvaluationReport) -> dict:
    """Return the report as a plain ``dict`` (enums rendered as their values)."""
    return report.model_dump(mode="json")


def render_json(report: EvaluationReport, *, indent: int = 2) -> str:
    """Render the report as an indented JSON string (the machine-readable form)."""
    return json.dumps(report_to_dict(report), indent=indent, ensure_ascii=False)


def render_text(report: EvaluationReport) -> str:
    """Render the report as a readable, sectioned text block."""
    lines: list[str] = []
    lines.append(f"VERDICT: {report.verdict.value}   [policy: {report.policy_mode.value}]")
    lines.append(
        f"  coercion={report.coercion_score:.2f}  "
        f"data_quality={report.data_quality_score:.2f}  "
        f"evidence={report.evidence_score:.2f}  "
        f"confidence={report.confidence:.2f}  "
        f"uncertainty={report.uncertainty_level.value}"
    )
    if report.explanation:
        lines.append("")
        lines.append(report.explanation)
    if report.consent_status:
        lines.append("")
        lines.append(f"Consent: {report.consent_status}")
    if report.agency_status:
        lines.append(f"Agency:  {report.agency_status}")

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section("Main reasons", report.main_reasons)
    _section("Axioms invoked", report.axioms_invoked)
    _section("Coercion reasoning", report.coercion_reasoning)
    _section("Data-quality reasoning", report.data_quality_reasoning)
    _section("Evidence reasoning", report.evidence_reasoning)

    if report.justification_result is not None:
        jr = report.justification_result
        _section(
            "Coercion justification (Axiom 3)",
            [
                f"is_justified = {jr.is_justified} (confidence {jr.confidence:.2f})",
                *(f"satisfied: {c}" for c in jr.satisfied_conditions),
                *(f"failed: {c}" for c in jr.failed_conditions),
                *(f"unknown: {c}" for c in jr.unknown_conditions),
            ],
        )

    if report.alternatives_analysis is not None:
        aa = report.alternatives_analysis
        _section(
            "Alternatives analysis (Axiom 2)",
            [
                f"evaluated = {aa.evaluated}, count = {aa.count}",
                *(f"feasible less coercive: {a}" for a in aa.feasible_less_coercive),
                *(f"less coercive but infeasible: {a}" for a in aa.infeasible_less_coercive),
                *(f"unquantified: {a}" for a in aa.unquantified),
            ],
        )

    if report.language_analysis is not None:
        la = report.language_analysis
        _section(
            "Language analysis",
            [
                f"linguistic_coercion = {la.linguistic_coercion_score:.2f}",
                f"constructive = {la.constructive.constructive_score:.2f}  "
                f"agency_support = {la.constructive.agency_support:.2f}",
                f"affects_consent = {la.affects_consent}  "
                f"replaces_subject_framing = {la.replaces_subject_framing}",
                *(f"indicator: {i}" for i in la.dominant_indicators),
                *(f"finding: {f.indicator} ({f.evidence})" for f in la.manipulation_findings),
            ],
        )

    if report.temporal_projection is not None and report.temporal_projection.has_temporal_data:
        tp = report.temporal_projection
        _section(
            "Temporal projection",
            [
                f"trend = {tp.trend}; stable across horizons = {tp.stable}",
                f"immediate = {tp.immediate_coercion:.2f}  "
                f"long-term = {tp.long_term_coercion:.2f}  "
                f"cumulative = {tp.cumulative_coercion:.2f}  expected total = "
                f"{tp.expected_total_coercion:.2f}",
                f"prevents greater future coercion = {tp.prevents_greater_future_coercion}; "
                f"creates long-term dependency = {tp.creates_long_term_dependency}; "
                f"reversible now / irreversible later = {tp.reversible_now_irreversible_later}",
                *(f"high-risk unknown: {u}" for u in tp.high_risk_unknowns),
            ],
        )

    _section("Missing data", report.missing_data)

    if report.reasoning_trace is not None:
        tr = report.reasoning_trace
        applied = [f"{r.rule_id} {r.name}: {r.status.value}/{r.severity.value}" for r in tr.applied]
        _section(f"Applied rules ({tr.policy_mode.value})", applied)
        _section("Blockers", tr.blockers)
        _section("Contradictions", tr.contradictions)
        _section("Confidence adjustments", tr.confidence_adjustments)

    _section("Warnings", report.warnings)

    if report.case_completeness is not None:
        cc = report.case_completeness
        lines.append("")
        lines.append(
            f"Case completeness: score={cc.completeness_score:.2f}  "
            f"can_evaluate={cc.can_evaluate}  "
            f"can_confidently_evaluate={cc.can_confidently_evaluate}"
        )
        _section("Critical missing fields", cc.critical_missing_fields)

    if report.recommended_questions:
        _section(
            "Recommended questions",
            [
                f"[{q.priority.value}] {q.text}  (why: {q.why_it_matters})"
                for q in report.recommended_questions
            ],
        )
    elif report.ethical_experiment is not None and report.ethical_experiment.open_questions:
        _section("Recommended next questions", report.ethical_experiment.open_questions)

    return "\n".join(lines)


def completeness_to_dict(
    report: CaseCompletenessReport, questions: QuestionSet | None = None
) -> dict:
    """Return the completeness report (and optional question set) as a plain dict."""
    payload: dict = {"completeness": report.model_dump(mode="json")}
    if questions is not None:
        payload["questions"] = [q.model_dump(mode="json") for q in questions.questions]
    return payload


def render_completeness_json(
    report: CaseCompletenessReport, questions: QuestionSet | None = None, *, indent: int = 2
) -> str:
    """Render a completeness report (+ optional questions) as indented JSON."""
    return json.dumps(completeness_to_dict(report, questions), indent=indent, ensure_ascii=False)


def render_completeness_text(
    report: CaseCompletenessReport, questions: QuestionSet | None = None
) -> str:
    """Render a completeness report (+ optional questions) as readable text."""
    lines: list[str] = []
    lines.append(f"COMPLETENESS: score={report.completeness_score:.2f}")
    lines.append(
        f"  can_evaluate={report.can_evaluate}  "
        f"can_confidently_evaluate={report.can_confidently_evaluate}"
    )

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section("Critical missing fields", report.critical_missing_fields)
    _section("High-priority missing fields", report.high_priority_missing_fields)
    _section("Optional missing fields", report.optional_missing_fields)
    _section("Warnings", report.warnings)

    shown = questions.questions if questions is not None else report.recommended_next_questions
    lines.append("")
    lines.append("Questions:")
    if not shown:
        lines.append("  (none)")
    for q in shown:
        axioms = (" [" + ", ".join(q.related_axioms) + "]") if q.related_axioms else ""
        block = " (blocks evaluation)" if q.blocks_evaluation else ""
        lines.append(f"  [{q.priority.value}/{q.category.value}]{axioms}{block} {q.text}")
        lines.append(f"      why it matters: {q.why_it_matters}")
    return "\n".join(lines)


def render_language_json(analysis: LanguageAnalysis, *, indent: int = 2) -> str:
    """Render a language analysis as indented JSON (the machine-readable form)."""
    return json.dumps(analysis.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def render_language_text(analysis: LanguageAnalysis) -> str:
    """Render a language analysis as a readable text block."""
    c = analysis.constructive
    lines = [
        f"LINGUISTIC COERCION: {analysis.linguistic_coercion_score:.2f}   "
        f"CONSTRUCTIVE: {c.constructive_score:.2f}",
        f"  affects_consent={analysis.affects_consent}  "
        f"replaces_subject_framing={analysis.replaces_subject_framing}",
        f"  agency_support={c.agency_support:.2f}  "
        f"alternative_visibility={c.alternative_visibility:.2f}  "
        f"clarifying_effect={c.clarifying_effect:.2f}",
    ]

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section("Dominant indicators", analysis.dominant_indicators)
    _section(
        "Manipulation findings",
        [
            f"{f.indicator}: {f.evidence} (severity {f.severity:.2f})"
            for f in analysis.manipulation_findings
        ],
    )
    _section("Warnings", analysis.warnings)
    _section("Missing data", analysis.missing_data)
    _section("Recommended questions", analysis.recommended_questions)
    lines.append("")
    lines.append("Recommended rewrite:")
    lines.append(f"  {c.recommended_rewrite}")
    return "\n".join(lines)
