"""LittleBoy's formal rule engine and policy layer (v0.3).

This package turns LittleBoy from a scoring system into a transparent reasoning
machine: every judgment is traceable to explicit, named rules, the axioms they
invoke, the policy thresholds they read, and the evidence they use.
"""

from __future__ import annotations

from littleboy.rules.base import Rule, RuleContext
from littleboy.rules.builtin_rules import BUILTIN_RULES, default_registry
from littleboy.rules.engine import RuleEngine, RuleEngineOutcome
from littleboy.rules.policy import (
    DEFAULT_POLICY_MODE,
    DEFAULT_PROFILES,
    NamedPolicy,
    PolicyProfile,
    PolicyProvenance,
    get_policy,
    load_named_policy,
    resolve_policy_ref,
    save_named_policy,
)
from littleboy.rules.registry import RuleRegistry

__all__ = [
    "BUILTIN_RULES",
    "DEFAULT_POLICY_MODE",
    "DEFAULT_PROFILES",
    "NamedPolicy",
    "PolicyProfile",
    "PolicyProvenance",
    "Rule",
    "RuleContext",
    "RuleEngine",
    "RuleEngineOutcome",
    "RuleRegistry",
    "default_registry",
    "get_policy",
    "load_named_policy",
    "resolve_policy_ref",
    "save_named_policy",
]
