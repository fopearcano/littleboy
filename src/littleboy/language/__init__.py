"""LittleBoy's language & coercion module (v0.5).

Language is ethically decisive because it can either **expand or restrict the
field in which will, consent, and self-understanding become possible**. This
module detects and scores linguistic/informational coercion -- and the
constructive language that does the opposite -- deterministically and
transparently (no NLP/LLM).
"""

from __future__ import annotations

from littleboy.language.analyzer import (
    analyze_language,
    language_to_coercion_profile,
    merge_coercion_profiles,
)
from littleboy.language.constructive import score_constructive_language
from littleboy.language.manipulation import detect_manipulation
from littleboy.language.models import (
    ConstructiveLanguageAssessment,
    LanguageAct,
    LanguageAnalysis,
    LanguageContext,
    LanguageEthicsProfile,
    ManipulationFinding,
)
from littleboy.language.scoring import (
    score_language_ethics,
    score_linguistic_coercion,
)

__all__ = [
    "ConstructiveLanguageAssessment",
    "LanguageAct",
    "LanguageAnalysis",
    "LanguageContext",
    "LanguageEthicsProfile",
    "ManipulationFinding",
    "analyze_language",
    "detect_manipulation",
    "language_to_coercion_profile",
    "merge_coercion_profiles",
    "score_constructive_language",
    "score_language_ethics",
    "score_linguistic_coercion",
]
