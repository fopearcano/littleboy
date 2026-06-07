# LittleBoy

A rational ethical evaluation engine built on a single foundational axiom:

> **The fundamental ethical evil is coercion.
> The ethical good is the minimization or absence of coercion.**

LittleBoy takes a structured description of an action — who acts, who is
affected, the coercion involved, the consent, the evidence, the alternatives —
and returns a **transparent, explained verdict** with an honest account of its
own uncertainty. It is a reasoning engine, not a user interface and not a
language model.

This is **v0.2**, a foundation focused on rigour and auditability. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/ETHICAL_MODEL.md`](docs/ETHICAL_MODEL.md) for the full design and formal
model.

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
  reasoning/
    report.py       # JSON / text rendering
    experiment.py   # EthicalExperiment runner (falsificatory + heuristic)
  cli.py            # littleboy evaluate / experiment / version
tests/              # pytest suite
examples/           # sample JSON cases
docs/               # ARCHITECTURE.md, ETHICAL_MODEL.md
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
pytest                      # 63 tests
ruff check src tests        # lint (optional)
```

## CLI usage

```bash
littleboy evaluate examples/high_coercion_missing_consent.json          # JSON (default)
littleboy evaluate examples/manipulative_language_case.json --format text
littleboy experiment examples/high_coercion_missing_consent.json        # falsificatory + heuristic
littleboy version
```

Malformed input fails gracefully with an explanation and a non-zero exit code.

## Example cases

| File | Demonstrates | Verdict |
|------|--------------|---------|
| `examples/low_coercion_good_data.json` | Consented, low-coercion, well-evidenced action | `ACCEPTABLE` |
| `examples/high_coercion_missing_consent.json` | Missing consent + weak data + vulnerable users | `INSUFFICIENT_DATA` |
| `examples/justified_emergency_coercion.json` | Temporary, justified defensive coercion (Axiom 3) | `ACCEPTABLE_WITH_RESERVATIONS` |
| `examples/manipulative_language_case.json` | Informational/linguistic coercion (dark patterns) | `NOT_ACCEPTABLE` |

(The v0.1 examples `simple_case.json`, `high_coercion_case.json`, and
`insufficient_data_case.json` remain valid.)

### Example output (abridged)

`littleboy evaluate examples/manipulative_language_case.json --format text`:

```text
VERDICT: NOT_ACCEPTABLE
  coercion=1.00  data_quality=0.62  evidence=0.42  confidence=0.31  uncertainty=HIGH

Verdict: NOT_ACCEPTABLE (coercion 1.00, confidence 0.31, uncertainty HIGH).
Primary basis: Coercion is high (1.00) and no Axiom 3 justification was supplied.

Consent: DISPUTED (informed=DISPUTED, voluntary=DISPUTED, specific=UNKNOWN, revocable=LIKELY)
Agency:  TYPE_II (capacity_confidence=0.70, vulnerability=0.00)

Coercion reasoning:
  - coercion channels present: informational manipulation (0.80), economic pressure (0.50), ...
  - score = min(1, means_intensity * (1 + aggravation)) = min(1, 0.94 * 1.57) = 1.00

Evidence reasoning:
  - 2 item(s); average reliability = 0.70
  - overall_evidence_score = 0.42
  - contested claim(s): Wording was A/B tested to maximise accidental sign-ups
```

The JSON form (default) is the machine-readable report and includes every field:
verdict, scores, confidence, consent/agency status, justification result,
alternatives analysis, missing data, warnings, axioms invoked, the ethical
experiment summary, and a plain-language explanation.

## Using the library

```python
from littleboy import ActionCase, EthicalEvaluator, EthicalExperiment

case = ActionCase.model_validate(... )      # or build with the typed models
report = EthicalEvaluator().evaluate(case)
print(report.verdict, report.confidence)

experiment = EthicalExperiment().run(case)  # contradictions + open questions
print(experiment.recommended_next_questions)
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

**v0.2 — rigour and auditability.** Implemented: explicit epistemic states;
structured evidence; consent and agency models; a tri-state Axiom 3
justification; feasibility-aware alternatives; a critical-data gate; an ethical
experiment runner; an upgraded report with a plain-language explanation; CLI
`evaluate`/`experiment`; and a 63-test suite (all passing).

**Deliberately not built:** any web UI, any LLM/API integration, any claim to
absolute truth, any heavy frameworks.

### Recommended next steps

- Calibrate the coercion / evidence heuristics against a worked case library
  with golden-file regression tests; add per-channel weights with justification.
- Model `EthicalTruth` as explicitly derived, queryable propositions with a
  derivation trace from specific axioms.
- Extend the experiment runner toward multi-action comparison that minimises
  *total system* coercion (Axiom 2 at the system level).

## License

MIT.
