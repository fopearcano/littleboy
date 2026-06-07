# LittleBoy case builder (v0.4)

LittleBoy should not only *judge* finished cases; it should help *construct* a
morally evaluable one. The case builder inspects a partial
:class:`ActionCase`, works out what is missing, and asks precise, prioritised
questions — so that a moral verdict is never produced prematurely under weak
data (Axiom 5).

## Why LittleBoy asks questions before judging

The foundational risk for any ethical engine is **confident judgment on thin
information**. LittleBoy treats that as itself an ethical failure (Axiom 5). So
before (or alongside) evaluating, it answers three questions:

1. *Can this case be judged at all?* — some facts are prerequisites (who is
   affected, whether coercion is even present, whether there is any evidential
   basis). Without them, evaluation is blocked.
2. *Can it be judged confidently?* — other gaps (unknown consent, un-analysed
   alternatives under real coercion) do not block a verdict but block a
   *confident, approving* one.
3. *What should be asked next?* — every gap becomes a concrete question that
   explains why it matters and which axiom it serves.

The builder **never invents facts**. It only asks for them.

## How missing data affects the judgment

| Missing fact | Effect |
|--------------|--------|
| Affected agents | **Blocks** evaluation — coercion is suffered by someone; we must know who. |
| Coercion profile | **Blocks** — coercion is the central quantity. |
| Any evidential basis (data quality / evidence) | **Blocks** — no basis to judge (Axiom 5). |
| Acting agent type | Lowers confidence (duties bind only Type II — Axiom 4). |
| Consent (when relevant) | Blocks *confident approval*; critical under high vulnerability. |
| Alternatives, under moderate/high coercion | Blocks *confident approval* (Axiom 2). |
| Justification, under high coercion | Case can proceed only as suspicious / not acceptable (Axiom 3). |
| Reversibility, under weak evidence | Warns; irreversible + weak data → treat as insufficient. |

These are realised both as **questions** (prioritised `CRITICAL` / `HIGH` /
`MEDIUM` / `LOW`) and as **warnings** in the completeness report.

## The completeness report

`CaseCompletenessReport` carries: `completeness_score` (a transparent 0–1
heuristic), `can_evaluate`, `can_confidently_evaluate`, the
`critical_/high_priority_/optional_missing_fields`, the
`recommended_next_questions`, and `warnings`. Every `EvaluationReport` also
includes this report (and `recommended_questions`) so a verdict always travels
with an honest account of what it rests on.

## CLI: `questions`

Print what a (possibly partial) case is missing and what to ask next:

```bash
littleboy questions examples/partial_generic_case.json                  # readable text
littleboy questions examples/partial_medical_case.json --template medical_decision
littleboy questions examples/partial_emergency_case.json --format json  # machine-readable
littleboy questions examples/partial_generic_case.json --policy strict  # stricter thresholds
```

Each question is shown with its priority, category, the axioms it serves, whether
it blocks evaluation, and **why it matters**.

## CLI: `build-case` (interactive wizard)

Construct a case by answering prompts (press Enter to skip any):

```bash
littleboy build-case
littleboy build-case --template medical_decision
littleboy build-case --template speech_or_language_manipulation --output examples/my_case.json
littleboy build-case --no-evaluate          # build + completeness only
```

The wizard asks for the title, description, acting/affected agents, consent, a
small set of template-relevant coercion dimensions, reversibility, alternatives,
and an overall information-reliability figure; writes an `ActionCase` JSON (with
`--output`); shows the completeness report; and, if enough data exist, evaluates
the case.

## Programmatic use

```python
from littleboy import ActionCase, CaseBuilder

builder = CaseBuilder(policy_mode="standard")
case = ActionCase(title="A partially-specified action")

questions = builder.generate_questions(case, template="medical_decision")
report = builder.completeness_report(case)

print(report.completeness_score, report.can_evaluate)
for q in report.recommended_next_questions:
    print(q.priority, q.text, "->", q.why_it_matters)

# Apply a simple answer (only the unambiguous fields are supported):
case = builder.apply_answer(case, "Q-CONSENT", "GIVEN")
```

## Limits of the system

- **`apply_answer` is deliberately minimal.** It fills only simple, unambiguous
  fields (description, acting-agent type, consent, coercion source, expected
  consequences). Complex structures (the full coercion profile, evidence,
  alternatives, justification, agency/consent profiles) must be supplied
  directly in JSON — the builder will not guess them.
- **The wizard captures a coarse case.** It collects one affected agent, a small
  set of coercion dimensions, and a single information-reliability figure. It is
  a starting point, not a substitute for a carefully authored case file.
- **The completeness score is a transparent heuristic**, not a measure of moral
  certainty. A high score means "few important gaps", not "the verdict is right".
- LittleBoy remains **not a legal, medical, or emergency decision-maker**.
