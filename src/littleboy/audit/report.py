"""Rendering helpers for audit reports (JSON for machines, text for terminals).

These add no judgment of their own; they only present what the audit found. Text
output shows the red flags, the bias and adversarial risks, the adversarial
'what if' questions, whether the judgment is stable, and what could reverse it.
"""

from __future__ import annotations

import json

from littleboy.audit.models import AuditReport, ComparisonAuditReport


def render_audit_json(report: AuditReport, *, indent: int = 2) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def _risk_lines(label: str, profile, *, threshold: float = 0.01) -> list[str]:
    fields = type(profile).RISK_FIELDS
    shown = [(f, getattr(profile, f)) for f in fields if getattr(profile, f) >= threshold]
    shown.sort(key=lambda kv: kv[1], reverse=True)
    if not shown:
        return [f"{label}: (no indicators above zero)"]
    return [f"{label}:"] + [f"  {name} = {value:.2f}" for name, value in shown]


def render_audit_text(report: AuditReport) -> str:
    """Render an audit report as a readable, sectioned text block."""
    lines: list[str] = []
    lines.append(
        f"ADVERSARIAL AUDIT ({report.target})   "
        f"judgment_stable={report.judgment_stable}   "
        f"requires_explicit_review={report.requires_explicit_review}"
    )
    lines.append(
        "LittleBoy must judge not only the action, but also the description through which "
        "the action becomes visible."
    )

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section(
        "Red flags",
        [
            f"[{f.severity.value}/{f.category.value}] {f.title}"
            for f in report.findings
            if f.severity.value in {"serious", "critical"}
        ],
    )
    _section(
        "Other findings",
        [
            f"[{f.severity.value}/{f.category.value}] {f.title}"
            for f in report.findings
            if f.severity.value in {"info", "warning"}
        ],
    )

    lines.append("")
    lines.extend(_risk_lines("Adversarial risks", report.adversarial_risk_profile, threshold=0.3))
    lines.append("")
    lines.extend(_risk_lines("Bias risks", report.bias_profile, threshold=0.3))

    _section(
        "Adversarial stress tests (what-if)",
        [
            f"{s.question}  [plausibility {s.plausibility:.2f}; "
            f"could change verdict: {s.could_change_judgment}]"
            for s in report.stress_tests
        ],
    )
    _section("Recommended questions", report.recommended_questions)
    _section("What could reverse / reshape the judgment", _reversers(report))
    _section("Warnings", report.warnings)
    return "\n".join(lines)


def _reversers(report: AuditReport) -> list[str]:
    """The specific things that, if resolved, could change the judgment."""
    items: list[str] = []
    for f in report.findings:
        if f.severity.value in {"serious", "critical"}:
            items.extend(f.recommended_questions)
    for s in report.stress_tests:
        if s.could_change_judgment:
            items.append(f"resolve: {s.question}")
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def render_comparison_audit_json(report: ComparisonAuditReport, *, indent: int = 2) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def render_comparison_audit_text(report: ComparisonAuditReport) -> str:
    """Render a comparison audit as a readable, sectioned text block."""
    lines: list[str] = []
    lines.append(
        "COMPARISON AUDIT   "
        f"ranking_unstable_due_to_missing_data={report.ranking_unstable_due_to_missing_data}"
    )

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section(
        "Cross-option findings",
        [f"[{f.severity.value}/{f.category.value}] {f.title}" for f in report.findings],
    )
    lines.append("")
    lines.append("Per-option audit summary:")
    if not report.option_audits:
        lines.append("  (none)")
    for oid, audit in report.option_audits.items():
        red = len(audit.red_flags)
        lines.append(
            f"  {oid}: stable={audit.judgment_stable}  red_flags={red}  "
            f"adversarial_max={audit.adversarial_risk_profile.max_risk:.2f}"
        )
    _section("Warnings", report.warnings)
    return "\n".join(lines)
