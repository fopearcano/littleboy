"""Tests for the v0.3 rule engine, policies, and reasoning trace."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    AgentType,
    AlternativeAction,
    CoercionJustification,
    CoercionProfile,
    ConsentStatus,
    DataQualityProfile,
    EpistemicStatus,
    EthicalEvaluator,
    EvidenceItem,
    EvidenceSet,
    MoralAgent,
    PolicyMode,
    RuleRegistry,
    SourceType,
    Verdict,
    default_registry,
)
from littleboy.cli import app
from littleboy.rules.base import Rule
from littleboy.rules.builtin_rules import BUILTIN_RULES

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}
runner = CliRunner()


# --- builders ----------------------------------------------------------------


def _agent(name: str = "A") -> MoralAgent:
    return MoralAgent(name=name, agent_type=AgentType.TYPE_II)


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.85,
        source_reliability=0.85,
        specificity=0.8,
        recency=0.85,
        corroboration=0.8,
        ambiguity=0.15,
    )


def _case(**overrides) -> ActionCase:
    defaults = dict(
        title="Case",
        acting_agent=_agent(),
        affected_agents=[_agent("B")],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
        available_alternatives=[],
        data_quality=_good_data(),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="benign",
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


def _result_for(report, rule_id: str):
    return next(r for r in report.reasoning_trace.applied if r.rule_id == rule_id)


# --- 1. registry can register and list rules ---------------------------------


def test_registry_registers_and_lists_rules():
    class DummyRule(Rule):
        rule_id = "Z-001"
        name = "Dummy"

        def evaluate(self, ctx):  # pragma: no cover - not run here
            raise NotImplementedError

    reg = RuleRegistry()
    reg.register(DummyRule())
    assert "Z-001" in reg
    assert reg.rule_ids() == ["Z-001"]
    assert len(reg) == 1
    with pytest.raises(ValueError):
        reg.register(DummyRule())  # duplicate id

    assert len(default_registry()) == 12


# --- 2. all built-in rules are well-formed -----------------------------------


def test_all_builtin_rules_have_metadata():
    ids = []
    for rule_cls in BUILTIN_RULES:
        rule = rule_cls()
        assert rule.rule_id.startswith("LB-R")
        assert rule.name
        assert rule.description
        assert rule.axioms_invoked  # at least one axiom
        ids.append(rule.rule_id)
    assert len(set(ids)) == len(ids) == 12


# --- 3. Type I agent does not receive moral-duty assignment ------------------


def test_type_i_agent_not_assigned_duties():
    case = _case(acting_agent=MoralAgent(name="Dog", agent_type=AgentType.TYPE_I))
    report = EthicalEvaluator().evaluate(case)
    r001 = _result_for(report, "LB-R001")
    assert r001.status.value == "not_applicable"
    assert any("Type I" in w for w in report.warnings)


# --- 4. unknown agent type lowers confidence ---------------------------------


def test_unknown_agent_type_lowers_confidence():
    known = EthicalEvaluator().evaluate(_case(acting_agent=_agent()))
    unknown = EthicalEvaluator().evaluate(_case(acting_agent=MoralAgent(name="?")))
    assert unknown.confidence < known.confidence


# --- 5. unknown consent: downgrade/block according to policy -----------------


def test_unknown_consent_blocks_only_under_strict_policy():
    case = _case(
        coercion_profile=CoercionProfile(economic_pressure=0.25, reversibility=0.8, severity=0.1),
        data_quality=DataQualityProfile(
            completeness=0.7,
            source_reliability=0.7,
            specificity=0.6,
            recency=0.7,
            corroboration=0.6,
            ambiguity=0.15,
        ),
        consent=ConsentStatus.UNKNOWN,
    )
    std = EthicalEvaluator(PolicyMode.STANDARD).evaluate(case)
    strict = EthicalEvaluator(PolicyMode.STRICT).evaluate(case)
    assert "LB-R003" not in std.reasoning_trace.blockers
    assert "LB-R003" in strict.reasoning_trace.blockers
    assert strict.verdict == Verdict.ETHICALLY_SUSPICIOUS
    assert std.verdict in POSITIVE


# --- 6. high coercion without justification is not acceptable ----------------


def test_high_coercion_without_justification_not_acceptable():
    case = _case(
        coercion_profile=CoercionProfile(
            physical_force=0.9, severity=0.8, reversibility=0.3, scope_number_of_agents=5
        ),
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict == Verdict.NOT_ACCEPTABLE
    assert "LB-R007" in report.reasoning_trace.blockers


# --- 7. justified emergency coercion can pass with reservations --------------


def test_justified_emergency_coercion_acceptable_with_reservations():
    case = _case(
        coercion_profile=CoercionProfile(
            physical_force=0.7, threat=0.3, duration=0.2, reversibility=0.9, severity=0.5
        ),
        available_alternatives=[
            AlternativeAction(title="Do nothing", estimated_coercion_score=0.95, feasibility=1.0),
            AlternativeAction(title="Talk", estimated_coercion_score=0.15, feasibility=0.2),
        ],
        consent=ConsentStatus.NOT_APPLICABLE,
        responds_to_existing_coercion=True,
        justification=CoercionJustification(
            responds_to_existing_or_imminent_coercion=EpistemicStatus.CONFIRMED,
            no_less_coercive_alternative_available=EpistemicStatus.LIKELY,
            necessity=EpistemicStatus.CONFIRMED,
            proportionality=EpistemicStatus.LIKELY,
            expected_total_coercion_reduction=0.6,
            cessation_condition_defined=EpistemicStatus.CONFIRMED,
            reversibility=EpistemicStatus.CONFIRMED,
        ),
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.verdict == Verdict.ACCEPTABLE_WITH_RESERVATIONS


# --- 8. feasible less-coercive alternative downgrades the verdict ------------


def test_feasible_less_coercive_alternative_downgrades():
    low = CoercionProfile(social_pressure=0.15, reversibility=1.0, severity=0.05)
    without = EthicalEvaluator().evaluate(_case(coercion_profile=low, available_alternatives=[]))
    with_alt = EthicalEvaluator().evaluate(
        _case(
            coercion_profile=low,
            available_alternatives=[
                AlternativeAction(title="Just ask", estimated_coercion_score=0.0, feasibility=1.0)
            ],
        )
    )
    assert without.verdict == Verdict.ACCEPTABLE
    assert with_alt.verdict == Verdict.ACCEPTABLE_WITH_RESERVATIONS
    assert "LB-R006" in with_alt.reasoning_trace.failed


# --- 9. weak evidence lowers confidence --------------------------------------


def test_weak_evidence_lowers_confidence():
    strong = EvidenceSet(
        items=[
            EvidenceItem(
                claim="documented",
                source_type=SourceType.DOCUMENT,
                reliability=0.9,
                specificity=0.9,
                recency=0.9,
                corroboration=0.85,
            )
        ]
    )
    weak = EvidenceSet(
        items=[
            EvidenceItem(
                claim="documented",
                source_type=SourceType.DOCUMENT,
                reliability=0.9,
                specificity=0.9,
                recency=0.9,
                corroboration=0.85,
            ),
            EvidenceItem(
                claim="rumour",
                source_type=SourceType.UNKNOWN,
                reliability=0.2,
                specificity=0.2,
                recency=0.3,
                corroboration=0.1,
                contested=True,
            ),
        ]
    )
    strong_report = EthicalEvaluator().evaluate(_case(evidence=strong))
    weak_report = EthicalEvaluator().evaluate(_case(evidence=weak))
    assert weak_report.confidence < strong_report.confidence
    assert "LB-R005" in weak_report.reasoning_trace.failed


# --- 10. informational manipulation triggers the coercion rule ---------------


def test_informational_manipulation_triggers_rule():
    case = _case(
        coercion_profile=CoercionProfile(informational_manipulation=0.8, reversibility=0.6),
        consent=ConsentStatus.UNKNOWN,
        available_alternatives=None,
    )
    report = EthicalEvaluator().evaluate(case)
    r009 = _result_for(report, "LB-R009")
    assert r009.status.value == "failed"
    assert report.coercion_score > 0.5
    assert any("informational manipulation" in w.lower() for w in report.warnings)


# --- 11. irreversible action with poor data is blocked / insufficient --------


def test_irreversible_with_poor_data_is_insufficient():
    report = EthicalEvaluator().evaluate(
        ActionCase.model_validate_json((EXAMPLES / "irreversible_low_data_case.json").read_text())
    )
    assert report.verdict == Verdict.INSUFFICIENT_DATA
    assert "LB-R010" in report.reasoning_trace.blockers


# --- 12. contradiction rule catches incompatible conclusions -----------------


def test_contradiction_rule_flags_incompatible_claims():
    report = EthicalEvaluator().evaluate(
        ActionCase.model_validate_json((EXAMPLES / "contradiction_case.json").read_text())
    )
    assert "LB-R012" in report.reasoning_trace.contradictions
    r012 = _result_for(report, "LB-R012")
    assert r012.severity.value == "contradiction"


# --- 13. different policy profiles produce different strictness --------------


def test_policies_produce_different_strictness():
    case = ActionCase.model_validate_json((EXAMPLES / "policy_permissive_case.json").read_text())
    permissive = EthicalEvaluator(PolicyMode.PERMISSIVE).evaluate(case)
    standard = EthicalEvaluator(PolicyMode.STANDARD).evaluate(case)
    assert permissive.verdict != standard.verdict
    assert permissive.verdict in POSITIVE
    assert standard.verdict == Verdict.NOT_ACCEPTABLE


# --- 14. final report includes a complete rule trace -------------------------


def test_report_includes_complete_rule_trace():
    report = EthicalEvaluator().evaluate(_case())
    tr = report.reasoning_trace
    assert tr is not None
    assert len(tr.applied) == 12
    assert tr.final_verdict == report.verdict
    assert tr.policy_mode == PolicyMode.STANDARD
    assert report.policy_mode == PolicyMode.STANDARD
    assert 0.0 <= tr.base_confidence <= 1.0
    assert tr.final_confidence == report.confidence
    # Every applied rule carries its identity and axioms.
    for r in tr.applied:
        assert r.rule_id and r.name


# --- 15. CLI output includes the rule trace ----------------------------------


def test_cli_output_includes_rule_trace():
    result = runner.invoke(
        app, ["evaluate", str(EXAMPLES / "manipulative_language_case.json"), "--policy", "strict"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["policy_mode"] == "strict"
    assert "reasoning_trace" in payload
    assert len(payload["reasoning_trace"]["applied"]) == 12
    assert "final_verdict" in payload["reasoning_trace"]


def test_cli_rejects_unknown_policy(tmp_path):
    result = runner.invoke(
        app, ["evaluate", str(EXAMPLES / "simple_case.json"), "--policy", "nonsense"]
    )
    assert result.exit_code == 2
    assert "Unknown policy" in result.output
