"""Typed models for the LittleBoy language & coercion module.

Core thesis: **language is ethically relevant because it can either expand or
restrict the field of possible understanding, expression, consent, and will.**
Language can clarify, liberate, and disclose; or it can manipulate, obscure,
shame, confuse, frame, silence, or replace the subject's own meaning-field with
someone else's.

These models are deliberately simple and typed. The scores on
:class:`LanguageEthicsProfile` are **heuristic indicators, not absolute moral
truths**. There is no NLP/ML here: indicators are either supplied explicitly or
detected by a small, transparent, documented lexicon (see
:mod:`littleboy.language.manipulation`).

This module depends only on :mod:`littleboy.core.enums` and
:mod:`littleboy.data.evidence`, so ``core.models`` can embed a language act
without an import cycle. A language act therefore refers to agents by *name*
(strings); the fully-typed agents live on the surrounding ``ActionCase``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import LanguageMedium
from littleboy.data.evidence import EvidenceSet


class _LangBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LanguageContext(_LangBase):
    """The situation in which a language act occurs.

    These factors do not make language coercive on their own, but they
    *amplify* the effect of manipulative language: pressure on a vulnerable
    person, under a power asymmetry, at high stakes, is far more coercive.
    """

    medium: LanguageMedium = LanguageMedium.UNKNOWN
    power_asymmetry: float = Field(default=0.0, ge=0.0, le=1.0)
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    target_vulnerability: float = Field(default=0.0, ge=0.0, le=1.0)
    stakes: float = Field(default=0.0, ge=0.0, le=1.0)
    reversibility: float = Field(
        default=1.0, ge=0.0, le=1.0, description="1.0 = the effect of the words is reversible."
    )
    audience_scope: float = Field(
        default=0.0, ge=0.0, le=1.0, description="0 = one listener, 1 = a mass audience."
    )
    notes: str = ""


class LanguageEthicsProfile(_LangBase):
    """A transparent, multi-axis description of the ethics of a language act.

    Two groups of axes. **Quality** axes (higher is better): clarity,
    truthfulness, specificity, context_completeness, agency_respect,
    consent_support, constructive_potential. **Risk** axes (higher is worse):
    manipulation_risk, shame_pressure, fear_pressure, false_necessity,
    false_dichotomy, loaded_language, omission_risk, ambiguity_level,
    silencing_effect.

    Every axis is a heuristic indicator in ``[0, 1]``, not a measurement. A
    default profile is neutral (quality 0.5, risk 0.0).
    """

    # Quality axes (higher = better).
    clarity: float = Field(default=0.5, ge=0.0, le=1.0)
    truthfulness: float = Field(default=0.5, ge=0.0, le=1.0)
    specificity: float = Field(default=0.5, ge=0.0, le=1.0)
    context_completeness: float = Field(default=0.5, ge=0.0, le=1.0)
    agency_respect: float = Field(default=0.5, ge=0.0, le=1.0)
    consent_support: float = Field(default=0.5, ge=0.0, le=1.0)
    constructive_potential: float = Field(default=0.5, ge=0.0, le=1.0)

    # Risk axes (higher = worse).
    manipulation_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    shame_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    fear_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    false_necessity: float = Field(default=0.0, ge=0.0, le=1.0)
    false_dichotomy: float = Field(default=0.0, ge=0.0, le=1.0)
    loaded_language: float = Field(default=0.0, ge=0.0, le=1.0)
    omission_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity_level: float = Field(default=0.0, ge=0.0, le=1.0)
    silencing_effect: float = Field(default=0.0, ge=0.0, le=1.0)


class LanguageAct(_LangBase):
    """A unit of language to be evaluated for its ethical effect."""

    text: str = Field(default="", description="The words spoken or written.")
    speaker_agent: str | None = Field(default=None, description="Name of the speaker.")
    target_agents: list[str] = Field(default_factory=list, description="Names of those addressed.")
    declared_intent: str | None = None
    context: LanguageContext | None = None
    ethics_profile: LanguageEthicsProfile | None = Field(
        default=None,
        description="Explicitly-supplied ethics indicators (merged with text detections).",
    )
    evidence: EvidenceSet | None = None
    notes: str = ""


class ManipulationFinding(_LangBase):
    """One detected indicator of linguistic manipulation, with its provenance."""

    indicator: str
    severity: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(default="", description="The phrase detected, or 'supplied'.")
    note: str = ""


class ConstructiveLanguageAssessment(_LangBase):
    """How much a language act expands (rather than restricts) the field of will."""

    constructive_score: float = Field(ge=0.0, le=1.0)
    liberating_effect: float = Field(ge=0.0, le=1.0)
    clarifying_effect: float = Field(ge=0.0, le=1.0)
    agency_support: float = Field(ge=0.0, le=1.0)
    consent_support: float = Field(ge=0.0, le=1.0)
    uncertainty_transparency: float = Field(ge=0.0, le=1.0)
    alternative_visibility: float = Field(ge=0.0, le=1.0)
    recommended_rewrite: str = ""
    warnings: list[str] = Field(default_factory=list)


class LanguageAnalysis(_LangBase):
    """The full, auditable result of analysing a language act."""

    linguistic_coercion_score: float = Field(ge=0.0, le=1.0)
    profile: LanguageEthicsProfile
    context: LanguageContext
    constructive: ConstructiveLanguageAssessment
    manipulation_findings: list[ManipulationFinding] = Field(default_factory=list)
    dominant_indicators: list[str] = Field(default_factory=list)
    affects_consent: bool = False
    replaces_subject_framing: bool = False
    warnings: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    recommended_questions: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
