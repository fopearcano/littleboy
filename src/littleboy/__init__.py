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

from littleboy.core.enums import (
    AgentType,
    ConsentStatus,
    UncertaintyLevel,
    Verdict,
)
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import (
    ActionCase,
    Alternative,
    CoercionJustification,
    CoercionProfile,
    DataQualityProfile,
    EvaluationReport,
    MoralAgent,
)

__version__ = "0.1.0"

__all__ = [
    "ActionCase",
    "AgentType",
    "Alternative",
    "CoercionJustification",
    "CoercionProfile",
    "ConsentStatus",
    "DataQualityProfile",
    "EthicalEvaluator",
    "EvaluationReport",
    "MoralAgent",
    "UncertaintyLevel",
    "Verdict",
    "__version__",
]
