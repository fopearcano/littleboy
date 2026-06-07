"""Assembly of the auditable :class:`~littleboy.core.models.ReasoningTrace`.

The trace is the record that lets a reader reconstruct *why* a verdict happened:
which rules applied, which were skipped, which failed or were unknown, which
blocked approval, which flagged a contradiction, and how confidence moved.
"""

from __future__ import annotations

from littleboy.core.enums import (
    PolicyMode,
    RuleResultStatus,
    RuleSeverity,
    Verdict,
)
from littleboy.core.models import ReasoningTrace, RuleResult


def build_reasoning_trace(
    *,
    policy_mode: PolicyMode,
    results: list[RuleResult],
    skipped: list[str],
    base_confidence: float,
    final_confidence: float,
    verdict: Verdict,
    missing_data: list[str],
) -> ReasoningTrace:
    """Aggregate rule results into a complete reasoning trace."""
    failed = [r.rule_id for r in results if r.status == RuleResultStatus.FAILED]
    unknown = [r.rule_id for r in results if r.status == RuleResultStatus.UNKNOWN]
    blockers = [
        r.rule_id
        for r in results
        if r.severity == RuleSeverity.BLOCKER
        and r.status in (RuleResultStatus.FAILED, RuleResultStatus.UNKNOWN)
    ]
    contradictions = [
        r.rule_id
        for r in results
        if r.severity == RuleSeverity.CONTRADICTION and r.status == RuleResultStatus.FAILED
    ]
    confidence_adjustments = [
        f"{r.rule_id}: {r.confidence_delta:+.2f} ({r.message})"
        for r in results
        if r.confidence_delta != 0.0
    ]

    return ReasoningTrace(
        policy_mode=policy_mode,
        applied=results,
        skipped=skipped,
        failed=failed,
        unknown=unknown,
        blockers=blockers,
        contradictions=contradictions,
        missing_data=missing_data,
        confidence_adjustments=confidence_adjustments,
        base_confidence=round(base_confidence, 4),
        final_confidence=round(final_confidence, 4),
        final_verdict=verdict,
    )
