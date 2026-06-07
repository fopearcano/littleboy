"""The rule engine: runs the rules and synthesizes a verdict from their results.

The synthesis is the policy layer made concrete. It is deterministic and fully
documented: a base verdict is derived from coercion level and epistemic basis,
then rule-emitted **blockers** (verdict caps), **downgrades** (notches), and
**contradictions** pull it toward less permissible, and confidence is the base
confidence plus every rule's confidence delta. Under the STANDARD policy this
reproduces the v0.2 decision behaviour; other policies change the thresholds and
toggles the rules read, not the axioms.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from littleboy.core.enums import RuleSeverity, Verdict
from littleboy.core.models import ReasoningTrace, RuleResult
from littleboy.rules.base import RuleContext
from littleboy.rules.builtin_rules import default_registry
from littleboy.rules.policy import PolicyProfile
from littleboy.rules.registry import RuleRegistry
from littleboy.rules.trace import build_reasoning_trace

# Verdicts ordered most -> least permissible. INSUFFICIENT_DATA is handled apart
# (it is an absorbing refusal to judge, not a point on the permissibility line).
_VERDICT_ORDER = (
    Verdict.ACCEPTABLE,
    Verdict.ACCEPTABLE_WITH_RESERVATIONS,
    Verdict.ETHICALLY_SUSPICIOUS,
    Verdict.NOT_ACCEPTABLE,
)


def _least_permissive(a: Verdict, b: Verdict) -> Verdict:
    return _VERDICT_ORDER[max(_VERDICT_ORDER.index(a), _VERDICT_ORDER.index(b))]


def _downgrade(verdict: Verdict, steps: int) -> Verdict:
    idx = _VERDICT_ORDER.index(verdict)
    return _VERDICT_ORDER[min(idx + max(0, steps), len(_VERDICT_ORDER) - 1)]


@dataclass
class RuleEngineOutcome:
    """Everything the evaluator needs from a rule-engine run."""

    verdict: Verdict
    base_confidence: float
    final_confidence: float
    rule_results: list[RuleResult]
    skipped: list[str]
    primary_reasons: list[str] = field(default_factory=list)
    trace: ReasoningTrace | None = None


class RuleEngine:
    """Runs a rule registry over a context and synthesizes the verdict + trace."""

    def __init__(self, policy: PolicyProfile, registry: RuleRegistry | None = None) -> None:
        self.policy = policy
        self.registry = registry or default_registry()

    def evaluate(self, ctx: RuleContext, *, missing_data: list[str]) -> RuleEngineOutcome:
        results, skipped = self.registry.evaluate_all(ctx)

        final_confidence = ctx.base_confidence + sum(r.confidence_delta for r in results)
        final_confidence = max(0.0, min(1.0, final_confidence))

        verdict, reasons = self._synthesize(ctx, results, final_confidence)

        trace = build_reasoning_trace(
            policy_mode=self.policy.mode,
            results=results,
            skipped=skipped,
            base_confidence=ctx.base_confidence,
            final_confidence=final_confidence,
            verdict=verdict,
            missing_data=missing_data,
        )
        return RuleEngineOutcome(
            verdict=verdict,
            base_confidence=ctx.base_confidence,
            final_confidence=final_confidence,
            rule_results=results,
            skipped=skipped,
            primary_reasons=reasons,
            trace=trace,
        )

    # -- synthesis ------------------------------------------------------------

    def _base_verdict(self, ctx: RuleContext) -> Verdict:
        """The most permissive verdict the bare scores allow, before rules bite."""
        if (
            ctx.coercion_score < self.policy.coercion_moderate
            and ctx.epistemic_score >= self.policy.data_quality_good
            and ctx.n_unknowns == 0
        ):
            return Verdict.ACCEPTABLE
        return Verdict.ACCEPTABLE_WITH_RESERVATIONS

    def _synthesize(
        self, ctx: RuleContext, results: list[RuleResult], final_confidence: float
    ) -> tuple[Verdict, list[str]]:
        caps = [r.verdict_cap for r in results if r.verdict_cap is not None]
        reasons: list[str] = []

        # 1. An explicit INSUFFICIENT_DATA cap is absorbing: a blocker rule has
        #    determined the central question cannot be assessed (Axiom 5).
        if Verdict.INSUFFICIENT_DATA in caps:
            reasons.append(
                "Data are insufficient for a confident judgment; per Axiom 5 LittleBoy "
                "declines to feign certainty."
            )
            reasons.extend(
                f"[{r.rule_id}] {r.message}"
                for r in results
                if r.verdict_cap == Verdict.INSUFFICIENT_DATA
            )
            return Verdict.INSUFFICIENT_DATA, reasons

        # 2. Start from the base verdict, apply caps (least permissive wins) and
        #    downgrade notches.
        base = self._base_verdict(ctx)
        verdict = base
        for cap in caps:
            if cap in _VERDICT_ORDER:
                verdict = _least_permissive(verdict, cap)
        total_delta = sum(r.verdict_delta for r in results)
        verdict = _downgrade(verdict, total_delta)

        # 3. Confidence below the policy minimum means we decline to judge --
        #    EXCEPT for a definite rejection: we do not need high confidence to
        #    reject, only to approve. So a NOT_ACCEPTABLE verdict stands.
        if final_confidence < self.policy.min_confidence and verdict != Verdict.NOT_ACCEPTABLE:
            reasons.append(
                "Data are insufficient for a confident judgment; per Axiom 5 LittleBoy "
                "declines to feign certainty."
            )
            reasons.append(
                f"Confidence {final_confidence:.2f} is below the policy minimum "
                f"{self.policy.min_confidence:.2f}."
            )
            return Verdict.INSUFFICIENT_DATA, reasons

        # 4. Reasons: the rules that actually moved the verdict.
        decisive = [
            r
            for r in results
            if (r.verdict_cap in _VERDICT_ORDER)
            or r.verdict_delta > 0
            or r.severity == RuleSeverity.CONTRADICTION
        ]
        reasons.append(
            f"Base verdict {base.value} (coercion {ctx.coercion_score:.2f}, "
            f"epistemic basis {ctx.epistemic_score:.2f}, {ctx.n_unknowns} unknown(s))."
        )
        reasons.extend(f"[{r.rule_id}] {r.message}" for r in decisive)
        if not decisive:
            reasons.append(f"No blocking or downgrading rule fired; verdict is {verdict.value}.")
        return verdict, reasons
