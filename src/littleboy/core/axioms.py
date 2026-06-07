"""The LittleBoy axioms, as data and as code-level rules.

The whole engine rests on a single normative commitment:

    The fundamental ethical evil is coercion.
    The ethical good is the minimization or absence of coercion.

From that commitment the following axioms are derived. They are represented
here both as human-readable statements (so a report can cite them verbatim) and
as small, testable functions (so the evaluator can apply them).

An *ethical truth* in LittleBoy is a proposition logically derived from the
*current* axioms; the axioms are therefore the single point of change for the
system's normative behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

from littleboy.core.enums import AgentType, EpistemicStatus
from littleboy.core.models import (
    CoercionJustification,
    JustificationResult,
    MoralAgent,
)


@dataclass(frozen=True)
class Axiom:
    """A normative proposition placed at the foundation of ethical deduction."""

    id: str
    title: str
    statement: str

    def cite(self) -> str:
        """Render the axiom as a single citable line, e.g. for a report."""
        return f"{self.id}: {self.statement}"


# The foundational axiom, kept separate because everything else derives from it.
FOUNDATION = Axiom(
    id="A0",
    title="Foundational axiom",
    statement=(
        "The fundamental ethical evil is coercion; the ethical good is the "
        "minimization or absence of coercion."
    ),
)

AXIOMS: tuple[Axiom, ...] = (
    Axiom(
        id="A1",
        title="Duty to interrogate",
        statement=("Type II moral agents must interrogate the ethical status of their actions."),
    ),
    Axiom(
        id="A2",
        title="Minimization of coercion",
        statement=(
            "Type II moral agents should act so that the world contains the least "
            "possible coercion, whether exercised by them or suffered by them."
        ),
    ),
    Axiom(
        id="A3",
        title="Conditions for justified coercion",
        statement=(
            "Coercion is ethically justified only if ALL hold: (a) it responds to "
            "existing or imminent coercion; (b) there is no less coercive available "
            "alternative; (c) it is necessary; (d) it is proportional; (e) it plausibly "
            "reduces total coercion; (f) it has a defined cessation condition and stops "
            "once the original coercion has been neutralized."
        ),
    ),
    Axiom(
        id="A4",
        title="Duties bind only Type II agents",
        statement="Duties bind only Type II agents.",
    ),
    Axiom(
        id="A5",
        title="No false certainty",
        statement=(
            "If data are insufficient, LittleBoy must not pretend certainty. It must "
            "return a judgment with uncertainty, missing data, and required clarifications."
        ),
    ),
)

# Index by id for convenient lookup when building reports.
AXIOMS_BY_ID: dict[str, Axiom] = {FOUNDATION.id: FOUNDATION, **{a.id: a for a in AXIOMS}}


def cite(axiom_id: str) -> str:
    """Return the citable one-line form of an axiom by id (e.g. ``cite("A3")``)."""
    return AXIOMS_BY_ID[axiom_id].cite()


# =============================================================================
# Axiom 4: duty-bearing
# =============================================================================


def agent_can_bear_duties(agent: MoralAgent | None) -> bool:
    """Axiom 4: only Type II agents can be bound by duties.

    A ``None`` agent (unknown) is treated as *not* duty-bearing for the purpose
    of assigning obligations -- we do not assign duties to an agent we cannot
    even classify.
    """
    return bool(agent and agent.can_bear_duties)


def agent_type_can_bear_duties(agent_type: AgentType | None) -> bool:
    """Axiom 4 at the level of a bare type (None = unknown = not duty-bearing)."""
    return agent_type == AgentType.TYPE_II


# =============================================================================
# Axiom 3: conditions for justified coercion
# =============================================================================

# The status-bearing conditions of Axiom 3, in canonical order, with labels.
_STATUS_CONDITIONS: tuple[tuple[str, str], ...] = (
    ("responds_to_existing_or_imminent_coercion", "responds to existing or imminent coercion"),
    ("no_less_coercive_alternative_available", "no less coercive alternative is available"),
    ("necessity", "the coercion is necessary"),
    ("proportionality", "the coercion is proportional"),
    ("cessation_condition_defined", "a cessation condition is defined"),
)

_REDUCTION_LABEL = "it plausibly reduces total coercion"
_REVERSIBILITY_LABEL = "the coercion is reversible"


def evaluate_coercion_justification(
    justification: CoercionJustification | None,
) -> JustificationResult:
    """Apply Axiom 3 to a justification claim, honestly tracking the unknown.

    Returns a tri-state result: justified (every condition affirmatively
    established), not justified (a condition is refuted), or unknown (a condition
    is simply not known). Reversibility is treated as a soft factor: it lowers
    confidence and raises a warning when not established, but does not by itself
    defeat an otherwise-complete justification.
    """
    if justification is None:
        unknown = [label for _, label in _STATUS_CONDITIONS] + [_REDUCTION_LABEL]
        return JustificationResult(
            is_justified=None,
            confidence=0.0,
            unknown_conditions=unknown,
            warnings=["no coercion justification was provided"],
        )

    satisfied: list[str] = []
    failed: list[str] = []
    unknown: list[str] = []
    warnings: list[str] = []
    weights: list[float] = []

    # Status-bearing core conditions.
    for field_name, label in _STATUS_CONDITIONS:
        status: EpistemicStatus = getattr(justification, field_name)
        weights.append(status.confidence_weight)
        if status.is_affirmative:
            satisfied.append(label)
        elif status == EpistemicStatus.DISPUTED:
            failed.append(f"{label} (disputed)")
            warnings.append(f"condition disputed: {label}")
        else:
            unknown.append(label)

    # Numeric condition: net reduction in total coercion.
    reduction = justification.expected_total_coercion_reduction
    if reduction is None:
        unknown.append(_REDUCTION_LABEL)
        weights.append(0.0)
    elif reduction > 0.0:
        satisfied.append(_REDUCTION_LABEL)
        weights.append(min(1.0, reduction))
    else:
        failed.append(f"{_REDUCTION_LABEL} (estimated reduction <= 0)")
        weights.append(0.0)

    # Reversibility: a soft factor, not a hard gate.
    rev = justification.reversibility
    weights.append(rev.confidence_weight)
    if rev.is_affirmative:
        satisfied.append(_REVERSIBILITY_LABEL)
    elif rev == EpistemicStatus.DISPUTED:
        warnings.append("reversibility of the coercion is disputed")
    else:
        warnings.append("reversibility of the coercion is not established")

    # Tri-state verdict from the *core* conditions (status + reduction).
    if failed:
        is_justified: bool | None = False
    elif unknown:
        is_justified = None
        warnings.append("justification incomplete: some conditions are unknown")
    else:
        is_justified = True

    confidence = sum(weights) / len(weights) if weights else 0.0

    return JustificationResult(
        is_justified=is_justified,
        confidence=round(confidence, 4),
        satisfied_conditions=satisfied,
        failed_conditions=failed,
        unknown_conditions=unknown,
        warnings=warnings,
    )
