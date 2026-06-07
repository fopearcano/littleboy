# LittleBoy rule engine (v0.3)

In v0.3 LittleBoy stops being only a scoring system and becomes a transparent
**reasoning machine**: every verdict is traceable to explicit, named rules, the
axioms they invoke, the policy thresholds they read, the evidence they use, and
the confidence adjustments they make.

## What a rule is

A **rule** (`littleboy.rules.base.Rule`) is a small, named, self-explaining unit
of ethical reasoning. It examines a `RuleContext` — the case plus everything
LittleBoy has already computed about it (coercion score, epistemic basis,
consent and agency assessments, justification result, alternative analysis) —
and returns a `RuleResult` that records:

- `status`: `passed` / `failed` / `unknown` / `not_applicable`;
- `severity`: `info` / `warning` / `downgrade` / `blocker` / `contradiction`;
- `message`: a plain-language explanation;
- `axioms_invoked`: which axioms the rule rests on;
- `evidence_used`, `missing_data`: what it relied on and what it lacked;
- `confidence_delta`: how it moves confidence;
- `verdict_delta` / `verdict_cap`: how it moves the verdict.

Rules never mutate state and never read global configuration. That makes each
rule individually testable and the whole engine auditable.

## How rules relate to axioms

Rules are the *operationalisation* of the axioms. The axioms (see
`docs/ETHICAL_MODEL.md`) state the norms; each rule applies one strand of a norm
to messy, uncertain data and cites the axiom(s) it serves. For example
LB-R007 (Justified Coercion) is the operational form of Axiom 3; LB-R004 /
LB-R010 serve Axiom 5 (no false certainty); LB-R006 serves Axiom 2.

| Rule | Name | Axioms |
|------|------|--------|
| LB-R001 | Type II Duty Rule | A1, A4 |
| LB-R002 | Coercion Detection Rule | A0, A2 |
| LB-R003 | Consent Rule | A0, A2 |
| LB-R004 | Data Quality Rule | A5 |
| LB-R005 | Evidence Quality Rule | A5 |
| LB-R006 | Less-Coercive Alternative Rule | A2 |
| LB-R007 | Justified Coercion Rule | A2, A3 |
| LB-R008 | Vulnerability Protection Rule | A0, A2 |
| LB-R009 | Informational Manipulation Rule | A0, A2 |
| LB-R010 | Irreversibility Rule | A5 |
| LB-R011 | Cessation Rule | A3 |
| LB-R012 | Contradiction Rule | A1, A3 |

## The registry

`RuleRegistry` is an ordinary, testable object — no global magic. You register
rules on it, list them in a stable order (sorted by `rule_id`), and evaluate
them all against a context. Rules can be disabled (e.g. by a policy) without
removing them; disabled rules are reported as *skipped*. `default_registry()`
returns a registry populated with all twelve built-in rules.

## How the verdict is synthesized

The `RuleEngine` runs the registry and then **synthesizes** a verdict
deterministically:

1. **Base verdict** from the bare scores: `ACCEPTABLE` only when coercion is low,
   the epistemic basis is good, and there are no outstanding unknowns; otherwise
   `ACCEPTABLE_WITH_RESERVATIONS`.
2. **Insufficiency is absorbing** (Axiom 5): any rule that caps the verdict at
   `INSUFFICIENT_DATA` (e.g. weak data, or an irreversible act on weak evidence),
   or a final confidence below the policy minimum, yields `INSUFFICIENT_DATA`.
3. **Caps**: each blocking rule contributes a `verdict_cap`; the least permissive
   cap wins (e.g. LB-R007 caps at `NOT_ACCEPTABLE` when justification is absent
   or false).
4. **Downgrades**: each `downgrade` rule contributes `verdict_delta` notches
   (e.g. a feasible less-coercive alternative pulls the verdict down).
5. **Contradictions** cap the verdict at `ETHICALLY_SUSPICIOUS` and are surfaced
   for review.

## How confidence is modified

Confidence starts as the **base confidence** (the epistemic basis reduced for
each structural unknown). Each rule may then apply a `confidence_delta`
(e.g. disputed consent, high vulnerability, or weak/contested evidence lower it).
The sum is clamped to `[0, 1]`. Every adjustment is listed in the trace's
`confidence_adjustments`, so a reader can see exactly which rule moved confidence
and by how much.

## How contradictions are detected

LB-R012 inspects the case for mutually incompatible claims, e.g.:

- the justification asserts *no less coercive alternative is available*, yet a
  feasible less-coercive alternative is supplied;
- the case says the action does *not* respond to prior coercion, yet the
  justification claims it does;
- consent is reported as `GIVEN` but its voluntariness is `DISPUTED`.

A contradiction does not silently change the score; it is flagged, caps the
verdict at suspicious, and is listed in `reasoning_trace.contradictions` for a
human to resolve.

## The reasoning trace

Every `EvaluationReport` carries a `reasoning_trace` (`ReasoningTrace`) with:
`applied` (every rule result), `skipped`, `failed`, `unknown`, `blockers`,
`contradictions`, `missing_data`, `confidence_adjustments`, `base_confidence`,
`final_confidence`, `final_verdict`, and `policy_mode`. This is the record that
lets anyone reconstruct *why* the verdict happened.

## Why uncertainty is exposed, not hidden

A rule that does not know returns `unknown`, not a guess. Unknown conditions
withhold confident approval rather than being silently treated as either true or
false. This is Axiom 5 enforced mechanically: producing a confident verdict from
poor information is itself an ethical failure, so LittleBoy reports the gap and
the questions that would close it.
