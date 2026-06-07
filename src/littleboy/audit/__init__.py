"""LittleBoy adversarial audit & bias-testing (v0.8).

Core thesis: **a rational ethical engine must not merely evaluate actions; it
must also evaluate the conditions under which the action is being described.**
LittleBoy must judge not only the action, but also the description through which
the action becomes visible.

This package inspects a case, an evaluation, or a comparison for *description-
level* risk: leading language, missing or distorted evidence, ideological
framing, hidden coercion, asymmetric language, false consent, fake alternatives,
under-reported vulnerability, over-confident conclusions, and framings designed
to lead LittleBoy toward a desired verdict. Everything here is deterministic,
typed, and auditable; the indicators are *risk flags, not proofs*.

Import order matters: ``models`` is imported first because ``core.models`` embeds
an :class:`AuditReport`, and every other submodule depends on ``models``.
"""

from __future__ import annotations

from littleboy.audit.adversarial import (
    assess_adversarial_risk,
    audit_adjusted_verdict,
    ideological_capture_findings,
)
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
    max_severity,
    severity_rank,
)
from littleboy.audit.red_flags import (
    coercion_red_flags,
    comparison_red_flags,
    consent_red_flags,
    evidence_red_flags,
    language_red_flags,
    temporal_red_flags,
)
from littleboy.audit.report import (
    render_audit_json,
    render_audit_text,
    render_comparison_audit_json,
    render_comparison_audit_text,
)
from littleboy.audit.stress import AdversarialStressTester

__all__ = [
    "AdversarialRiskProfile",
    "AdversarialStressTester",
    "AuditCategory",
    "AuditFinding",
    "AuditReport",
    "AuditSeverity",
    "BiasProfile",
    "ComparisonAuditReport",
    "StressTestResult",
    "assess_adversarial_risk",
    "assess_bias",
    "audit_adjusted_verdict",
    "coercion_red_flags",
    "comparison_red_flags",
    "consent_red_flags",
    "evidence_red_flags",
    "ideological_capture_findings",
    "language_red_flags",
    "max_severity",
    "render_audit_json",
    "render_audit_text",
    "render_comparison_audit_json",
    "render_comparison_audit_text",
    "severity_rank",
    "temporal_red_flags",
]
