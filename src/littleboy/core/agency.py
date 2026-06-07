"""Consent and agency assessment for LittleBoy.

These functions translate the structured :class:`ConsentProfile` and
:class:`AgencyProfile` (or their v0.1 fallbacks) into assessments the evaluator
can act on. They never decide the verdict; they surface validity, unknowns,
vulnerability, and warnings, with reasons attached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from littleboy.core.enums import AgentType, ConsentStatus
from littleboy.core.models import ActionCase

# At or above this vulnerability level the subject warrants heightened scrutiny.
HIGH_VULNERABILITY_THRESHOLD = 0.6

_CONSENT_DIMENSIONS = ("informed", "voluntary", "specific", "revocable")


@dataclass
class ConsentAssessment:
    """What we can say about consent, and what it implies."""

    effective_status: ConsentStatus
    valid: bool | None  # True = valid; False = invalid; None = unknown/contested
    is_unknown: bool
    blocks_confident_approval: bool
    n_unknown_dimensions: int
    summary: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class AgencyAssessment:
    """What we can say about the subject's agency and vulnerability."""

    agent_type: AgentType | None
    type_is_known: bool
    can_bear_duties: bool
    capacity_confidence: float
    vulnerability_level: float
    high_vulnerability: bool
    n_unknowns: int
    summary: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def assess_consent(case: ActionCase) -> ConsentAssessment:
    """Assess the consent in force for a case (profile takes precedence)."""
    status = case.effective_consent_status()
    profile = case.consent_profile
    reasons: list[str] = []
    warnings: list[str] = []

    # Count unresolved consent dimensions, if a structured profile is present.
    n_unknown_dimensions = 0
    if profile is not None:
        for dim in _CONSENT_DIMENSIONS:
            if getattr(profile, dim).is_unresolved:
                n_unknown_dimensions += 1

    valid: bool | None
    is_unknown = False
    blocks = False

    if status == ConsentStatus.GIVEN:
        valid = True
        reasons.append("consent was given")
        if profile is not None:
            weak = [d for d in _CONSENT_DIMENSIONS if not getattr(profile, d).is_affirmative]
            if weak:
                valid = None
                warnings.append("consent is given but not fully established on: " + ", ".join(weak))
    elif status == ConsentStatus.NOT_APPLICABLE:
        valid = True
        reasons.append("consent is not applicable to this action")
    elif status == ConsentStatus.REFUSED:
        valid = False
        blocks = True
        reasons.append("consent was refused; acting against refusal is presumptively coercive")
    elif status == ConsentStatus.COERCED:
        valid = False
        blocks = True
        warnings.append("consent was coerced; coerced consent is not valid consent")
        reasons.append("consent was coerced and does not count as consent")
    elif status == ConsentStatus.DISPUTED:
        valid = None
        blocks = True
        warnings.append("consent is disputed; confident approval is blocked")
        reasons.append("consent is contested")
    else:  # UNKNOWN
        valid = None
        is_unknown = True
        reasons.append("consent status is unknown")

    dims = ""
    if profile is not None:
        dims = (
            " (" + ", ".join(f"{d}={getattr(profile, d).value}" for d in _CONSENT_DIMENSIONS) + ")"
        )
    summary = f"{status.value}{dims}"

    return ConsentAssessment(
        effective_status=status,
        valid=valid,
        is_unknown=is_unknown,
        blocks_confident_approval=blocks,
        n_unknown_dimensions=n_unknown_dimensions,
        summary=summary,
        reasons=reasons,
        warnings=warnings,
    )


def assess_agency(case: ActionCase) -> AgencyAssessment:
    """Assess the subject's agency type, capacity, and vulnerability."""
    profile = case.agency_profile
    agent_type = case.effective_agent_type()
    type_is_known = agent_type is not None
    can_bear_duties = agent_type == AgentType.TYPE_II

    reasons: list[str] = []
    warnings: list[str] = []
    n_unknowns = 0

    if not type_is_known:
        n_unknowns += 1
        warnings.append("agent type is unknown; duty-bearing status (Axiom 4) is undetermined")
    elif can_bear_duties:
        reasons.append("subject is Type II and can bear moral duties (A4)")
    else:
        reasons.append("subject is Type I and cannot bear moral duties (A4)")
        warnings.append("agent is Type I: duties do not bind it (Axiom 4)")

    capacity_confidence = (
        profile.capacity_confidence if profile is not None else (0.7 if type_is_known else 0.0)
    )
    vulnerability = profile.vulnerability_level if profile is not None else 0.0
    high_vulnerability = vulnerability >= HIGH_VULNERABILITY_THRESHOLD

    if profile is not None:
        if profile.decision_capacity.is_unresolved:
            n_unknowns += 1
        if profile.language_symbolic_capacity.is_unresolved:
            n_unknowns += 1
        if high_vulnerability:
            warnings.append(
                f"subject vulnerability is high ({vulnerability:.2f}); "
                "consent and coercion require heightened scrutiny"
            )
            reasons.append("high subject vulnerability raises the bar for valid consent")

    type_label = agent_type.value if agent_type is not None else "UNKNOWN"
    summary = (
        f"{type_label} (capacity_confidence={capacity_confidence:.2f}, "
        f"vulnerability={vulnerability:.2f})"
    )

    return AgencyAssessment(
        agent_type=agent_type,
        type_is_known=type_is_known,
        can_bear_duties=can_bear_duties,
        capacity_confidence=capacity_confidence,
        vulnerability_level=vulnerability,
        high_vulnerability=high_vulnerability,
        n_unknowns=n_unknowns,
        summary=summary,
        reasons=reasons,
        warnings=warnings,
    )
