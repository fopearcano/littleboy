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


class RuleSeverity(StrEnum):
    """How forcefully a rule's finding bears on the verdict.

    - ``INFO``: informational only.
    - ``WARNING``: surfaced to the user, may lower confidence.
    - ``DOWNGRADE``: pulls the verdict toward less permissible.
    - ``BLOCKER``: caps the verdict (e.g. NOT_ACCEPTABLE or INSUFFICIENT_DATA).
    - ``CONTRADICTION``: the case asserts mutually incompatible things.
    """

    INFO = "info"
    WARNING = "warning"
    DOWNGRADE = "downgrade"
    BLOCKER = "blocker"
    CONTRADICTION = "contradiction"


class RuleResultStatus(StrEnum):
    """The outcome of evaluating a single rule against a case."""

    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class PolicyMode(StrEnum):
    """Named strictness profiles. They change operational thresholds, never axioms."""

    PERMISSIVE = "permissive"
    STANDARD = "standard"
    STRICT = "strict"
    PRECAUTIONARY = "precautionary"


class QuestionPriority(StrEnum):
    """How important a missing piece of information is to a sound judgment."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QuestionCategory(StrEnum):
    """The aspect of a case a question is trying to fill in."""

    ACTING_AGENT = "acting_agent"
    AFFECTED_AGENT = "affected_agent"
    ACTION_DESCRIPTION = "action_description"
    CONSENT = "consent"
    COERCION = "coercion"
    JUSTIFICATION = "justification"
    ALTERNATIVES = "alternatives"
    CONSEQUENCES = "consequences"
    REVERSIBILITY = "reversibility"
    VULNERABILITY = "vulnerability"
    EVIDENCE = "evidence"
    DATA_QUALITY = "data_quality"
    CONTEXT = "context"
    LANGUAGE = "language"


class TimeHorizon(StrEnum):
    """When a consequence is expected to occur.

    These are *semantic* horizons, not fixed durations -- different case types
    interpret them differently:

    - ``IMMEDIATE``: the direct consequence of the action;
    - ``SHORT_TERM``: soon after the action;
    - ``MEDIUM_TERM``: consequences emerging after the first effects;
    - ``LONG_TERM``: structural or persistent consequences;
    - ``UNKNOWN``: the horizon is not known.
    """

    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    UNKNOWN = "unknown"


class LanguageMedium(StrEnum):
    """The medium of a language act. Different media carry different duties of clarity."""

    SPEECH = "speech"
    WRITING = "writing"
    CONTRACT = "contract"
    ADVERTISEMENT = "advertisement"
    POLITICAL_MESSAGE = "political_message"
    MEDICAL_CONSENT = "medical_consent"
    LEGAL_NOTICE = "legal_notice"
    INTIMATE_CONVERSATION = "intimate_conversation"
    PUBLIC_STATEMENT = "public_statement"
    EDUCATIONAL = "educational"
    UNKNOWN = "unknown"
