"""Scoring of *constructive* language.

Constructive language is language that expands the field of will: it increases
clarity, preserves agency, makes alternatives visible, reduces unnecessary
fear/shame, distinguishes facts from interpretations and certainty from
uncertainty, exposes missing data, allows disagreement, improves consent and
self-expression, prevents premature judgment, and makes the subject *more*
visible rather than less.

``recommended_rewrite`` is built from a small set of deterministic, templated
suggestions keyed to the risk axes that are high. There is no LLM rewriting.
"""

from __future__ import annotations

from littleboy.language.models import (
    ConstructiveLanguageAssessment,
    LanguageContext,
    LanguageEthicsProfile,
)

# Templated, deterministic rewrite suggestions, keyed to high risk axes.
_REWRITE_SUGGESTIONS: list[tuple[str, float, str]] = [
    (
        "false_necessity",
        0.4,
        "State the actual alternatives instead of asserting there is no choice.",
    ),
    (
        "false_dichotomy",
        0.4,
        "Name more than two options where they exist; avoid 'either/or' framing.",
    ),
    (
        "fear_pressure",
        0.4,
        "Replace catastrophe/urgency language with a calm, proportionate description of risk.",
    ),
    (
        "shame_pressure",
        0.4,
        "Remove humiliation/guilt; address the decision, not the person's worth.",
    ),
    ("manipulation_risk", 0.4, "Separate facts from persuasion; let the content stand on its own."),
    ("ambiguity_level", 0.4, "Make the wording specific and concrete; define key terms."),
    ("omission_risk", 0.4, "Disclose the material facts and what is not yet known."),
    ("silencing_effect", 0.4, "Invite questions and disagreement; do not foreclose reply."),
]


def score_constructive_language(
    profile: LanguageEthicsProfile, context: LanguageContext
) -> ConstructiveLanguageAssessment:
    """Assess how constructive (field-expanding) a language act is."""
    clarifying_effect = profile.clarity * (1.0 - profile.ambiguity_level)
    agency_support = profile.agency_respect * (1.0 - profile.silencing_effect)
    consent_support = profile.consent_support * (1.0 - profile.manipulation_risk)
    uncertainty_transparency = profile.truthfulness * (1.0 - profile.omission_risk)
    alternative_visibility = 1.0 - max(profile.false_necessity, profile.false_dichotomy)
    liberating_effect = (agency_support + alternative_visibility + clarifying_effect) / 3.0

    quality = (
        profile.clarity
        + profile.truthfulness
        + profile.specificity
        + profile.context_completeness
        + profile.agency_respect
        + profile.consent_support
        + profile.constructive_potential
    ) / 7.0
    risk = max(
        profile.manipulation_risk,
        profile.shame_pressure,
        profile.fear_pressure,
        profile.false_necessity,
        profile.false_dichotomy,
        profile.silencing_effect,
    )
    constructive_score = max(0.0, min(1.0, quality * (1.0 - risk)))

    warnings: list[str] = []
    if profile.clarity < 0.5 and context.stakes >= 0.5:
        warnings.append("clarity is low in a high-stakes context where clarity is owed")
    if alternative_visibility < 0.5:
        warnings.append("the language hides or forecloses alternatives")
    if agency_support < 0.4:
        warnings.append("the language suppresses the target's agency or reply")

    return ConstructiveLanguageAssessment(
        constructive_score=round(constructive_score, 4),
        liberating_effect=round(max(0.0, min(1.0, liberating_effect)), 4),
        clarifying_effect=round(max(0.0, min(1.0, clarifying_effect)), 4),
        agency_support=round(max(0.0, min(1.0, agency_support)), 4),
        consent_support=round(max(0.0, min(1.0, consent_support)), 4),
        uncertainty_transparency=round(max(0.0, min(1.0, uncertainty_transparency)), 4),
        alternative_visibility=round(max(0.0, min(1.0, alternative_visibility)), 4),
        recommended_rewrite=_build_rewrite(profile),
        warnings=warnings,
    )


def _build_rewrite(profile: LanguageEthicsProfile) -> str:
    """Compose deterministic rewrite suggestions for the high-risk axes."""
    suggestions = [
        text
        for axis, threshold, text in _REWRITE_SUGGESTIONS
        if getattr(profile, axis) >= threshold
    ]
    if not suggestions:
        return "No rewrite needed: the language is largely constructive."
    return "Suggested revisions: " + " ".join(f"({i + 1}) {s}" for i, s in enumerate(suggestions))
