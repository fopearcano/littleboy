"""Policy profiles for LittleBoy's rule engine.

A :class:`PolicyProfile` is a bundle of *operational parameters* — thresholds and
toggles — that control how strict the rule engine is. Policies change how the
axioms are applied to uncertain, real-world data; they never change the axioms
themselves.

These numbers are deliberate, documented defaults, **not** claims of absolute
moral truth. They exist so that the same case can be examined under different
risk postures (e.g. a permissive research setting vs. a precautionary one).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import PolicyMode


class PolicyProfile(BaseModel):
    """Operational thresholds and toggles for one strictness posture."""

    model_config = ConfigDict(extra="forbid")

    mode: PolicyMode

    # Epistemic gates.
    min_data_quality_for_approval: float = Field(ge=0.0, le=1.0)
    min_evidence_quality_for_approval: float = Field(ge=0.0, le=1.0)
    min_confidence: float = Field(ge=0.0, le=1.0)
    data_quality_good: float = Field(
        ge=0.0, le=1.0, description="At/above this, the epistemic basis is treated as good."
    )

    # Coercion thresholds.
    max_coercion_for_acceptable: float = Field(
        ge=0.0, le=1.0, description="Above this, coercion is unacceptable unless justified."
    )
    coercion_moderate: float = Field(
        ge=0.0, le=1.0, description="Above this, coercion is non-trivial and needs scrutiny."
    )

    # Irreversibility.
    irreversible_requires_high_certainty: bool = True
    irreversible_min_epistemic: float = Field(
        ge=0.0, le=1.0, description="Min epistemic basis for an irreversible action."
    )

    # Consent / vulnerability / alternatives / manipulation.
    unknown_consent_is_blocker: bool = False
    vulnerability_confidence_penalty: float = Field(ge=0.0, le=1.0)
    alternative_downgrade_steps: int = Field(ge=0, le=3)
    informational_manipulation_severe: bool = True


# The four built-in profiles. STANDARD reproduces the v0.2 evaluator behaviour.
_PERMISSIVE = PolicyProfile(
    mode=PolicyMode.PERMISSIVE,
    min_data_quality_for_approval=0.25,
    min_evidence_quality_for_approval=0.20,
    min_confidence=0.20,
    data_quality_good=0.60,
    max_coercion_for_acceptable=0.75,
    coercion_moderate=0.40,
    irreversible_requires_high_certainty=False,
    irreversible_min_epistemic=0.40,
    unknown_consent_is_blocker=False,
    vulnerability_confidence_penalty=0.10,
    alternative_downgrade_steps=1,
    informational_manipulation_severe=False,
)

_STANDARD = PolicyProfile(
    mode=PolicyMode.STANDARD,
    min_data_quality_for_approval=0.35,
    min_evidence_quality_for_approval=0.30,
    min_confidence=0.30,
    data_quality_good=0.70,
    max_coercion_for_acceptable=0.60,
    coercion_moderate=0.30,
    irreversible_requires_high_certainty=True,
    irreversible_min_epistemic=0.50,
    unknown_consent_is_blocker=False,
    vulnerability_confidence_penalty=0.15,
    alternative_downgrade_steps=1,
    informational_manipulation_severe=True,
)

_STRICT = PolicyProfile(
    mode=PolicyMode.STRICT,
    min_data_quality_for_approval=0.50,
    min_evidence_quality_for_approval=0.45,
    min_confidence=0.45,
    data_quality_good=0.80,
    max_coercion_for_acceptable=0.45,
    coercion_moderate=0.20,
    irreversible_requires_high_certainty=True,
    irreversible_min_epistemic=0.65,
    unknown_consent_is_blocker=True,
    vulnerability_confidence_penalty=0.25,
    alternative_downgrade_steps=2,
    informational_manipulation_severe=True,
)

_PRECAUTIONARY = PolicyProfile(
    mode=PolicyMode.PRECAUTIONARY,
    min_data_quality_for_approval=0.60,
    min_evidence_quality_for_approval=0.55,
    min_confidence=0.55,
    data_quality_good=0.85,
    max_coercion_for_acceptable=0.35,
    coercion_moderate=0.15,
    irreversible_requires_high_certainty=True,
    irreversible_min_epistemic=0.75,
    unknown_consent_is_blocker=True,
    vulnerability_confidence_penalty=0.30,
    alternative_downgrade_steps=2,
    informational_manipulation_severe=True,
)

DEFAULT_PROFILES: dict[PolicyMode, PolicyProfile] = {
    PolicyMode.PERMISSIVE: _PERMISSIVE,
    PolicyMode.STANDARD: _STANDARD,
    PolicyMode.STRICT: _STRICT,
    PolicyMode.PRECAUTIONARY: _PRECAUTIONARY,
}

DEFAULT_POLICY_MODE = PolicyMode.STANDARD


def get_policy(policy: PolicyMode | PolicyProfile | str | None) -> PolicyProfile:
    """Resolve a policy mode (or an explicit profile, or ``None``) to a profile."""
    if policy is None:
        return DEFAULT_PROFILES[DEFAULT_POLICY_MODE]
    if isinstance(policy, PolicyProfile):
        return policy
    mode = PolicyMode(policy) if isinstance(policy, str) else policy
    return DEFAULT_PROFILES[mode]
