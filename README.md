# LittleBoy

A rational ethical evaluation engine built on a single foundational axiom:

> **The fundamental ethical evil is coercion.
> The ethical good is the minimization or absence of coercion.**

LittleBoy takes a structured description of an action — who acts, who is
affected, the coercion involved, the consent, the evidence, the alternatives —
and returns a **transparent, explained verdict** with an honest account of its
own uncertainty. It is a reasoning engine, not a user interface and not a
language model.

This is **v0.4**, which adds a **scenario builder / case-input wizard**: LittleBoy
now also helps *construct* a morally evaluable case, detecting missing
information and asking precise questions before judging. (v0.3 added the formal,
inspectable **rule engine** and **policy layer**.) See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/ETHICAL_MODEL.md`](docs/ETHICAL_MODEL.md),
[`docs/RULE_ENGINE.md`](docs/RULE_ENGINE.md),
[`docs/POLICY_PROFILES.md`](docs/POLICY_PROFILES.md),
[`docs/CASE_BUILDER.md`](docs/CASE_BUILDER.md), and
[`docs/SCENARIO_TEMPLATES.md`](docs/SCENARIO_TEMPLATES.md) for the full design and
formal model.

---

## The core axiom: evil = coercion

Everything derives from one normative commitment (`A0`) and five axioms built on
it (`src/littleboy/core/axioms.py`):

| ID | Axiom |
|----|-------|
| A0 | The fundamental ethical evil is coercion; the good is its minimization or absence. |
| A1 | Type II moral agents must interrogate the ethical status of their actions. |
| A2 | Type II agents should act so the world contains the least possible coercion, exercised or suffered. |
| A3 | Coercion is justified **only if all** of: it responds to existing/imminent coercion; no less coercive alternative is available; it is necessary; it is proportional; it plausibly reduces total coercion; it has a defined cessation condition. |
| A4 | Duties bind **only Type II agents**. |
| A5 | If data are insufficient, LittleBoy must not pretend certainty; it must report uncertainty, missing data, and required clarifications. |

## What's new in v0.2

- **Explicit epistemic states** (`EpistemicStatus`): the engine never confuses
  *confirmed*, *likely*, *unknown*, *disputed*, and *insufficiently evidenced*.
- **Structured evidence** (`EvidenceItem` / `EvidenceSet`): per-claim sourcing
  with detection of **contested** and **unsupported** claims.
- **Consent and agency models** (`ConsentProfile`, `AgencyProfile`): consent as
  informed/voluntary/specific/revocable; coerced and disputed consent handled;
  vulnerability raises scrutiny.
- **A formal, tri-state coercion justification** (Axiom 3): justified / not
  justified / **unknown**.
- **Feasibility-aware alternative comparison**: a feasible less-coercive option
  downgrades the verdict; a fantasy-level one does not.
- **A critical-data gate** and an **Ethical Experiment runner** that exposes
  whether a case can be judged at all, and what questions remain.

All v0.1 inputs still validate and evaluate identically (back-compatible).

## LittleBoy v0.3: Rule Engine

v0.3 turns LittleBoy from a scoring system into a transparent **reasoning
machine**. The verdict is no longer produced by opaque branching: it is
synthesized from twelve explicit, self-explaining **rules** (LB-R001 .. LB-R012),
evaluated under a chosen **policy profile**, and recorded in a complete
**reasoning trace**.

- **Rules** (`littleboy.rules`): each rule reads a `RuleContext`, cites the
  axioms it serves, and returns a `RuleResult` with a status, a severity
  (`info` / `warning` / `downgrade` / `blocker` / `contradiction`), a
  confidence delta, and a verdict effect. The twelve rules cover duty, coercion
  detection, consent, data quality, evidence quality, less-coercive
  alternatives, justified coercion, vulnerability, informational manipulation,
  irreversibility, cessation, and contradiction.
- **Policy profiles** (`PolicyMode`: `permissive` / `standard` / `strict` /
  `precautionary`) change *operational thresholds*, never the axioms. The
  default is `standard`, which reproduces v0.2 behaviour.
- **Reasoning trace** (`ReasoningTrace`): every report records which rules
  applied, which were skipped, which failed or were unknown, which blocked
  approval, which flagged a contradiction, and every confidence adjustment —
  so a reader can reconstruct exactly *why* the verdict happened.

See [`docs/RULE_ENGINE.md`](docs/RULE_ENGINE.md) and
[`docs/POLICY_PROFILES.md`](docs/POLICY_PROFILES.md).

## LittleBoy v0.4: Scenario Builder

LittleBoy should not only judge finished cases; it should help *build* one. The
case builder (`littleboy.case_builder`) inspects a partial `ActionCase`, detects
what is missing, and asks precise, prioritised **questions** — so that a moral
verdict is never produced prematurely under weak data (Axiom 5).

- **Questions** (`Question` / `QuestionSet`): each is tagged with a category and
  a priority (`critical` / `high` / `medium` / `low`), names the axioms it
  serves, says whether it **blocks evaluation**, and — always — explains
  **why it matters** ethically. Priority is context-sensitive (e.g. unknown
  consent becomes *critical* under high vulnerability).
- **Completeness** (`CaseCompletenessReport`): a 0–1 completeness score,
  `can_evaluate` / `can_confidently_evaluate`, the missing fields by priority,
  the recommended next questions, and warnings. Every `EvaluationReport` now
  carries this report, so a verdict travels with an honest account of its gaps.
- **Templates** (`ScenarioTemplate`): ten reusable case shapes (medical decision,
  language manipulation, emergency intervention, economic pressure, AI/algorithmic
  decision, …) that raise the priority of the categories they emphasise and add
  their own questions. Ethical framing only — no legal or medical claims.
- **CLI**: `littleboy questions <case.json>` (non-interactive) and
  `littleboy build-case` (interactive wizard).

The builder never invents facts; it only asks for them. See
[`docs/CASE_BUILDER.md`](docs/CASE_BUILDER.md) and
[`docs/SCENARIO_TEMPLATES.md`](docs/SCENARIO_TEMPLATES.md).

## How evidence is represented

An `EvidenceSet` holds `EvidenceItem`s, each a `claim` plus its `source_type`
(direct observation, document, expert/legal/medical report, testimony, user
statement, unknown) and support axes (reliability, specificity, recency,
corroboration, `contested`). From these LittleBoy derives an `evidence_score`,
the **weakest** item, and the lists of **contested** and **unsupported** claims.
Evidence and the `DataQualityProfile` blend into one *epistemic basis*.

## How consent is represented

A `ConsentProfile` records a headline `status` (given / refused / **coerced** /
**disputed** / not applicable / unknown) plus the epistemic status of each of
**informed**, **voluntary**, **specific**, **revocable**. Coerced consent is not
valid consent; disputed consent blocks confident approval; unknown consent
lowers confidence.

## How coercion justification works

A `CoercionJustification` carries the Axiom 3 conditions, each as an
`EpistemicStatus` (plus a numeric expected net coercion reduction).
`evaluate_coercion_justification` returns a **tri-state** result —
`is_justified` is `True` (all conditions established), `False` (a condition is
refuted), or `None` (a condition is unknown) — with the satisfied, failed, and
unknown conditions listed. Unknown conditions never yield confident approval.

## How uncertainty affects verdicts

Confidence starts from the epistemic basis and is reduced for each structural
unknown and for named hazards (disputed consent, high vulnerability, contested
evidence). Two gates protect against false certainty (Axiom 5):

- too little trustworthy information → `INSUFFICIENT_DATA`;
- an effectively **irreversible** action on a weak epistemic basis →
  `INSUFFICIENT_DATA`.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `ACCEPTABLE` | Low coercion, good epistemic basis, no outstanding unknowns. |
| `ACCEPTABLE_WITH_RESERVATIONS` | Permissible but with caveats (e.g. a complete Axiom 3 justification for unavoidable coercion). |
| `ETHICALLY_SUSPICIOUS` | Coercion is non-trivial and a key check (alternatives, justification, consent) is unmet. |
| `NOT_ACCEPTABLE` | High coercion without a complete justification. |
| `INSUFFICIENT_DATA` | Not enough trustworthy information to judge (A5). |

---

## Project layout

```text
src/littleboy/
  core/
    enums.py        # AgentType, EpistemicStatus, SourceType, ConsentStatus, Verdict, ...
    models.py       # all Pydantic data structures (input + report)
    axioms.py       # axioms as data; Axiom 3 justification; Axiom 4 duty rule
    scoring.py      # transparent coercion-score heuristic
    agency.py       # consent + agency assessment
    alternatives.py # feasibility-aware alternative comparison
    gates.py        # critical-data gate + recommended next questions
    evaluator.py    # EthicalEvaluator: the decision logic
  data/
    quality.py      # data-quality scoring, epistemic blend, confidence, uncertainty
    evidence.py     # EvidenceItem / EvidenceSet and their scoring
  rules/
    base.py         # Rule base class + RuleContext
    registry.py     # RuleRegistry (register / list / evaluate / enable-disable)
    policy.py       # PolicyProfile + the four built-in policy modes
    builtin_rules.py# LB-R001 .. LB-R012
    engine.py       # RuleEngine: runs rules and synthesizes the verdict
    trace.py        # builds the ReasoningTrace
  case_builder/
    questions.py    # generates prioritised Questions for a partial case
    completeness.py # CaseCompletenessReport (can/should this be judged yet?)
    templates.py    # ScenarioTemplate + the ten built-in templates
    builder.py      # CaseBuilder (the public entry point)
    session.py      # wizard prompts + build_case_from_answers (I/O-free)
  reasoning/
    report.py       # JSON / text rendering
    experiment.py   # EthicalExperiment runner (falsificatory + heuristic)
  cli.py            # littleboy evaluate / experiment / questions / build-case / templates
tests/              # pytest suite
examples/           # sample JSON cases (incl. partial_*.json for the builder)
docs/               # ARCHITECTURE, ETHICAL_MODEL, RULE_ENGINE, POLICY_PROFILES,
                    #   CASE_BUILDER, SCENARIO_TEMPLATES
```

## Installation

Requires **Python 3.11+**. Pydantic v2 is the only runtime dependency; Typer is
needed only for the CLI.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # pydantic, pytest, typer, ruff
```

## Running the tests

```bash
pytest                      # 93 tests
ruff check src tests        # lint (optional)
```

## CLI usage

```bash
littleboy evaluate examples/high_coercion_missing_consent.json            # JSON (default), standard policy
littleboy evaluate examples/policy_strict_case.json --policy strict       # choose a policy
littleboy evaluate examples/manipulative_language_case.json --policy strict --format text
littleboy experiment examples/high_coercion_missing_consent.json          # falsificatory + heuristic
littleboy questions examples/partial_generic_case.json                    # what's missing + questions
littleboy questions examples/partial_medical_case.json --template medical_decision --format json
littleboy build-case --template speech_or_language_manipulation -o my_case.json   # interactive wizard
littleboy templates                                                       # list scenario templates
littleboy version
```

`--policy` accepts `permissive`, `standard` (default), `strict`, or
`precautionary`. Malformed input (or an unknown policy/template) fails gracefully
with an explanation and a non-zero exit code.

## Example cases

| File | Demonstrates | Verdict |
|------|--------------|---------|
| `examples/low_coercion_good_data.json` | Consented, low-coercion, well-evidenced action | `ACCEPTABLE` |
| `examples/high_coercion_missing_consent.json` | Missing consent + weak data + vulnerable users | `INSUFFICIENT_DATA` |
| `examples/justified_emergency_coercion.json` | Temporary, justified defensive coercion (Axiom 3) | `ACCEPTABLE_WITH_RESERVATIONS` |
| `examples/manipulative_language_case.json` | Informational/linguistic coercion (dark patterns) | `NOT_ACCEPTABLE` |

The v0.3 policy examples show how the rule engine and policy layer matter:

| File | Demonstrates |
|------|--------------|
| `examples/policy_permissive_case.json` | `NOT_ACCEPTABLE` under `standard`, `ACCEPTABLE_WITH_RESERVATIONS` under `permissive` |
| `examples/policy_strict_case.json` | unknown consent: permitted-with-reservations under `standard`, blocked (`ETHICALLY_SUSPICIOUS`) under `strict` |
| `examples/contradiction_case.json` | LB-R012 flags a justification that contradicts a supplied alternative |
| `examples/irreversible_low_data_case.json` | LB-R010 blocks: irreversible action on weak evidence → `INSUFFICIENT_DATA` |

The v0.4 **partial** examples intentionally lack critical data, so the case
builder has something to ask about — try them with `littleboy questions`:

| File | Use with |
|------|----------|
| `examples/partial_generic_case.json` | `littleboy questions ...` (base questions) |
| `examples/partial_medical_case.json` | `--template medical_decision` |
| `examples/partial_language_manipulation_case.json` | `--template speech_or_language_manipulation` |
| `examples/partial_emergency_case.json` | `--template emergency_intervention` |

(The v0.1 examples `simple_case.json`, `high_coercion_case.json`, and
`insufficient_data_case.json` remain valid.)

### Example output (abridged)

`littleboy evaluate examples/policy_permissive_case.json --format text`:

```text
VERDICT: NOT_ACCEPTABLE   [policy: standard]
  coercion=0.65  data_quality=0.71  evidence=0.00  confidence=0.71  uncertainty=MODERATE

Applied rules (standard):
  - LB-R001 Type II Duty Rule: passed/info
  - LB-R002 Coercion Detection Rule: failed/blocker
  - LB-R004 Data Quality Rule: passed/info
  - LB-R007 Justified Coercion Rule: failed/blocker
  ...
Blockers:
  - LB-R002
  - LB-R007
```

The JSON form (default) is the machine-readable report and includes every field:
verdict, scores, confidence, `policy_mode`, consent/agency status, justification
result, alternatives analysis, missing data, warnings, axioms invoked, the
ethical experiment summary, a plain-language explanation, and the full
`reasoning_trace`:

```json
{
  "verdict": "NOT_ACCEPTABLE",
  "confidence": 0.71,
  "policy_mode": "standard",
  "reasoning_trace": {
    "applied": [ "...one entry per rule..." ],
    "blockers": ["LB-R002", "LB-R007"],
    "contradictions": [],
    "missing_data": [],
    "confidence_adjustments": []
  }
}
```

## Using the library

```python
from littleboy import ActionCase, EthicalEvaluator, PolicyMode, EthicalExperiment

case = ActionCase.model_validate(... )                  # or build with the typed models
report = EthicalEvaluator(PolicyMode.STRICT).evaluate(case)
print(report.verdict, report.confidence, report.policy_mode)
print(report.reasoning_trace.blockers)                  # which rules blocked approval
for rule in report.reasoning_trace.applied:             # full, auditable trace
    print(rule.rule_id, rule.status, rule.severity, rule.message)

experiment = EthicalExperiment().run(case)              # contradictions + open questions
print(experiment.recommended_next_questions)
```

Build a case and see what it still needs:

```python
from littleboy import ActionCase, CaseBuilder

builder = CaseBuilder(policy_mode="standard")
report = builder.completeness_report(ActionCase(title="A partially-specified action"))
print(report.completeness_score, report.can_evaluate)
for q in report.recommended_next_questions:
    print(q.priority, q.text, "->", q.why_it_matters)
```

---

## ⚠️ Scope and limitations

**LittleBoy is not a legal, medical, or emergency decision-maker.** It produces a
transparent heuristic judgment, not absolute moral truth. The coercion, data-
quality, and evidence scores are uncalibrated first-pass heuristics; the
decision thresholds are hand-set defaults. Every report carries this disclaimer,
exposes the axioms it invoked, and lists what it did not know. Do not use it to
make consequential decisions about real people.

## Current development status

**v0.4 — scenario builder / case-input wizard.** Implemented on top of v0.3: a
`case_builder` package that generates prioritised, self-explaining questions for
a partial case; a `CaseCompletenessReport` (now embedded in every evaluation);
ten scenario templates; a non-interactive `questions` command and an interactive
`build-case` wizard; and a 93-test suite (all passing). Completeness is purely
additive — verdict behaviour is unchanged, and all v0.1–v0.3 inputs remain valid.

Earlier phases delivered the core models; coercion/data-quality/evidence scoring;
consent/agency models; the tri-state Axiom 3 justification; feasibility-aware
alternatives; the critical-data gate; the ethical experiment runner; and the
v0.3 twelve-rule engine with four policy profiles and a full reasoning trace.

**Deliberately not built:** any web UI, any LLM/API integration, any claim to
absolute truth, any heavy frameworks.

### Recommended next steps

- Richer `apply_answer` / wizard coverage for the structured fields (coercion
  profile, evidence, alternatives, justification) so a case can be built end to
  end without hand-editing JSON.
- Calibrate the coercion / evidence heuristics and the policy thresholds against
  a worked case library with golden-file regression tests.
- Model `EthicalTruth` as explicitly derived, queryable propositions with a
  derivation trace from specific axioms and rules.

## License

MIT.
