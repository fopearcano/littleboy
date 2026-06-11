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
    REGISTRY_ENV_VAR,
    NamedPolicy,
    PolicyProfile,
    PolicyProvenance,
    PolicyRegistry,
    ProvenanceCheck,
    RegistryEntry,
    get_policy,
    load_named_policy,
    lookup_registered_policy,
    profile_changes,
    registry_dir,
    resolve_policy_ref,
    save_named_policy,
    scan_policy_registry,
    verify_named_policy,
)
from littleboy.rules.registry import RuleRegistry

__all__ = [
    "BUILTIN_RULES",
    "DEFAULT_POLICY_MODE",
    "DEFAULT_PROFILES",
    "REGISTRY_ENV_VAR",
    "NamedPolicy",
    "PolicyProfile",
    "PolicyProvenance",
    "PolicyRegistry",
    "ProvenanceCheck",
    "RegistryEntry",
    "Rule",
    "RuleContext",
    "RuleEngine",
    "RuleEngineOutcome",
    "RuleRegistry",
    "default_registry",
    "get_policy",
    "load_named_policy",
    "lookup_registered_policy",
    "profile_changes",
    "registry_dir",
    "resolve_policy_ref",
    "save_named_policy",
    "scan_policy_registry",
    "verify_named_policy",
]
