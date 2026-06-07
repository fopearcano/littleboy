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

from littleboy.case_builder import (
    CaseBuilder,
    ScenarioTemplate,
    build_case_from_answers,
    completeness_report,
    generate_questions,
    get_template,
    list_templates,
    wizard_prompts,
)
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
    LanguageMedium,
    PolicyMode,
    QuestionCategory,
    QuestionPriority,
    RuleResultStatus,
    RuleSeverity,
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
    CaseCompletenessReport,
    CoercionJustification,
    CoercionProfile,
    ConsentProfile,
    DataQualityProfile,
    EvaluationReport,
    ExperimentSummary,
    JustificationResult,
    MoralAgent,
    Question,
    QuestionSet,
    ReasoningTrace,
    RuleResult,
)
from littleboy.data.evidence import EvidenceItem, EvidenceSet
from littleboy.language import (
    ConstructiveLanguageAssessment,
    LanguageAct,
    LanguageAnalysis,
    LanguageContext,
    LanguageEthicsProfile,
    ManipulationFinding,
    analyze_language,
    detect_manipulation,
    score_constructive_language,
    score_language_ethics,
    score_linguistic_coercion,
)
from littleboy.reasoning.experiment import EthicalExperiment, EthicalExperimentResult
from littleboy.rules import (
    BUILTIN_RULES,
    PolicyProfile,
    Rule,
    RuleEngine,
    RuleRegistry,
    default_registry,
    get_policy,
)

__version__ = "0.5.0"

__all__ = [
    "BUILTIN_RULES",
    "ActionCase",
    "AgencyProfile",
    "AgentType",
    "Alternative",
    "AlternativeAction",
    "AlternativeAnalysis",
    "AlternativeSet",
    "CaseBuilder",
    "CaseCompletenessReport",
    "CoercionJustification",
    "ConstructiveLanguageAssessment",
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
    "LanguageAct",
    "LanguageAnalysis",
    "LanguageContext",
    "LanguageEthicsProfile",
    "LanguageMedium",
    "ManipulationFinding",
    "MoralAgent",
    "PolicyMode",
    "PolicyProfile",
    "Question",
    "QuestionCategory",
    "QuestionPriority",
    "QuestionSet",
    "ReasoningTrace",
    "Rule",
    "RuleEngine",
    "RuleRegistry",
    "RuleResult",
    "RuleResultStatus",
    "RuleSeverity",
    "ScenarioTemplate",
    "SourceType",
    "UncertaintyLevel",
    "Verdict",
    "agent_can_bear_duties",
    "analyse_alternatives",
    "analyze_language",
    "assess_agency",
    "assess_consent",
    "build_case_from_answers",
    "completeness_report",
    "default_registry",
    "detect_manipulation",
    "detect_missing_critical_data",
    "evaluate_coercion_justification",
    "generate_questions",
    "get_policy",
    "get_template",
    "list_templates",
    "recommended_next_questions",
    "score_constructive_language",
    "score_language_ethics",
    "score_linguistic_coercion",
    "wizard_prompts",
    "__version__",
]
