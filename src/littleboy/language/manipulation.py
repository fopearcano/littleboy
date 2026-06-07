"""A small, transparent lexicon for detecting linguistic manipulation.

This is deliberately **not** NLP or machine learning. It is a documented,
auditable list of phrases, each mapped to a manipulation category. Detection is
literal, case-insensitive substring matching, and every match is reported with
the exact phrase that triggered it, so a reader can always see *why* an indicator
was raised. The lexicon is intentionally conservative and easy to extend.

It will miss paraphrases and misfire on quotation or discussion of these
phrases; that is an accepted limitation of a non-LLM detector. Explicitly
supplied indicators on a :class:`~littleboy.language.models.LanguageEthicsProfile`
always take precedence and are the primary input.
"""

from __future__ import annotations

from littleboy.language.models import ManipulationFinding

# Category -> phrases that suggest it. Lower-cased, matched as substrings.
_LEXICON: dict[str, tuple[str, ...]] = {
    "false_necessity": (
        "you have no choice",
        "there is no alternative",
        "there is no other option",
        "no other option",
        "no way around",
        "you must",
        "you have to",
        "it is mandatory",
    ),
    "false_dichotomy": (
        "either you",
        "or else",
        "your only options",
        "it's them or us",
        "if you don't",
        "you're either with",
    ),
    "shame_pressure": (
        "you should be ashamed",
        "shame on you",
        "how selfish",
        "you are a burden",
        "you're a burden",
        "pathetic",
        "after all i've done",
        "a real man would",
        "a good person would",
    ),
    "fear_pressure": (
        "you will lose everything",
        "you'll lose everything",
        "act now",
        "last chance",
        "before it's too late",
        "catastrophe",
        "disaster",
        "you'll regret",
        "or you will suffer",
        "terrible things will happen",
    ),
    "loaded_language": (
        "miracle",
        "guaranteed",
        "once-in-a-lifetime",
        "revolutionary",
        "everyone knows",
        "obviously the best",
    ),
    "silencing": (
        "don't argue",
        "end of discussion",
        "you wouldn't understand",
        "be quiet",
        "that's final",
        "stop complaining",
    ),
    "authority_capture": (
        "trust me, i'm",
        "as an expert",
        "you're not qualified",
        "leave it to the professionals",
        "i know better than you",
    ),
    "obfuscation": (
        "notwithstanding",
        "hereinafter",
        "pursuant to the aforementioned",
        "subject to the terms herein",
    ),
    "semantic_compression": (
        "just wants to",
        "just being dramatic",
        "just attention",
        "you're overreacting",
        "doesn't really mean it",
        "it's nothing",
    ),
    "testimonial_injustice": (
        "she's just",
        "he's just",
        "they're just",
        "you always exaggerate",
        "you're being hysterical",
        "no one believes",
    ),
}

# How a detected category maps onto the risk axes of a LanguageEthicsProfile.
CATEGORY_TO_FIELDS: dict[str, tuple[str, ...]] = {
    "false_necessity": ("false_necessity",),
    "false_dichotomy": ("false_dichotomy",),
    "shame_pressure": ("shame_pressure",),
    "fear_pressure": ("fear_pressure",),
    "loaded_language": ("loaded_language", "manipulation_risk"),
    "silencing": ("silencing_effect",),
    "authority_capture": ("silencing_effect", "manipulation_risk"),
    "obfuscation": ("ambiguity_level", "omission_risk"),
    "semantic_compression": ("omission_risk",),
    "testimonial_injustice": ("silencing_effect", "omission_risk"),
}

# Categories that indicate the speaker is replacing the subject's own framing.
FRAMING_REPLACEMENT_CATEGORIES = {"semantic_compression", "testimonial_injustice"}

_BASE_SEVERITY = 0.55
_PER_EXTRA_MATCH = 0.15


def detect_manipulation(text: str) -> list[ManipulationFinding]:
    """Return the manipulation indicators detected in ``text`` (transparent matching)."""
    if not text:
        return []
    lowered = text.lower()
    findings: list[ManipulationFinding] = []
    for category, phrases in _LEXICON.items():
        matched = [p for p in phrases if p in lowered]
        if not matched:
            continue
        severity = min(1.0, _BASE_SEVERITY + _PER_EXTRA_MATCH * (len(matched) - 1))
        findings.append(
            ManipulationFinding(
                indicator=category,
                severity=round(severity, 4),
                evidence="; ".join(f'"{p}"' for p in matched),
                note=f"detected {len(matched)} phrase(s) suggesting {category}",
            )
        )
    return findings
