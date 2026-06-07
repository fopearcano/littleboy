"""Tests for alternative comparison (brief scenarios 5, 6, and the feasibility guard)."""

from __future__ import annotations

from littleboy import (
    ActionCase,
    AgentType,
    AlternativeAction,
    CoercionProfile,
    ConsentStatus,
    DataQualityProfile,
    EthicalEvaluator,
    MoralAgent,
    Verdict,
)
from littleboy.core.alternatives import analyse_alternatives

POSITIVE = {Verdict.ACCEPTABLE, Verdict.ACCEPTABLE_WITH_RESERVATIONS}


def _good_data() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.9,
        source_reliability=0.9,
        specificity=0.85,
        recency=0.9,
        corroboration=0.85,
        ambiguity=0.1,
    )


def _case(**overrides) -> ActionCase:
    defaults = dict(
        title="Case",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        data_quality=_good_data(),
        consent=ConsentStatus.GIVEN,
        responds_to_existing_coercion=False,
        expected_consequences="known",
    )
    defaults.update(overrides)
    return ActionCase(**defaults)


# --- Scenario 5: a feasible less-coercive alternative downgrades the verdict --


def test_feasible_less_coercive_alternative_downgrades_verdict():
    low = CoercionProfile(social_pressure=0.15, reversibility=1.0, severity=0.05)
    gentler = AlternativeAction(title="Just ask", estimated_coercion_score=0.0, feasibility=1.0)

    without_alt = EthicalEvaluator().evaluate(
        _case(coercion_profile=low, available_alternatives=[])
    )
    with_alt = EthicalEvaluator().evaluate(
        _case(coercion_profile=low, available_alternatives=[gentler])
    )

    assert without_alt.verdict == Verdict.ACCEPTABLE
    # The feasible, clearly-less-coercive option pulls the verdict down a notch.
    assert with_alt.verdict == Verdict.ACCEPTABLE_WITH_RESERVATIONS
    assert with_alt.less_coercive_alternatives


def test_infeasible_less_coercive_alternative_does_not_defeat_action():
    fantasy = AlternativeAction(
        title="Teleport everyone to safety",
        estimated_coercion_score=0.0,
        feasibility=0.05,  # below the feasibility floor
    )
    analysis = analyse_alternatives([fantasy], proposed_coercion_score=0.7)
    assert analysis.feasible_less_coercive == []
    assert analysis.infeasible_less_coercive  # noted, but does not defeat


# --- Scenario 6: unknown alternatives block confident approval ----------------


def test_unknown_alternatives_block_confident_approval_of_coercive_action():
    moderate = CoercionProfile(threat=0.4, reversibility=0.7, severity=0.2)
    report = EthicalEvaluator().evaluate(
        _case(coercion_profile=moderate, available_alternatives=None)
    )
    assert report.verdict not in POSITIVE
    assert any("alternativ" in m.lower() for m in report.missing_data)


def test_analysis_marks_unevaluated_when_alternatives_are_none():
    analysis = analyse_alternatives(None, proposed_coercion_score=0.5)
    assert analysis.evaluated is False
    assert analysis.count == 0


def test_v01_alternative_dict_still_validates():
    # Back-compat: the v0.1 `Alternative` shape (description + coercion_profile).
    gentle = CoercionProfile(social_pressure=0.1, reversibility=1.0)
    case = _case(
        coercion_profile=CoercionProfile(threat=0.9, severity=0.8, reversibility=0.3),
        available_alternatives=[
            {"description": "Ask politely instead", "coercion_profile": gentle.model_dump()}
        ],
        consent=ConsentStatus.REFUSED,
    )
    report = EthicalEvaluator().evaluate(case)
    assert report.less_coercive_alternatives
