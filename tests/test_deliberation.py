"""Tests for the v0.9 deliberation & value-of-information layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typer.testing import CliRunner

from littleboy import (
    ActionCase,
    AgentType,
    CoercionProfile,
    ConsentStatus,
    ConsequenceEstimate,
    ConsequenceSet,
    DataQualityProfile,
    Deliberator,
    MoralAgent,
    TimeHorizon,
    Verdict,
)
from littleboy.cli import app
from littleboy.comparison.models import ActionComparisonSet
from littleboy.deliberation import Deliberator as _Deliberator  # noqa: F401  (re-export check)
from littleboy.deliberation.intake import apply_intake_answer, run_minimal_intake
from littleboy.deliberation.minimal_case import DEFAULT_QUESTION_COSTS, plan_minimal_questions
from littleboy.deliberation.voi import (
    cheapest_flip_set,
    minimal_flip_sets,
    value_of_information,
    verdict_distance,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
runner = CliRunner()


def _load(name: str) -> ActionCase:
    return ActionCase.model_validate_json((EXAMPLES / name).read_text())


def _load_set(name: str) -> ActionComparisonSet:
    return ActionComparisonSet.model_validate_json((EXAMPLES / name).read_text())


# --- narration ---------------------------------------------------------------


def test_deliberation_narrates_verdict():
    d = Deliberator("standard").deliberate(_load("manipulative_language_case.json"))
    assert d.headline
    assert d.verdict is not None
    assert d.steps  # there is always at least the coercion/confidence context
    # the narration agrees with the evaluator's verdict
    assert d.verdict.value in d.headline


# --- value of information: the pivotal unknown -------------------------------


def test_voi_identifies_pivotal_consent():
    d = Deliberator("standard").deliberate(_load("voi_consent_pivotal.json"))
    assert d.most_informative is not None
    assert d.most_informative.field == "consent"
    assert d.most_informative.changes_verdict is True
    assert d.stable_under_information is False


def test_voi_records_counterfactual_resolutions():
    d = Deliberator("standard").deliberate(_load("voi_consent_pivotal.json"))
    res = d.most_informative.resolutions
    assert len(res) == 2
    # the two resolutions land on different verdicts (that is why it is pivotal)
    assert len({r.verdict for r in res}) > 1


def test_fully_specified_case_is_information_stable():
    case = ActionCase(
        title="Fully specified, low-coercion, consented action",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
        data_quality=DataQualityProfile(
            completeness=0.85,
            source_reliability=0.85,
            specificity=0.85,
            recency=0.85,
            corroboration=0.8,
            ambiguity=0.15,
        ),
        consent=ConsentStatus.GIVEN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="no lasting effect",
                    horizon=TimeHorizon.SHORT_TERM,
                    coercion_delta=-0.05,
                    probability=0.8,
                    confidence=0.8,
                )
            ]
        ),
    )
    d = Deliberator("standard").deliberate(case)
    assert d.information_values == []
    assert d.most_informative is None
    assert d.stable_under_information is True


# --- comparison deliberation -------------------------------------------------


def test_comparison_deliberation_finds_pivotal_option_fact():
    cd = Deliberator("standard").deliberate_comparison(_load_set("comparison_voi_pivotal.json"))
    assert cd.best_option_id == "option_x"
    assert cd.most_informative is not None
    assert cd.most_informative.changes_best_option is True
    assert cd.most_informative.value == 1.0
    assert cd.ranking_robust is False
    assert cd.why_top_wins


# --- helpers -----------------------------------------------------------------


def test_verdict_distance_metric():
    assert verdict_distance(Verdict.ACCEPTABLE, Verdict.ACCEPTABLE) == 0.0
    assert verdict_distance(Verdict.ACCEPTABLE, Verdict.NOT_ACCEPTABLE) == 1.0
    # resolving (or creating) the data gate is a maximal change
    assert verdict_distance(Verdict.INSUFFICIENT_DATA, Verdict.ACCEPTABLE) == 1.0


# --- CLI ---------------------------------------------------------------------


def test_cli_deliberate_case_works():
    result = runner.invoke(app, ["deliberate", str(EXAMPLES / "voi_consent_pivotal.json")])
    assert result.exit_code == 0
    assert "DELIBERATION:" in result.stdout
    assert "Most informative unknown" in result.stdout


def test_cli_deliberate_comparison_works():
    result = runner.invoke(
        app,
        [
            "deliberate",
            str(EXAMPLES / "comparison_voi_pivotal.json"),
            "--compare",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert '"target": "comparison"' in result.stdout


# --- backward compatibility --------------------------------------------------


def test_deliberation_does_not_change_default_evaluation():
    from littleboy import EthicalEvaluator

    case = _load("voi_consent_pivotal.json")
    base = EthicalEvaluator("standard").evaluate(case)
    # deliberation re-runs the evaluator internally; the user's own report is untouched.
    Deliberator("standard").deliberate(case)
    again = EthicalEvaluator("standard").evaluate(case)
    assert base.verdict == again.verdict
    assert base.audit_report is None


# --- multi-fact value of information -----------------------------------------


def test_single_pivotal_fact_is_a_size_one_flip_set():
    d = Deliberator("standard").deliberate(_load("voi_consent_pivotal.json"))
    assert d.smallest_flip_size == 1
    assert d.verdict_robust_to_combinations is False
    assert ["consent"] in [fs.fields for fs in d.minimal_flip_sets]


@dataclass
class _StubReport:
    verdict: Verdict
    confidence: float = 0.5


class _AndEvaluator:
    """A stub evaluator that flips to ACCEPTABLE only when BOTH unknowns are resolved.

    Lets us test the multi-fact search's combination logic and minimality
    independently of the real (discrete) rule thresholds.
    """

    def evaluate(self, case: ActionCase) -> _StubReport:
        consent_known = case.effective_consent_status() != ConsentStatus.UNKNOWN
        rev_known = (
            case.coercion_profile is not None and case.coercion_profile.reversibility is not None
        )
        if consent_known and rev_known:
            return _StubReport(Verdict.ACCEPTABLE)
        return _StubReport(Verdict.NOT_ACCEPTABLE)


def _two_unknown_case() -> ActionCase:
    # Exactly two probes fire: consent (UNKNOWN) and coercion.reversibility (None).
    return ActionCase(
        title="Two-unknown case",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.3, severity=0.3),  # reversibility None
        data_quality=DataQualityProfile(
            completeness=0.8,
            source_reliability=0.8,
            specificity=0.8,
            recency=0.8,
            corroboration=0.8,
            ambiguity=0.2,
        ),
        consent=ConsentStatus.UNKNOWN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="benign",
                    horizon=TimeHorizon.SHORT_TERM,
                    coercion_delta=-0.05,
                    probability=0.8,
                    confidence=0.8,
                )
            ]
        ),
    )


def test_multifact_search_finds_a_minimal_size_two_set():
    case = _two_unknown_case()
    evaluator = _AndEvaluator()
    # Neither unknown, alone, changes the verdict ...
    for iv in value_of_information(case, evaluator):
        assert iv.changes_verdict is False
    # ... but the two together do: the minimal flip set has size 2.
    flip_sets, smallest = minimal_flip_sets(case, evaluator, max_size=3)
    assert smallest == 2
    assert flip_sets
    assert set(flip_sets[0].fields) == {"consent", "coercion.reversibility"}
    assert flip_sets[0].resulting_verdict == Verdict.ACCEPTABLE


# --- minimal-sufficient-case question plan -----------------------------------


def test_question_plan_keeps_only_verdict_relevant_questions():
    plan = Deliberator("standard").question_plan(_load("voi_consent_pivotal.json"))
    fields = [q.field for q in plan.questions]
    assert "consent" in fields
    consent_q = next(q for q in plan.questions if q.field == "consent")
    assert consent_q.priority == "critical"
    assert consent_q.alone_changes_verdict is True
    assert plan.verdict_robust is False
    assert plan.smallest_flip_size == 1


def test_question_plan_is_empty_when_verdict_is_robust():
    case = ActionCase(
        title="Fully specified, low-coercion, consented action",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
        data_quality=DataQualityProfile(
            completeness=0.85,
            source_reliability=0.85,
            specificity=0.85,
            recency=0.85,
            corroboration=0.8,
            ambiguity=0.15,
        ),
        consent=ConsentStatus.GIVEN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="no lasting effect",
                    horizon=TimeHorizon.SHORT_TERM,
                    coercion_delta=-0.05,
                    probability=0.8,
                    confidence=0.8,
                )
            ]
        ),
    )
    plan = Deliberator("standard").question_plan(case)
    assert plan.questions == []
    assert plan.verdict_robust is True


def test_cli_questions_minimal_works():
    result = runner.invoke(
        app, ["questions", str(EXAMPLES / "voi_consent_pivotal.json"), "--minimal"]
    )
    assert result.exit_code == 0
    assert "MINIMAL QUESTION PLAN" in result.stdout


# --- cost-aware: cheapest sufficient set (v0.11) -----------------------------


class _OrEvaluator:
    """Flips to ACCEPTABLE if data is known, OR if both consent and reversibility are known.

    So {data_quality} flips alone (smallest set, but expensive) while
    {consent, coercion.reversibility} also flips (larger, but cheaper).
    """

    def evaluate(self, case: ActionCase) -> _StubReport:
        data_known = case.data_quality is not None
        consent_known = case.effective_consent_status() != ConsentStatus.UNKNOWN
        rev_known = (
            case.coercion_profile is not None and case.coercion_profile.reversibility is not None
        )
        if data_known or (consent_known and rev_known):
            return _StubReport(Verdict.ACCEPTABLE)
        return _StubReport(Verdict.NOT_ACCEPTABLE)


def _three_unknown_case() -> ActionCase:
    # Probes that fire: consent, coercion.reversibility, data_quality.
    return ActionCase(
        title="Three-unknown case",
        acting_agent=MoralAgent(name="A", agent_type=AgentType.TYPE_II),
        affected_agents=[MoralAgent(name="B", agent_type=AgentType.TYPE_II)],
        coercion_profile=CoercionProfile(social_pressure=0.3, severity=0.3),  # reversibility None
        consent=ConsentStatus.UNKNOWN,
        available_alternatives=[],
        responds_to_existing_coercion=False,
        consequences=ConsequenceSet(
            consequences=[
                ConsequenceEstimate(
                    description="benign",
                    horizon=TimeHorizon.SHORT_TERM,
                    coercion_delta=-0.05,
                    probability=0.8,
                    confidence=0.8,
                )
            ]
        ),
    )


def test_cheapest_set_prefers_two_cheap_over_one_expensive():
    case = _three_unknown_case()
    evaluator = _OrEvaluator()
    # Smallest-by-size is the single, expensive data_quality.
    flip_sets, smallest = minimal_flip_sets(case, evaluator, max_size=3)
    assert smallest == 1
    assert ["data_quality"] in [fs.fields for fs in flip_sets]
    # Cheapest-by-cost is the two cheap questions together.
    cheapest = cheapest_flip_set(case, evaluator, cost=DEFAULT_QUESTION_COSTS, max_size=3)
    assert cheapest is not None
    flip, total = cheapest
    assert set(flip.fields) == {"consent", "coercion.reversibility"}
    assert total == 2.0
    # With uniform cost the cheapest collapses back to the smallest set.
    uniform = cheapest_flip_set(case, evaluator, max_size=3)
    assert uniform[0].fields == ["data_quality"]


def test_plan_orders_cheapest_set_first():
    case = _three_unknown_case()
    plan = plan_minimal_questions(case, _OrEvaluator())
    assert plan.cheapest_set == ["consent", "coercion.reversibility"] or set(plan.cheapest_set) == {
        "consent",
        "coercion.reversibility",
    }
    # the two cheap, cheapest-set questions come before the expensive single flipper
    fields_in_order = [q.field for q in plan.questions]
    assert fields_in_order[:2] == ["consent", "coercion.reversibility"]
    assert fields_in_order[-1] == "data_quality"


# --- interactive minimal intake ----------------------------------------------


def test_apply_intake_answer_parses_fields():
    case = _load("voi_consent_pivotal.json")
    refused = apply_intake_answer(case, "consent", "refused")
    assert refused.effective_consent_status() == ConsentStatus.REFUSED
    # an unparseable answer leaves the case unchanged
    assert apply_intake_answer(case, "consent", "???").effective_consent_status() == (
        ConsentStatus.UNKNOWN
    )


def test_intake_loop_settles_the_verdict():
    case = _load("voi_consent_pivotal.json")
    answers = {"consent": "refused"}
    transcript, final_case = run_minimal_intake(
        case, lambda q: answers.get(q.field, ""), policy="standard"
    )
    assert transcript.initial_verdict == Verdict.ACCEPTABLE_WITH_RESERVATIONS
    assert transcript.final_verdict == Verdict.ETHICALLY_SUSPICIOUS
    assert transcript.settled is True
    assert transcript.questions_asked == 1
    assert transcript.steps[0].verdict_changed is True
    assert final_case.effective_consent_status() == ConsentStatus.REFUSED


def test_intake_loop_terminates_when_no_answer_progress():
    case = _load("voi_consent_pivotal.json")
    # Always answering "" makes no progress; the loop must still terminate.
    transcript, _ = run_minimal_intake(case, lambda q: "", policy="standard", max_steps=5)
    assert transcript.questions_asked <= 1
    assert transcript.final_verdict is not None
