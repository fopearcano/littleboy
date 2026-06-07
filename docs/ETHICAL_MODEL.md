# The LittleBoy ethical model (v0.2)

This document states the formal model LittleBoy currently implements. It is a
working model, not a finished moral theory. It is deliberately explicit so that
its commitments, and its limits, can be inspected and argued with.

## Foundational axiom

> **The fundamental ethical evil is coercion.
> The ethical good is the minimization or absence of coercion.**

Everything below derives from this single commitment (`A0`).

## Moral agents (Type I / Type II)

A **moral agent** is any entity or collective capable of action.

- **Type I** — no symbolic metacognition (an animal, a thermostat, a simple
  automaton). A Type I agent can *cause* and *suffer* coercion, so it matters to
  an evaluation, but it **cannot bear duties**.
- **Type II** — possesses propositional metacognition and a logical-symbolic
  language. Only Type II agents can be **bound by duties** (Axiom 4).

When the agent type is unknown, LittleBoy does not assign duties and lowers its
confidence rather than guessing.

## Coercion

Coercion is modelled along two groups of axes (see `CoercionProfile`):

- **Channels** (the means): physical force, threat, economic pressure,
  psychological pressure, **informational manipulation**, legal constraint,
  social pressure.
- **Aggravating factors** (the seriousness): duration, reversibility, scope
  (number of agents), severity.

The `coercion_score` combines these transparently:
`means_intensity = soft-OR(channels)`, scaled by an aggravation factor.
Informational manipulation is a coercion channel: deceiving someone into a
choice is coercion, **not** "merely bad communication".

The score is a **heuristic**, intended to make cases comparable and drive a
first-pass rule. It is not a measurement and not a moral truth; two acts with
the same score are not thereby morally equivalent.

## Non-coercion

The ethical good is the minimization or absence of coercion (Axiom 2). A Type II
agent should act so the world contains the least coercion, whether exercised by
them or suffered by them. This is why a *feasible* less-coercive alternative
matters so much: if one exists, the more coercive action is, by the axiom, worse.

## Justified coercion (Axiom 3)

Coercion is ethically justified **only if all** of the following hold:

1. it responds to existing or imminent coercion;
2. there is no less coercive available alternative;
3. it is necessary;
4. it is proportional;
5. it plausibly reduces total coercion (a net reduction, not zero or negative);
6. it has a defined cessation condition and stops once the original coercion is
   neutralized.

Crucially, each condition carries an **epistemic status**, not a boolean. The
justification verdict is therefore **tri-state**:

- **justified** — every condition is affirmatively established;
- **not justified** — a condition is refuted (e.g. a non-positive expected
  reduction, or a disputed condition);
- **unknown** — a condition is simply not known.

If the conditions are unknown, LittleBoy must **not** output confident approval.
Reversibility is treated as a soft factor: it lowers confidence and raises a
warning when not established, but does not by itself defeat an otherwise
complete justification.

## Data quality and evidence quality

LittleBoy treats epistemics as an ethical matter (Axiom 5): a confident verdict
built on poor information is itself a failure.

- **Data quality** (`DataQualityProfile`) rates completeness, source reliability,
  specificity, recency, corroboration, ambiguity, and names missing critical
  facts.
- **Evidence quality** (`EvidenceSet`) goes finer: each `EvidenceItem` records a
  claim, its source type, and support axes, from which LittleBoy derives an
  evidence score and surfaces **contested** and **unsupported** claims.

These combine into a single **epistemic basis**, which drives confidence and the
sufficiency gates.

## Consent

Consent is not one bit (`ConsentProfile`). Valid consent is **informed**,
**voluntary**, **specific**, and **revocable**, each with an epistemic status.

- **Coerced** consent is not valid consent (it is itself coercion).
- **Disputed** consent blocks confident approval.
- **Unknown** consent lowers confidence.
- High subject **vulnerability** raises the bar for valid consent and increases
  scrutiny of any coercion.

## Alternatives

Alternatives (`AlternativeAction` / `AlternativeSet`) are compared on coercion
*and feasibility*. A feasible less-coercive alternative downgrades the verdict.
A less-coercive but **infeasible** ("fantasy-level") alternative is recorded but
does **not** defeat the proposed action. If alternatives were never analysed,
LittleBoy says so and withholds confident approval of any coercive action.

## Why uncertainty must be exposed (Axiom 5)

The system never confuses *true*, *false*, *unknown*, *disputed*, and
*insufficiently evidenced*. When data are insufficient — or an action is
irreversible and the evidence is weak — LittleBoy returns `INSUFFICIENT_DATA`
with the missing facts and the questions that would resolve them, instead of
manufacturing a confident answer. Every report exposes its confidence, its
uncertainty level, the axioms invoked, and what it did not know.

## Out of scope

LittleBoy is **not** a legal, medical, or emergency decision-maker, and it does
not claim absolute moral truth. Its scores are heuristics; its verdicts are
provisional and only as good as the inputs and the model above.
