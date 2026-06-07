"""The rule registry: a testable, explicit collection of rules.

No global magic. A :class:`RuleRegistry` is an ordinary object you construct,
register rules on, and evaluate. Rules are returned in a stable order (sorted by
``rule_id``) so traces are reproducible. Rules can be disabled (e.g. by a policy)
without removing them, and disabled rules are reported as *skipped*.
"""

from __future__ import annotations

from littleboy.core.models import RuleResult
from littleboy.rules.base import Rule, RuleContext


class RuleRegistry:
    """An ordered, introspectable collection of rules."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._disabled: set[str] = set()

    # -- registration ---------------------------------------------------------

    def register(self, rule: Rule) -> Rule:
        """Register a rule. Raises on a duplicate or missing ``rule_id``."""
        if not rule.rule_id:
            raise ValueError(f"{type(rule).__name__} has no rule_id")
        if rule.rule_id in self._rules:
            raise ValueError(f"duplicate rule_id: {rule.rule_id}")
        self._rules[rule.rule_id] = rule
        return rule

    def register_all(self, rules: list[Rule]) -> None:
        for rule in rules:
            self.register(rule)

    # -- introspection --------------------------------------------------------

    def rules(self) -> list[Rule]:
        """All registered rules, in stable order (by rule_id)."""
        return [self._rules[rid] for rid in sorted(self._rules)]

    def rule_ids(self) -> list[str]:
        return sorted(self._rules)

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def __len__(self) -> int:
        return len(self._rules)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self._rules

    # -- enabling / disabling -------------------------------------------------

    def disable(self, *rule_ids: str) -> None:
        self._disabled.update(rule_ids)

    def enable(self, *rule_ids: str) -> None:
        self._disabled.difference_update(rule_ids)

    def is_enabled(self, rule_id: str) -> bool:
        return rule_id not in self._disabled

    # -- evaluation -----------------------------------------------------------

    def evaluate_all(self, ctx: RuleContext) -> tuple[list[RuleResult], list[str]]:
        """Evaluate every enabled rule in stable order.

        Returns ``(results, skipped_rule_ids)``. Disabled rules are skipped (not
        evaluated) and reported by id.
        """
        results: list[RuleResult] = []
        skipped: list[str] = []
        for rule in self.rules():
            if not self.is_enabled(rule.rule_id):
                skipped.append(rule.rule_id)
                continue
            results.append(rule.evaluate(ctx))
        return results, skipped
