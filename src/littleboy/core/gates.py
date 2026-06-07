"""Critical-data gates for LittleBoy.

A central, auditable checklist of the facts LittleBoy considers *critical* to a
sound judgment. When such facts are missing, the engine must say so (Axiom 5),
lower its confidence, and -- where useful -- propose the questions that would
resolve the gap. This module computes both the list of missing critical data
and the recommended next questions, from the same single source of truth.
"""

from __future__ import annotations

from littleboy.core.enums import ConsentStatus
from littleboy.core.models import ActionCase

# Each critical-data key maps to a human-readable "what's missing" label and a
# concrete clarifying question. Keeping them together keeps the two outputs in
# lockstep.
_MISSING_LABEL: dict[str, str] = {
    "agent_type": "acting agent type (Type I or Type II)",
    "affected_agents": "identity of the affected agents",
    "coercion_presence": "whether coercion is present (no coercion profile supplied)",
    "coercion_source": "whether coercion is already occurring (the coercion source)",
    "alternatives": "possible less-coercive alternatives",
    "reversibility": "reversibility of the action",
    "consequences": "the likely consequences of the action",
    "consent": "consent status of the affected agents",
    "source_reliability": "source reliability / supporting evidence",
    "vulnerability": "vulnerability of the affected agents",
}

_QUESTION: dict[str, str] = {
    "agent_type": "Is the acting agent a Type I or Type II moral agent?",
    "affected_agents": "Who are the agents affected by this action?",
    "coercion_presence": "What coercion, if any, does this action involve?",
    "coercion_source": "Is this action a response to existing or imminent coercion?",
    "alternatives": "What less-coercive alternatives were considered, and how feasible are they?",
    "reversibility": "Is the action's effect reversible, and to what degree?",
    "consequences": "What are the expected consequences of the action?",
    "consent": "Did the affected agents consent, and was that consent informed and voluntary?",
    "source_reliability": "How reliable are the sources for the claims in this case?",
    "vulnerability": "How vulnerable are the affected agents?",
}


def _missing_keys(case: ActionCase) -> list[str]:
    """Return the keys of critical data absent from the case, in checklist order."""
    keys: list[str] = []

    # A language act characterises coercion (and its reversibility via context) too.
    has_coercion = case.coercion_profile is not None or case.language_act is not None
    reversibility_known = (
        case.coercion_profile is not None and case.coercion_profile.reversibility_is_known
    ) or case.language_act is not None

    if case.effective_agent_type() is None:
        keys.append("agent_type")
    if not case.affected_agents:
        keys.append("affected_agents")
    if not has_coercion:
        keys.append("coercion_presence")
    if case.responds_to_existing_coercion is None:
        keys.append("coercion_source")
    if case.available_alternatives is None:
        keys.append("alternatives")
    if not reversibility_known:
        keys.append("reversibility")
    if case.expected_consequences is None:
        keys.append("consequences")
    if case.effective_consent_status() == ConsentStatus.UNKNOWN:
        keys.append("consent")
    if case.data_quality is None and case.evidence is None:
        keys.append("source_reliability")
    if case.agency_profile is None:
        keys.append("vulnerability")

    return keys


def detect_missing_critical_data(case: ActionCase) -> list[str]:
    """Return human-readable descriptions of the critical data missing from a case."""
    return [_MISSING_LABEL[key] for key in _missing_keys(case)]


def recommended_next_questions(case: ActionCase) -> list[str]:
    """Return the clarifying questions that would resolve the missing critical data."""
    return [_QUESTION[key] for key in _missing_keys(case)]
