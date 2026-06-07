"""Deterministic scoring for the language & coercion module.

All functions here are transparent heuristics over explicit indicators. No NLP
model is used: supplied :class:`LanguageEthicsProfile` indicators are merged with
the literal phrase detections from :mod:`littleboy.language.manipulation`, and
the linguistic-coercion score is a documented combination of those indicators
amplified by the :class:`LanguageContext`.
"""

from __future__ import annotations

from littleboy.language.manipulation import (
    CATEGORY_TO_FIELDS,
    detect_manipulation,
)
from littleboy.language.models import (
    LanguageAct,
    LanguageContext,
    LanguageEthicsProfile,
    ManipulationFinding,
)

# The nine risk axes that constitute "linguistic coercion means".
_RISK_AXES = (
    "manipulation_risk",
    "shame_pressure",
    "fear_pressure",
    "false_necessity",
    "false_dichotomy",
    "loaded_language",
    "omission_risk",
    "ambiguity_level",
    "silencing_effect",
)


def _soft_or(values: list[float]) -> float:
    """Probabilistic OR: ``1 - prod(1 - v)``. Order-independent, bounded in [0, 1]."""
    product_complement = 1.0
    for v in values:
        product_complement *= 1.0 - v
    return 1.0 - product_complement


def apply_findings(
    profile: LanguageEthicsProfile, findings: list[ManipulationFinding]
) -> LanguageEthicsProfile:
    """Return a copy of ``profile`` raised to reflect detected manipulation findings.

    Detections can only *raise* a risk axis (``max``), never lower it, and never
    touch the quality axes. Explicitly-supplied indicators thus dominate unless a
    detection is stronger.
    """
    updates: dict[str, float] = {}
    for finding in findings:
        for field in CATEGORY_TO_FIELDS.get(finding.indicator, ()):
            updates[field] = max(updates.get(field, 0.0), finding.severity, getattr(profile, field))
    return profile.model_copy(update=updates) if updates else profile


def score_language_ethics(language_act: LanguageAct) -> LanguageEthicsProfile:
    """Build the language ethics profile: supplied indicators merged with detections."""
    base = language_act.ethics_profile or LanguageEthicsProfile()
    findings = detect_manipulation(language_act.text)
    return apply_findings(base, findings)


def score_linguistic_coercion(profile: LanguageEthicsProfile, context: LanguageContext) -> float:
    """Compute a 0..1 linguistic-coercion score from a profile and its context.

    In words:

    * ``means`` = soft-OR of the risk axes plus deception (``1 - truthfulness``)
      and loss of agency (``1 - agency_respect``) -- how coercive the language is;
    * ``amplifier`` = ``1 + mean(power_asymmetry, target_vulnerability, urgency,
      stakes)`` -- context makes the same words more coercive;
    * ``mitigation`` from agency respect and consent support pulls it back down.

    The result is clamped to ``[0, 1]``. It is a heuristic, not a measurement.
    """
    means = _soft_or(
        [getattr(profile, axis) for axis in _RISK_AXES]
        + [1.0 - profile.truthfulness, 1.0 - profile.agency_respect]
    )
    amp = (
        context.power_asymmetry + context.target_vulnerability + context.urgency + context.stakes
    ) / 4.0
    mitigation = (profile.agency_respect + profile.consent_support) / 2.0
    score = means * (1.0 + amp) * (1.0 - 0.4 * mitigation)
    return max(0.0, min(1.0, score))


def dominant_indicators(profile: LanguageEthicsProfile, *, threshold: float = 0.4) -> list[str]:
    """Return the risk axes that are materially present, strongest first."""
    present = [(axis, getattr(profile, axis)) for axis in _RISK_AXES]
    present = [(axis, value) for axis, value in present if value >= threshold]
    present.sort(key=lambda pair: pair[1], reverse=True)
    return [axis for axis, _ in present]
