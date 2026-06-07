"""Tests for the domain models, agent duties, and coercion scoring."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from littleboy import AgentType, CoercionProfile, EpistemicStatus, MoralAgent
from littleboy.core.axioms import (
    agent_can_bear_duties,
    evaluate_coercion_justification,
)
from littleboy.core.models import CoercionJustification
from littleboy.core.scoring import HEURISTIC_DISCLAIMER, score_coercion

# --- Scenario 1: Type I agents do not receive moral duty assignment ----------


def test_type_i_agent_cannot_bear_duties():
    type_i = MoralAgent(name="Thermostat", agent_type=AgentType.TYPE_I)
    assert type_i.can_bear_duties is False
    assert agent_can_bear_duties(type_i) is False


def test_type_ii_agent_can_bear_duties():
    type_ii = MoralAgent(name="Citizen", agent_type=AgentType.TYPE_II)
    assert type_ii.can_bear_duties is True
    assert agent_can_bear_duties(type_ii) is True


def test_unknown_agent_is_not_assigned_duties():
    unknown = MoralAgent(name="Mystery")  # agent_type defaults to None
    assert unknown.type_is_known is False
    assert agent_can_bear_duties(unknown) is False
    assert agent_can_bear_duties(None) is False


# --- Model validation --------------------------------------------------------


def test_coercion_profile_rejects_out_of_range_values():
    with pytest.raises(ValidationError):
        CoercionProfile(threat=1.5)
    with pytest.raises(ValidationError):
        CoercionProfile(physical_force=-0.1)


def test_coercion_profile_rejects_unknown_fields():
    # extra="forbid" should catch typos in input keys.
    with pytest.raises(ValidationError):
        CoercionProfile(treat=0.5)  # misspelled "threat"


def test_scope_must_be_at_least_one():
    with pytest.raises(ValidationError):
        CoercionProfile(scope_number_of_agents=0)


# --- Scenario 7: informational manipulation contributes to coercion ----------


def test_informational_manipulation_increases_score():
    baseline = CoercionProfile()  # all channels zero -> no coercion
    manipulated = CoercionProfile(informational_manipulation=0.7)

    assert score_coercion(baseline).score == pytest.approx(0.0)
    assert score_coercion(manipulated).score > 0.0
    assert score_coercion(manipulated).score > score_coercion(baseline).score


def test_coercion_score_is_monotonic_in_a_channel():
    low = CoercionProfile(informational_manipulation=0.2)
    high = CoercionProfile(informational_manipulation=0.8)
    assert score_coercion(high).score > score_coercion(low).score


def test_coercion_assessment_is_transparent():
    result = score_coercion(CoercionProfile(threat=0.6, severity=0.4))
    # The heuristic disclaimer must always be present: the score is not truth.
    assert HEURISTIC_DISCLAIMER in result.reasoning
    assert result.reasoning  # non-empty explanation
    assert "threat" in result.dominant_channels


def test_unknown_reversibility_is_flagged_in_assessment():
    known = score_coercion(CoercionProfile(threat=0.5, reversibility=1.0))
    unknown = score_coercion(CoercionProfile(threat=0.5))  # reversibility None
    assert known.reversibility_known is True
    assert unknown.reversibility_known is False


# --- Axiom 3 justification checking (epistemic, tri-state) -------------------


def _full_justification(**overrides) -> CoercionJustification:
    base = dict(
        responds_to_existing_or_imminent_coercion=EpistemicStatus.CONFIRMED,
        no_less_coercive_alternative_available=EpistemicStatus.CONFIRMED,
        necessity=EpistemicStatus.CONFIRMED,
        proportionality=EpistemicStatus.CONFIRMED,
        expected_total_coercion_reduction=0.5,
        cessation_condition_defined=EpistemicStatus.CONFIRMED,
        reversibility=EpistemicStatus.CONFIRMED,
    )
    base.update(overrides)
    return CoercionJustification(**base)


def test_complete_justification_is_justified():
    result = evaluate_coercion_justification(_full_justification())
    assert result.is_justified is True
    assert result.failed_conditions == []
    assert result.unknown_conditions == []
    assert result.confidence > 0.8


def test_unknown_condition_makes_justification_unknown_not_false():
    # A genuinely unknown condition must NOT collapse to "false".
    result = evaluate_coercion_justification(_full_justification(necessity=EpistemicStatus.UNKNOWN))
    assert result.is_justified is None
    assert "the coercion is necessary" in result.unknown_conditions


def test_negative_reduction_refutes_justification():
    result = evaluate_coercion_justification(
        _full_justification(expected_total_coercion_reduction=-0.2)
    )
    assert result.is_justified is False
    assert result.failed_conditions


def test_disputed_condition_fails_justification():
    result = evaluate_coercion_justification(
        _full_justification(proportionality=EpistemicStatus.DISPUTED)
    )
    assert result.is_justified is False


def test_absent_justification_is_unknown_not_false():
    result = evaluate_coercion_justification(None)
    assert result.is_justified is None
    assert result.unknown_conditions
    assert result.confidence == 0.0
