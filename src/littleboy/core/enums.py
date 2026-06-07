"""Enumerations used across the LittleBoy ethical evaluation engine.

These are the small, closed vocabularies of the system. Keeping them in one
place makes the conceptual ontology explicit and easy to audit.
"""

from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    """The two classes of moral agent recognised by LittleBoy.

    A *moral agent* is any entity or collective capable of action.

    - ``TYPE_I``: an entity *without* symbolic metacognition (e.g. an animal,
      a thermostat, a simple automaton). It can cause coercion in the world,
      but it cannot be morally *bound* by duties.
    - ``TYPE_II``: an entity *with* propositional metacognition and a
      logical-symbolic language (e.g. a typical adult human, a sufficiently
      reflective artificial agent). Only Type II agents can bear duties.
    """

    TYPE_I = "TYPE_I"
    TYPE_II = "TYPE_II"


class ConsentStatus(StrEnum):
    """Whether the affected agents consented to the action under evaluation."""

    GIVEN = "GIVEN"
    REFUSED = "REFUSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class Verdict(StrEnum):
    """The possible top-level conclusions of an ethical evaluation.

    Ordered, loosely, from most permissible to least permissible, with
    ``INSUFFICIENT_DATA`` standing apart as an explicit refusal to judge.
    """

    ACCEPTABLE = "ACCEPTABLE"
    ACCEPTABLE_WITH_RESERVATIONS = "ACCEPTABLE_WITH_RESERVATIONS"
    ETHICALLY_SUSPICIOUS = "ETHICALLY_SUSPICIOUS"
    NOT_ACCEPTABLE = "NOT_ACCEPTABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class UncertaintyLevel(StrEnum):
    """A coarse, human-readable summary of how much LittleBoy trusts its inputs."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
