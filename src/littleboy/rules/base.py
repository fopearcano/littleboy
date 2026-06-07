"""Rule primitives: the :class:`Rule` base class and the :class:`RuleContext`.

A rule is a small, named, self-explaining unit of ethical reasoning. It looks at
a :class:`RuleContext` (the case plus everything LittleBoy has already computed
about it) and returns a :class:`~littleboy.core.models.RuleResult` that explains
what it found, which axioms it invoked, and how it affects the verdict.

Rules never mutate state and never reach into global configuration; everything
they need is on the context. That makes them individually testable and the whole
engine auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from littleboy.core.agency import AgencyAssessment, ConsentAssessment
from littleboy.core.enums import RuleResultStatus, RuleSeverity, Verdict
from littleboy.core.models import (
    ActionCase,
    AlternativeAnalysis,
    JustificationResult,
    RuleResult,
)
from littleboy.data.evidence import EvidenceAssessment
from littleboy.rules.policy import PolicyProfile


@dataclass
class RuleContext:
    """Everything a rule needs to evaluate a case, computed once up front.

    Bundling the precomputed assessments here means rules share a single,
    consistent view of the case and never recompute scores.
    """

    case: ActionCase
    policy: PolicyProfile

    coercion_score: float
    coercion_present: bool
    informational_manipulation: float
    irreversible: bool

    epistemic_score: float
    has_epistemic_basis: bool
    data_quality_score: float
    evidence: EvidenceAssessment

    consent: ConsentAssessment
    agency: AgencyAssessment
    justification: JustificationResult
    alternatives: AlternativeAnalysis

    n_unknowns: int
    base_confidence: float


class Rule:
    """Base class for all rules.

    Subclasses set the class attributes and implement :meth:`evaluate`. The
    identifying metadata (id, name, description, axioms) lives on the class so
    the registry can introspect rules without running them.
    """

    rule_id: str = ""
    name: str = ""
    description: str = ""
    axioms_invoked: tuple[str, ...] = ()

    def evaluate(self, ctx: RuleContext) -> RuleResult:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- helpers for building results ----------------------------------------

    def result(
        self,
        *,
        status: RuleResultStatus,
        severity: RuleSeverity,
        message: str,
        evidence_used: list[str] | None = None,
        missing_data: list[str] | None = None,
        confidence_delta: float = 0.0,
        verdict_delta: int = 0,
        verdict_cap: Verdict | None = None,
        trace_notes: list[str] | None = None,
    ) -> RuleResult:
        """Construct a :class:`RuleResult` pre-filled with this rule's identity."""
        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            status=status,
            severity=severity,
            message=message,
            axioms_invoked=list(self.axioms_invoked),
            evidence_used=evidence_used or [],
            missing_data=missing_data or [],
            confidence_delta=confidence_delta,
            verdict_delta=verdict_delta,
            verdict_cap=verdict_cap,
            trace_notes=trace_notes or [],
        )

    def not_applicable(self, message: str = "not applicable to this case") -> RuleResult:
        """A convenience for the common 'this rule does not apply here' result."""
        return self.result(
            status=RuleResultStatus.NOT_APPLICABLE,
            severity=RuleSeverity.INFO,
            message=message,
        )
