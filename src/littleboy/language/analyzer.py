"""The language analyzer: orchestration and the bridge to the coercion model.

``analyze_language`` turns a :class:`LanguageAct` into a full, auditable
:class:`LanguageAnalysis`. ``language_to_coercion_profile`` and
``merge_coercion_profiles`` are the bridge that lets linguistic coercion
contribute to the main :class:`~littleboy.core.models.CoercionProfile`, so the
rest of the engine treats manipulative language as the coercion it is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.core.enums import LanguageMedium
from littleboy.language.constructive import score_constructive_language
from littleboy.language.manipulation import (
    FRAMING_REPLACEMENT_CATEGORIES,
    detect_manipulation,
)
from littleboy.language.models import (
    LanguageAct,
    LanguageAnalysis,
    LanguageContext,
    LanguageEthicsProfile,
)
from littleboy.language.scoring import (
    apply_findings,
    dominant_indicators,
    score_linguistic_coercion,
)

if TYPE_CHECKING:  # avoids a core.models <-> language import cycle at module load
    from littleboy.core.models import CoercionProfile

# Media where consent/clarity carry a heightened ethical duty.
_CONSENT_MEDIA = {
    LanguageMedium.MEDICAL_CONSENT,
    LanguageMedium.LEGAL_NOTICE,
    LanguageMedium.CONTRACT,
}
_CLARITY_REQUIRED_MEDIA = _CONSENT_MEDIA | {LanguageMedium.EDUCATIONAL}


def analyze_language(language_act: LanguageAct) -> LanguageAnalysis:
    """Analyse a language act, returning the full transparent result."""
    context = language_act.context or LanguageContext()
    findings = detect_manipulation(language_act.text)
    profile = apply_findings(language_act.ethics_profile or LanguageEthicsProfile(), findings)

    coercion = score_linguistic_coercion(profile, context)
    constructive = score_constructive_language(profile, context)
    dominant = dominant_indicators(profile)

    replaces_framing = (
        any(f.indicator in FRAMING_REPLACEMENT_CATEGORIES for f in findings)
        or profile.silencing_effect >= 0.6
        or (profile.omission_risk >= 0.6 and profile.context_completeness < 0.4)
    )
    affects_consent = (
        context.medium in _CONSENT_MEDIA
        or profile.consent_support < 0.4
        or profile.manipulation_risk >= 0.5
    )

    warnings = _build_warnings(profile, context, coercion, replaces_framing, affects_consent)
    missing_data = _build_missing_data(language_act, findings)
    questions = _build_questions(language_act, context, affects_consent)

    reasoning = [
        "language scores are heuristic indicators, not absolute moral truths",
        f"linguistic_coercion = {coercion:.2f} "
        f"(context amplifier from power/vulnerability/urgency/stakes)",
        f"constructive_score = {constructive.constructive_score:.2f}",
    ]
    if findings:
        reasoning.append(
            "detected manipulation indicators: "
            + "; ".join(f"{f.indicator} ({f.evidence})" for f in findings)
        )

    return LanguageAnalysis(
        linguistic_coercion_score=round(coercion, 4),
        profile=profile,
        context=context,
        constructive=constructive,
        manipulation_findings=findings,
        dominant_indicators=dominant,
        affects_consent=affects_consent,
        replaces_subject_framing=replaces_framing,
        warnings=warnings,
        missing_data=missing_data,
        recommended_questions=questions,
        reasoning=reasoning,
    )


def _build_warnings(profile, context, coercion, replaces_framing, affects_consent) -> list[str]:
    warnings: list[str] = []
    if profile.fear_pressure >= 0.5 and context.target_vulnerability >= 0.5:
        warnings.append(
            "fear pressure on a vulnerable target sharply increases linguistic coercion"
        )
    if profile.manipulation_risk >= 0.5 and context.power_asymmetry >= 0.5:
        warnings.append("manipulation under a power asymmetry is a severe linguistic-coercion risk")
    if profile.false_necessity >= 0.5:
        warnings.append(
            "language asserts a false necessity ('no choice') -- alternatives may exist"
        )
    if profile.false_dichotomy >= 0.5:
        warnings.append("language frames a false dichotomy -- more than two options may exist")
    if profile.clarity < 0.5 and context.stakes >= 0.5:
        warnings.append("low clarity in a high-stakes context where clarity is ethically owed")
    if profile.ambiguity_level >= 0.5 and context.medium in _CLARITY_REQUIRED_MEDIA:
        warnings.append(
            "high ambiguity in a context (consent/legal/educational) that requires clarity"
        )
    if replaces_framing:
        warnings.append(
            "language may replace the subject's own framing of their will "
            "(semantic compression / testimonial injustice); examine the fuller meaning-field"
        )
    if affects_consent and coercion >= 0.3:
        warnings.append("this language may reduce the quality of any consent it seeks")
    return warnings


def _build_missing_data(language_act: LanguageAct, findings: list) -> list[str]:
    missing: list[str] = []
    if language_act.ethics_profile is None and not findings:
        missing.append(
            "language ethics indicators not provided and none detected from the text; "
            "supply a LanguageEthicsProfile or the actual wording"
        )
    if language_act.context is None:
        missing.append(
            "language context (medium, power asymmetry, stakes, vulnerability) is unknown"
        )
    if language_act.evidence is None:
        missing.append("no evidence for what was actually said")
    return missing


def _build_questions(language_act, context: LanguageContext, affects_consent: bool) -> list[str]:
    questions: list[str] = []
    if context.medium == LanguageMedium.UNKNOWN:
        questions.append(
            "In what medium and setting was this said (speech, contract, advert, ...)?"
        )
    if not language_act.text and language_act.ethics_profile is None:
        questions.append("What were the actual words used?")
    questions.append("Did the language mislead, pressure, shame, silence, or rush the target?")
    if affects_consent:
        questions.append("Did this language affect the target's consent or decision?")
    questions.append("Could the target reply, disagree, or ask questions?")
    return questions


# --- bridge to the main coercion model --------------------------------------


def language_to_coercion_profile(analysis: LanguageAnalysis) -> CoercionProfile:
    """Express a language analysis as a coercion profile contribution.

    Deception/omission map to ``informational_manipulation``; emotional pressure
    and silencing map to ``psychological_pressure``; the overall linguistic
    coercion becomes the ``severity``; reversibility comes from the context.
    """
    from littleboy.core.models import CoercionProfile

    p = analysis.profile
    return CoercionProfile(
        informational_manipulation=max(
            p.manipulation_risk, p.omission_risk, p.loaded_language, 1.0 - p.truthfulness
        ),
        psychological_pressure=max(p.shame_pressure, p.fear_pressure, p.silencing_effect),
        severity=analysis.linguistic_coercion_score,
        reversibility=analysis.context.reversibility,
    )


def merge_coercion_profiles(
    base: CoercionProfile | None, language: CoercionProfile | None
) -> CoercionProfile | None:
    """Merge a base coercion profile with a language-derived one (language can only raise)."""
    from littleboy.core.models import CoercionProfile

    if base is None:
        return language
    if language is None:
        return base

    channels = (
        "physical_force",
        "threat",
        "economic_pressure",
        "psychological_pressure",
        "informational_manipulation",
        "legal_constraint",
        "social_pressure",
    )
    merged: dict[str, float] = {
        ch: max(getattr(base, ch), getattr(language, ch)) for ch in channels
    }
    merged["duration"] = max(base.duration, language.duration)
    merged["severity"] = max(base.severity, language.severity)
    merged["scope_number_of_agents"] = max(
        base.scope_number_of_agents, language.scope_number_of_agents
    )

    if base.reversibility is None:
        merged["reversibility"] = language.reversibility
    elif language.reversibility is None:
        merged["reversibility"] = base.reversibility
    else:
        merged["reversibility"] = min(base.reversibility, language.reversibility)

    return CoercionProfile(**merged)
