"""Wizard session logic for the LittleBoy case builder.

This module is deliberately free of input/output: it declares the prompts a
wizard should ask (optionally tailored to a template) and turns a flat dict of
answers into a validated :class:`~littleboy.core.models.ActionCase`. The CLI
supplies the actual prompting. Keeping the parsing here makes the wizard
testable without a terminal.

The session only records what the user actually answers; blank answers leave the
corresponding field unset (``None``), so the case builder can then ask for them.
It never fabricates values.
"""

from __future__ import annotations

from dataclasses import dataclass

from littleboy.case_builder.templates import ScenarioTemplate
from littleboy.core.enums import AgentType, ConsentStatus
from littleboy.core.models import (
    ActionCase,
    CoercionProfile,
    DataQualityProfile,
    MoralAgent,
)

_COERCION_CHANNELS = {
    "physical_force",
    "threat",
    "economic_pressure",
    "psychological_pressure",
    "informational_manipulation",
    "legal_constraint",
    "social_pressure",
}
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


@dataclass
class WizardPrompt:
    """A single prompt the wizard should present."""

    key: str
    text: str
    answer_type: str  # text | agent_type | consent_status | score_0_1 | boolean
    choices: list[str] | None = None


def wizard_prompts(template: ScenarioTemplate | None = None) -> list[WizardPrompt]:
    """Return the ordered prompts for a build session, tailored to ``template``."""
    channels = template.typical_coercion_dimensions if template else ["social_pressure"]
    # Keep only recognised channels; fall back to social_pressure if none.
    channels = [c for c in channels if c in _COERCION_CHANNELS] or ["social_pressure"]

    prompts: list[WizardPrompt] = [
        WizardPrompt("title", "Title of the action", "text"),
        WizardPrompt("description", "Describe the action", "text"),
        WizardPrompt("acting_agent_name", "Name of the acting agent", "text"),
        WizardPrompt(
            "acting_agent_type",
            "Acting agent type",
            "agent_type",
            choices=[AgentType.TYPE_I.value, AgentType.TYPE_II.value],
        ),
        WizardPrompt("affected_agent_name", "Name of an affected agent", "text"),
        WizardPrompt(
            "consent",
            "Consent status of the affected agents",
            "consent_status",
            choices=[s.value for s in ConsentStatus],
        ),
    ]
    for channel in channels:
        prompts.append(
            WizardPrompt(f"coercion.{channel}", f"Coercion via {channel} (0-1)", "score_0_1")
        )
    prompts += [
        WizardPrompt("coercion.severity", "Overall severity of the coercion (0-1)", "score_0_1"),
        WizardPrompt(
            "coercion.reversibility",
            "Reversibility (0 = irreversible, 1 = fully reversible)",
            "score_0_1",
        ),
        WizardPrompt(
            "responds_to_existing_coercion",
            "Does the action respond to existing/imminent coercion? (yes/no)",
            "boolean",
        ),
        WizardPrompt("expected_consequences", "Expected consequences of the action", "text"),
        WizardPrompt(
            "alternatives_analysed",
            "Were less-coercive alternatives analysed? (yes/no)",
            "boolean",
        ),
        WizardPrompt(
            "info_reliability", "Overall reliability of the information (0-1)", "score_0_1"
        ),
    ]
    return prompts


def _score(value: str) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _bool(value: str) -> bool | None:
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return None


def build_case_from_answers(
    answers: dict[str, str], *, template: ScenarioTemplate | None = None
) -> ActionCase:
    """Build a (possibly partial) :class:`ActionCase` from collected wizard answers.

    Blank/missing answers leave their field unset, so the resulting case is only
    as complete as the user made it -- by design.
    """

    def get(key: str) -> str:
        return (answers.get(key) or "").strip()

    data: dict[str, object] = {"title": get("title") or "Untitled action"}

    if get("description"):
        data["description"] = get("description")

    # Acting agent.
    agent_name = get("acting_agent_name")
    agent_type = get("acting_agent_type")
    if agent_name or agent_type:
        parsed_type = None
        if agent_type:
            try:
                parsed_type = AgentType(agent_type)
            except ValueError:
                parsed_type = None
        data["acting_agent"] = MoralAgent(name=agent_name or "acting agent", agent_type=parsed_type)

    # Affected agents (one, in the minimal wizard).
    if get("affected_agent_name"):
        data["affected_agents"] = [MoralAgent(name=get("affected_agent_name"))]

    # Consent.
    if get("consent"):
        try:
            data["consent"] = ConsentStatus(get("consent"))
        except ValueError:
            pass

    # Coercion profile: only build it if at least one coercion value was given.
    coercion_fields: dict[str, float] = {}
    for key, value in answers.items():
        if key.startswith("coercion.") and (value or "").strip():
            field = key.split(".", 1)[1]
            score = _score(value)
            if score is not None:
                coercion_fields[field] = score
    if coercion_fields:
        data["coercion_profile"] = CoercionProfile(**coercion_fields)

    # Coercion source.
    if get("responds_to_existing_coercion"):
        parsed = _bool(get("responds_to_existing_coercion"))
        if parsed is not None:
            data["responds_to_existing_coercion"] = parsed

    if get("expected_consequences"):
        data["expected_consequences"] = get("expected_consequences")

    # Alternatives: "yes" => analysed (empty set captured); "no"/blank => unknown.
    if get("alternatives_analysed"):
        if _bool(get("alternatives_analysed")) is True:
            data["available_alternatives"] = []

    # Data quality: a single coarse reliability proxy.
    reliability = _score(get("info_reliability")) if get("info_reliability") else None
    if reliability is not None:
        data["data_quality"] = DataQualityProfile(
            completeness=reliability,
            source_reliability=reliability,
            specificity=reliability,
            recency=reliability,
            corroboration=reliability,
            ambiguity=round(1.0 - reliability, 4),
        )

    return ActionCase(**data)
