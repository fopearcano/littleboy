"""LittleBoy: a rational ethical evaluation engine.

Foundational axiom:

    The fundamental ethical evil is coercion.
    The ethical good is the minimization or absence of coercion.

This package is an early, deliberately small foundation. It is a transparent
reasoning engine, not an oracle: it always reports its uncertainty, the data it
is missing, and the axioms it invoked. It is NOT a legal, medical, or emergency
decision-maker.
"""

from __future__ import annotations

from littleboy.core.agency import assess_agency, assess_consent
from littleboy.core.alternatives import analyse_alternatives
from littleboy.core.axioms import (
    agent_can_bear_duties,
    evaluate_coercion_justification,
)
from littleboy.core.enums import (
    AgentType,
    ConsentStatus,
    EpistemicStatus,
    SourceType,
    UncertaintyLevel,
    Verdict,
)
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.gates import (
    detect_missing_critical_data,
    recommended_next_questions,
)
from littleboy.core.models import (
    ActionCase,
    AgencyProfile,
    Alternative,
    AlternativeAction,
    AlternativeAnalysis,
    AlternativeSet,
    CoercionJustification,
    CoercionProfile,
    ConsentProfile,
    DataQualityProfile,
    EvaluationReport,
    ExperimentSummary,
    JustificationResult,
    MoralAgent,
)
from littleboy.data.evidence import EvidenceItem, EvidenceSet
from littleboy.reasoning.experiment import EthicalExperiment, EthicalExperimentResult

__version__ = "0.2.0"

__all__ = [
    "ActionCase",
    "AgencyProfile",
    "AgentType",
    "Alternative",
    "AlternativeAction",
    "AlternativeAnalysis",
    "AlternativeSet",
    "CoercionJustification",
    "CoercionProfile",
    "ConsentProfile",
    "ConsentStatus",
    "DataQualityProfile",
    "EpistemicStatus",
    "EthicalEvaluator",
    "EthicalExperiment",
    "EthicalExperimentResult",
    "EvaluationReport",
    "EvidenceItem",
    "EvidenceSet",
    "ExperimentSummary",
    "JustificationResult",
    "MoralAgent",
    "SourceType",
    "UncertaintyLevel",
    "Verdict",
    "agent_can_bear_duties",
    "analyse_alternatives",
    "assess_agency",
    "assess_consent",
    "detect_missing_critical_data",
    "evaluate_coercion_justification",
    "recommended_next_questions",
    "__version__",
]
