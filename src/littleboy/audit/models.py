"""Typed models for the LittleBoy adversarial audit & bias-testing module.

Core thesis: **a rational ethical engine must not merely evaluate actions; it
must also evaluate the conditions under which the action is being described.**
LittleBoy must judge not only the action, but also the description through which
the action becomes visible.

These are pure data structures. They depend only on :mod:`littleboy.core.enums`
(and pydantic), so ``core.models`` can embed an :class:`AuditReport` in an
:class:`~littleboy.core.models.EvaluationReport` without an import cycle. The
audit *logic* lives in :mod:`littleboy.audit.red_flags`,
:mod:`littleboy.audit.bias`, :mod:`littleboy.audit.adversarial`, and
:mod:`littleboy.audit.stress`.

Every number here is an **audit indicator in ``[0, 1]``, not a proof**. The audit
does not claim to detect bias or manipulation perfectly; it exposes *risk* so a
reader can decide what to re-examine.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, computed_field


class AuditSeverity(StrEnum):
    """How serious an audit finding is for the trustworthiness of a judgment."""

    INFO = "info"
    WARNING = "warning"
    SERIOUS = "serious"
    CRITICAL = "critical"


_SEVERITY_RANK: dict[AuditSeverity, int] = {
    AuditSeverity.INFO: 0,
    AuditSeverity.WARNING: 1,
    AuditSeverity.SERIOUS: 2,
    AuditSeverity.CRITICAL: 3,
}


def severity_rank(severity: AuditSeverity) -> int:
    """Return a 0..3 ordinal for a severity (higher = more serious)."""
    return _SEVERITY_RANK[severity]


def max_severity(severities: list[AuditSeverity]) -> AuditSeverity:
    """Return the most serious severity in the list (INFO if empty)."""
    if not severities:
        return AuditSeverity.INFO
    return max(severities, key=severity_rank)


class AuditCategory(StrEnum):
    """The aspect of a case/description an audit finding concerns."""

    CONSENT = "consent"
    COERCION = "coercion"
    EVIDENCE = "evidence"
    LANGUAGE = "language"
    TEMPORAL = "temporal"
    COMPARISON = "comparison"
    IDEOLOGICAL_CAPTURE = "ideological_capture"
    BIAS = "bias"
    OVERCONFIDENCE = "overconfidence"
    FRAMING = "framing"
    VULNERABILITY = "vulnerability"
    ALTERNATIVES = "alternatives"


class _AuditBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuditFinding(_AuditBase):
    """One audited risk in the way a case is described or judged.

    A finding is a *flag for scrutiny*, never a verdict. It names what was seen,
    which fields it concerns, why it matters ethically, and what to ask next.
    """

    finding_id: str
    title: str
    description: str
    severity: AuditSeverity = AuditSeverity.WARNING
    category: AuditCategory
    evidence: list[str] = Field(default_factory=list)
    affected_fields: list[str] = Field(default_factory=list)
    why_it_matters: str = ""
    recommended_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How confident the audit is this risk is real (an indicator, not proof).",
    )


class AdversarialRiskProfile(_AuditBase):
    """How susceptible a case is to having been *described* so as to lead a verdict.

    Each axis is a 0..1 indicator. Higher means the description shows more of the
    pattern; it does **not** prove manipulation.
    """

    leading_language_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_counterevidence_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    one_sided_description_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    false_necessity_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    false_dichotomy_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    fake_alternative_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    hidden_power_asymmetry_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    hidden_vulnerability_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    consent_contamination_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    ideological_capture_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    overconfidence_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    data_laundering_risk: float = Field(default=0.0, ge=0.0, le=1.0)

    RISK_FIELDS: ClassVar[tuple[str, ...]] = (
        "leading_language_risk",
        "missing_counterevidence_risk",
        "one_sided_description_risk",
        "false_necessity_risk",
        "false_dichotomy_risk",
        "fake_alternative_risk",
        "hidden_power_asymmetry_risk",
        "hidden_vulnerability_risk",
        "consent_contamination_risk",
        "ideological_capture_risk",
        "overconfidence_risk",
        "data_laundering_risk",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_risk(self) -> float:
        return round(max(getattr(self, f) for f in self.RISK_FIELDS), 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dominant_risks(self) -> list[str]:
        ranked = sorted(self.RISK_FIELDS, key=lambda f: getattr(self, f), reverse=True)
        return [f for f in ranked if getattr(self, f) >= 0.5]


class BiasProfile(_AuditBase):
    """Indicators that the *framing* of a case may bias the judgment.

    These are heuristic indicators, not measurements, and the audit explicitly
    does not claim to detect bias perfectly.
    """

    agent_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    status_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    authority_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    outcome_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    survivorship_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    availability_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    framing_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    language_beauty_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    sympathy_bias_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    dehumanization_risk: float = Field(default=0.0, ge=0.0, le=1.0)

    RISK_FIELDS: ClassVar[tuple[str, ...]] = (
        "agent_bias_risk",
        "status_bias_risk",
        "authority_bias_risk",
        "outcome_bias_risk",
        "survivorship_bias_risk",
        "availability_bias_risk",
        "framing_bias_risk",
        "language_beauty_bias_risk",
        "sympathy_bias_risk",
        "dehumanization_risk",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_risk(self) -> float:
        return round(max(getattr(self, f) for f in self.RISK_FIELDS), 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dominant_risks(self) -> list[str]:
        ranked = sorted(self.RISK_FIELDS, key=lambda f: getattr(self, f), reverse=True)
        return [f for f in ranked if getattr(self, f) >= 0.5]


class StressTestResult(_AuditBase):
    """One adversarial 'what if' applied to a case.

    The audit does not assert the adversarial assumption is true; it asks whether
    the judgment would survive if it were, and flags the data that would settle it.
    """

    question: str
    assumption: str
    affected_fields: list[str] = Field(default_factory=list)
    plausibility: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How plausible the adversarial assumption is, given the description.",
    )
    could_change_judgment: bool = Field(
        default=False,
        description="True if the verdict could plausibly flip were the assumption true.",
    )
    severity: AuditSeverity = AuditSeverity.WARNING
    note: str = ""


class AuditReport(_AuditBase):
    """The full, auditable result of stress-testing one case or evaluation.

    Carries the findings (red flags), the adversarial-risk and bias indicator
    profiles, the adversarial stress tests, and whether the judgment should be
    treated as stable. Nothing here overrides the core verdict on its own; the
    evaluator decides (only when audit is enabled) how a critical finding bears on
    the verdict, and records that transparently.
    """

    target: str = Field(default="case", description="What was audited: 'case', 'evaluation', ...")
    findings: list[AuditFinding] = Field(default_factory=list)
    adversarial_risk_profile: AdversarialRiskProfile = Field(default_factory=AdversarialRiskProfile)
    bias_profile: BiasProfile = Field(default_factory=BiasProfile)
    stress_tests: list[StressTestResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    judgment_stable: bool = True
    requires_explicit_review: bool = False
    reasoning: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def red_flags(self) -> list[str]:
        """Titles of the findings serious enough to call red flags."""
        return [
            f.title
            for f in self.findings
            if severity_rank(f.severity) >= severity_rank(AuditSeverity.SERIOUS)
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def critical_findings(self) -> list[str]:
        return [f.title for f in self.findings if f.severity == AuditSeverity.CRITICAL]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stress_test_questions(self) -> list[str]:
        return [s.question for s in self.stress_tests]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recommended_questions(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for f in self.findings:
            for q in f.recommended_questions:
                if q not in seen:
                    seen.add(q)
                    out.append(q)
        return out

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_severity(self) -> AuditSeverity:
        return max_severity([f.severity for f in self.findings])

    @property
    def has_critical(self) -> bool:
        return any(f.severity == AuditSeverity.CRITICAL for f in self.findings)


class ComparisonAuditReport(_AuditBase):
    """The audit of a whole comparison: per-option audits plus cross-option risks."""

    option_audits: dict[str, AuditReport] = Field(default_factory=dict)
    findings: list[AuditFinding] = Field(default_factory=list)
    ranking_unstable_due_to_missing_data: bool = False
    warnings: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def red_flags(self) -> list[str]:
        return [
            f.title
            for f in self.findings
            if severity_rank(f.severity) >= severity_rank(AuditSeverity.SERIOUS)
        ]

    @property
    def has_critical(self) -> bool:
        return any(f.severity == AuditSeverity.CRITICAL for f in self.findings)
