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

from littleboy.core.models import CoercionJustification, MoralAgent


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
            "alternative; (c) it is necessary to obtain lower total coercion in the "
            "system; (d) it is proportional; (e) it stops once the original coercion "
            "has been neutralized."
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


def agent_can_bear_duties(agent: MoralAgent | None) -> bool:
    """Axiom 4: only Type II agents can be bound by duties.

    A ``None`` agent (unknown) is treated as *not* duty-bearing for the purpose
    of assigning obligations -- we do not assign duties to an agent we cannot
    even classify.
    """
    return bool(agent and agent.can_bear_duties)


@dataclass(frozen=True)
class JustificationResult:
    """The outcome of checking a :class:`CoercionJustification` against Axiom 3."""

    justified: bool
    satisfied_conditions: list[str]
    failed_conditions: list[str]

    @property
    def axiom_id(self) -> str:
        return "A3"


# Human-readable labels for each Axiom 3 condition, in canonical order.
_A3_CONDITIONS: tuple[tuple[str, str], ...] = (
    ("responds_to_existing_coercion", "responds to existing or imminent coercion"),
    ("no_less_coercive_alternative", "no less coercive alternative is available"),
    ("necessary_for_lower_total_coercion", "necessary to obtain lower total coercion"),
    ("proportional", "the coercion is proportional"),
    ("stops_when_neutralized", "the coercion stops once the original is neutralized"),
)


def check_coercion_justification(
    justification: CoercionJustification | None,
) -> JustificationResult:
    """Apply Axiom 3 to a justification claim.

    Coercion is justified only if *every* condition is satisfied. If no
    justification is offered at all, the result is "not justified" with every
    condition recorded as unmet -- silence is not a justification.
    """
    if justification is None:
        return JustificationResult(
            justified=False,
            satisfied_conditions=[],
            failed_conditions=[label for _, label in _A3_CONDITIONS],
        )

    satisfied: list[str] = []
    failed: list[str] = []
    for field_name, label in _A3_CONDITIONS:
        if getattr(justification, field_name):
            satisfied.append(label)
        else:
            failed.append(label)

    return JustificationResult(
        justified=not failed,
        satisfied_conditions=satisfied,
        failed_conditions=failed,
    )
