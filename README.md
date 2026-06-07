# LittleBoy

A rational ethical evaluation engine built on a single foundational axiom:

> **The fundamental ethical evil is coercion.
> The ethical good is the minimization or absence of coercion.**

LittleBoy takes a structured description of an action — who acts, who is
affected, the coercion involved, the alternatives considered, and how
trustworthy the information is — and returns a **transparent, explained
verdict**. It is a reasoning engine first, not a user interface and not a
language model.

This repository is an early, deliberately small **foundation**. It is meant to
be clean, typed, and testable, not feature-complete.

---

## The core axiom: evil = coercion

Everything LittleBoy does derives from one normative commitment (`A0`) and five
axioms built on top of it (see `src/littleboy/core/axioms.py`):

| ID  | Axiom |
|-----|-------|
| A0  | The fundamental ethical evil is coercion; the good is its minimization or absence. |
| A1  | Type II moral agents must interrogate the ethical status of their actions. |
| A2  | Type II agents should act so the world contains the least possible coercion, exercised or suffered. |
| A3  | Coercion is justified **only if all** of: it responds to existing/imminent coercion; no less coercive alternative exists; it is necessary for lower total coercion; it is proportional; and it stops once the original coercion is neutralized. |
| A4  | Duties bind **only Type II agents**. |
| A5  | If data are insufficient, LittleBoy must not pretend certainty; it must report uncertainty, missing data, and required clarifications. |

### Moral agents

- **Type I** — an entity *without* symbolic metacognition (e.g. an animal, a
  simple automaton). It can cause or suffer coercion, but it **cannot be bound
  by duties** (A4).
- **Type II** — an entity *with* propositional metacognition and a
  logical-symbolic language. Only Type II agents bear duties.

### Coercion is scored as a transparent heuristic

A `CoercionProfile` describes coercion along several axes: seven *channels*
(physical force, threat, economic pressure, psychological pressure,
informational manipulation, legal constraint, social pressure) and four
*aggravating factors* (duration, reversibility, scope, severity). These feed a
`coercion_score` in `[0, 1]`.

**The score is a heuristic, not a moral measurement.** It exists to make cases
comparable and to drive a first-pass decision rule. The full derivation is
returned with every report, so the number is never a black box.

---

## Why LittleBoy considers data quality

A confident-looking verdict built on poor information is itself an ethical
failure (A5). LittleBoy therefore treats epistemics as first-class:

- A `DataQualityProfile` rates completeness, source reliability, specificity,
  recency, corroboration, ambiguity, and lists any missing critical facts.
- These produce a `data_quality_score` and an `uncertainty_level`.
- Confidence is reduced for each **structural unknown** in the case:
  unknown consent, unknown agent type, un-analysed alternatives, unknown
  coercion source, unknown consequences, and unknown reversibility.
- When data are too thin, the verdict is `INSUFFICIENT_DATA` — LittleBoy
  declines to feign certainty rather than guessing.

The distinction between *"absent"* (a present-but-low value) and *"unknown"*
(`null`) is meaningful and preserved throughout.

---

## ⚠️ Scope and limitations

**LittleBoy is not a legal, medical, or emergency decision-maker.** It produces
a transparent heuristic judgment, not absolute moral truth. Do not use it to
make real consequential decisions about real people. Every report carries this
disclaimer, exposes the axioms it invoked, and lists what it did not know.

---

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `ACCEPTABLE` | Low coercion, good data, no outstanding unknowns. |
| `ACCEPTABLE_WITH_RESERVATIONS` | Permissible but with residual uncertainty or caveats. |
| `ETHICALLY_SUSPICIOUS` | Coercion is non-trivial and key checks (e.g. alternatives) are unmet. |
| `NOT_ACCEPTABLE` | High coercion without a complete A3 justification. |
| `INSUFFICIENT_DATA` | Not enough trustworthy information to judge (A5). |

---

## Project layout

```text
src/littleboy/
  core/
    enums.py       # AgentType, Verdict, ConsentStatus, UncertaintyLevel
    models.py      # MoralAgent, CoercionProfile, DataQualityProfile, ActionCase, EvaluationReport
    axioms.py      # the axioms (as data) + Axiom 3 justification checking + duty rule
    scoring.py     # transparent coercion-score heuristic
    evaluator.py   # EthicalEvaluator: the decision logic
  data/
    quality.py     # data-quality scoring, confidence, uncertainty
  reasoning/
    report.py      # JSON / text rendering of a report
  cli.py           # `littleboy evaluate <case.json>`
tests/             # pytest suite
examples/          # sample JSON cases
```

---

## Installation

Requires **Python 3.11+**. Pydantic v2 is the only runtime dependency; Typer is
needed only for the CLI.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # installs pydantic, pytest, typer, ruff
```

## Running the tests

```bash
pytest                      # 34 tests
ruff check src tests        # lint (optional)
```

The suite covers, among other things: Type I agents are never assigned duties;
Type II agents can be evaluated; high coercion with poor data is never
confidently approved; high coercion without alternative analysis is rejected or
flagged; low coercion with good data is cautiously positive; missing consent is
reported; and informational manipulation contributes to the coercion score.

## Using the CLI

```bash
littleboy evaluate examples/simple_case.json            # JSON output
littleboy evaluate examples/high_coercion_case.json -f text
littleboy version
```

## Using the library

```python
from littleboy import (
    ActionCase, AgentType, CoercionProfile, ConsentStatus,
    DataQualityProfile, EthicalEvaluator, MoralAgent,
)

case = ActionCase(
    title="Optional after-hours workshop",
    acting_agent=MoralAgent(name="Manager", agent_type=AgentType.TYPE_II),
    coercion_profile=CoercionProfile(social_pressure=0.1, reversibility=1.0, severity=0.05),
    available_alternatives=[],
    data_quality=DataQualityProfile(completeness=0.9, source_reliability=0.9, ambiguity=0.1),
    consent=ConsentStatus.GIVEN,
    responds_to_existing_coercion=False,
    expected_consequences="Skills gained; no penalty for declining.",
)

report = EthicalEvaluator().evaluate(case)
print(report.verdict, report.confidence)
```

---

## Example: input and output

**Input** (`examples/simple_case.json`, abridged):

```json
{
  "title": "Optional after-hours workshop invitation",
  "acting_agent": { "name": "Team manager", "agent_type": "TYPE_II" },
  "coercion_profile": {
    "social_pressure": 0.1, "duration": 0.05, "reversibility": 1.0,
    "scope_number_of_agents": 8, "severity": 0.05
  },
  "available_alternatives": [],
  "data_quality": {
    "completeness": 0.9, "source_reliability": 0.9, "specificity": 0.85,
    "recency": 0.9, "corroboration": 0.8, "ambiguity": 0.1
  },
  "consent": "GIVEN",
  "responds_to_existing_coercion": false,
  "expected_consequences": "Some employees gain new skills; no one is penalised."
}
```

**Output** (`littleboy evaluate examples/simple_case.json`, abridged):

```json
{
  "verdict": "ACCEPTABLE",
  "coercion_score": 0.11,
  "data_quality_score": 0.78,
  "confidence": 0.78,
  "uncertainty_level": "LOW",
  "main_reasons": [
    "Acting agent 'Team manager' is Type II and can bear moral duties (A4).",
    "Coercion is low (0.11) and data quality is good (0.78) with no outstanding unknowns."
  ],
  "coercion_reasoning": [
    "coercion_score is a transparent heuristic, not an absolute moral truth",
    "coercion channels present: social pressure (0.10)",
    "score = min(1, means_intensity * (1 + aggravation)) = min(1, 0.10 * 1.10) = 0.11"
  ],
  "axioms_invoked": ["A0: ...", "A1: ...", "A4: ...", "A2: ..."],
  "missing_data": [],
  "warnings": [
    "LittleBoy produces a transparent heuristic judgment, not absolute moral truth. It is NOT a legal, medical, or emergency decision-maker."
  ]
}
```

A high-coercion case (`examples/high_coercion_case.json`) returns
`NOT_ACCEPTABLE`; a thin, ambiguous case (`examples/insufficient_data_case.json`)
returns `INSUFFICIENT_DATA` with every missing fact enumerated.

---

## Current development status

**v0.1.0 — first foundation.** Implemented:

- Typed Pydantic v2 models for agents, coercion, data quality, cases, reports.
- The five axioms as data plus an Axiom 3 justification checker.
- A transparent coercion-scoring heuristic.
- Data-quality scoring, confidence, and uncertainty handling.
- A first `EthicalEvaluator` with a legible, ordered decision rule.
- A minimal CLI and a 34-test pytest suite.

**Deliberately *not* built yet:** any web UI, any LLM/API integration, any claim
to absolute moral truth, and any heavy frameworks. The coercion and data-quality
scores are first-pass heuristics intended to be refined.

### Possible next steps

- Strengthen the coercion model (per-channel weighting, calibration against
  worked cases, sensitivity analysis).
- Model *ethical experiments* (falsificatory + heuristic simulations) as a
  first-class construct for stress-testing axioms and derived truths.
- Represent "ethical truths" as explicitly derived, queryable propositions.
- Add a case library and golden-file regression tests.
- Explore an optional explanation layer — kept strictly separate from the
  deterministic core, and never the source of the verdict.

---

## License

MIT.
