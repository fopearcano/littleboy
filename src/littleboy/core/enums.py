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


class EpistemicStatus(StrEnum):
    """The epistemic standing of a single proposition.

    LittleBoy must never confuse *true*, *false*, *unknown*, *disputed*, and
    *insufficiently evidenced*. A reasoning engine that collapses these into a
    boolean will silently manufacture certainty. This enum keeps them distinct.

    - ``CONFIRMED``: well-supported as true.
    - ``LIKELY``: probably true, but not established.
    - ``UNKNOWN``: simply not known either way.
    - ``DISPUTED``: actively contested by the available information.
    - ``INSUFFICIENT_EVIDENCE``: too little evidence to take any position.
    """

    CONFIRMED = "CONFIRMED"
    LIKELY = "LIKELY"
    UNKNOWN = "UNKNOWN"
    DISPUTED = "DISPUTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

    @property
    def is_affirmative(self) -> bool:
        """True if the proposition can be treated as holding (confirmed/likely)."""
        return self in (EpistemicStatus.CONFIRMED, EpistemicStatus.LIKELY)

    @property
    def is_unresolved(self) -> bool:
        """True if we genuinely do not know (unknown / insufficient evidence)."""
        return self in (
            EpistemicStatus.UNKNOWN,
            EpistemicStatus.INSUFFICIENT_EVIDENCE,
        )

    @property
    def confidence_weight(self) -> float:
        """A 0..1 weight expressing how much this status supports a conclusion."""
        return {
            EpistemicStatus.CONFIRMED: 1.0,
            EpistemicStatus.LIKELY: 0.7,
            EpistemicStatus.DISPUTED: 0.3,
            EpistemicStatus.UNKNOWN: 0.0,
            EpistemicStatus.INSUFFICIENT_EVIDENCE: 0.0,
        }[self]


class SourceType(StrEnum):
    """Where a piece of evidence comes from. Drives an evidence-reliability prior."""

    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    DOCUMENT = "DOCUMENT"
    EXPERT_REPORT = "EXPERT_REPORT"
    LEGAL_SOURCE = "LEGAL_SOURCE"
    MEDICAL_SOURCE = "MEDICAL_SOURCE"
    TESTIMONY = "TESTIMONY"
    USER_STATEMENT = "USER_STATEMENT"
    UNKNOWN = "UNKNOWN"


class ConsentStatus(StrEnum):
    """Whether (and how) the affected agents consented to the action.

    Extended in v0.2 with ``COERCED`` and ``DISPUTED``: consent extracted under
    coercion is not valid consent, and contested consent must block confident
    approval.
    """

    GIVEN = "GIVEN"
    REFUSED = "REFUSED"
    COERCED = "COERCED"
    DISPUTED = "DISPUTED"
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
