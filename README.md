# LittleBoy

A rational ethical evaluation engine built on a single foundational axiom:

> **The fundamental ethical evil is coercion.
> The ethical good is the minimization or absence of coercion.**

LittleBoy takes a structured description of an action — who acts, who is
affected, the coercion involved, the consent, the evidence, the alternatives —
and returns a **transparent, explained verdict** with an honest account of its
own uncertainty. It is a reasoning engine, not a user interface and not a
language model.

This is **v0.7**, which adds **Temporal & Consequence Modeling**: LittleBoy now
judges an action *across time* — short-, medium-, and long-term consequences,
delayed and cumulative coercion, reversibility, and the non-neutrality of
inaction — rather than only at the instant it occurs. The guiding thesis: **an
action is ethically unstable if it reduces visible coercion now while creating
hidden, cumulative, irreversible, or delayed coercion later.** (v0.6 added the
comparison engine; v0.5 the language module; v0.4 the scenario builder; v0.3 the
rule engine and policy layer.) See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/ETHICAL_MODEL.md`](docs/ETHICAL_MODEL.md),
[`docs/RULE_ENGINE.md`](docs/RULE_ENGINE.md),
[`docs/POLICY_PROFILES.md`](docs/POLICY_PROFILES.md),
[`docs/CASE_BUILDER.md`](docs/CASE_BUILDER.md),
[`docs/SCENARIO_TEMPLATES.md`](docs/SCENARIO_TEMPLATES.md),
[`docs/LANGUAGE_ETHICS.md`](docs/LANGUAGE_ETHICS.md),
[`docs/LINGUISTIC_COERCION.md`](docs/LINGUISTIC_COERCION.md),
[`docs/COMPARISON_ENGINE.md`](docs/COMPARISON_ENGINE.md),
[`docs/TRADEOFF_ANALYSIS.md`](docs/TRADEOFF_ANALYSIS.md),
[`docs/TEMPORAL_MODEL.md`](docs/TEMPORAL_MODEL.md),
[`docs/CONSEQUENCE_MODELING.md`](docs/CONSEQUENCE_MODELING.md), and
[`docs/CUMULATIVE_COERCION.md`](docs/CUMULATIVE_COERCION.md) for the full design
and formal model.

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

## LittleBoy v0.5: Language & Coercion Module

> **Language is ethically decisive because it can either expand or restrict the
> field in which will, consent, and self-understanding become possible.**

Language is not ethically neutral. It can clarify, liberate, and disclose; or it
can manipulate, obscure, shame, confuse, frame, silence, or replace the subject's
own meaning-field with someone else's. The `littleboy.language` module detects
and evaluates linguistic/informational coercion — deterministically and
transparently, with **no NLP/LLM**.

- **`LanguageAct` / `LanguageContext` / `LanguageEthicsProfile`**: a unit of
  language, its setting (medium, power asymmetry, vulnerability, stakes, ...),
  and 16 heuristic ethics indicators (quality axes vs. risk axes).
- **Manipulation dimensions**: false necessity, false dichotomy, shame/fear
  pressure, authority capture, semantic compression, testimonial injustice,
  obfuscation, persuasive counterfeit — supplied explicitly and/or detected by a
  small, documented phrase lexicon that always cites the phrase it matched.
- **Constructive language**: a `ConstructiveLanguageAssessment` scores how much
  the language *expands* the field of will (clarity, agency support, alternative
  visibility, consent support, ...) with a deterministic recommended rewrite.
- **Integration**: when a case has a `language_act`, its linguistic coercion is
  folded into the main `CoercionProfile` (it can only *raise* coercion), six new
  rules fire (**LB-R013 .. LB-R018**), and the report carries a full
  `language_analysis`. Consent built on manipulative language gets no confident
  approval (LB-R015).
- **CLI**: `littleboy analyze-language <case.json>`.

See [`docs/LANGUAGE_ETHICS.md`](docs/LANGUAGE_ETHICS.md) and
[`docs/LINGUISTIC_COERCION.md`](docs/LINGUISTIC_COERCION.md).

## LittleBoy v0.6: Comparison Engine

> Choose the **least coercive morally viable path** under the available
> evidence, while exposing uncertainty, missing data, trade-offs, and possible
> contradictions.

Real ethical decisions are choices among options, not verdicts on one action in
isolation. The `littleboy.comparison` module evaluates several candidate actions
(each a full `ActionCase`) with the existing `EthicalEvaluator` — it does **not**
replace it — and then:

- decides **moral viability** for each option (viable / viable-with-reservations
  / non-viable), where "viable" never means "morally perfect";
- computes **dominance**: an option strictly dominates another when it is less
  coercive and no worse on data, evidence, confidence, verdict, blockers, and
  feasibility for the same goal; partial dominance is a **trade-off**, surfaced
  not hidden;
- produces a **layered, transparent ranking** (viability → least coercion →
  consent integrity → vulnerability protection → reversibility under uncertainty
  → lower uncertainty → fewer less-coercive alternatives → constructive language),
  with a `primary_reason` and a `downgrade_reason` for each option;
- marks the ranking **unstable** when missing data or a close call could reorder
  it, and lists exactly `what_could_change_ranking`;
- preserves every option's full `EvaluationReport`.

The same set can rank differently under different policy profiles. CLI:
`littleboy compare <set.json> --policy strict`. See
[`docs/COMPARISON_ENGINE.md`](docs/COMPARISON_ENGINE.md) and
[`docs/TRADEOFF_ANALYSIS.md`](docs/TRADEOFF_ANALYSIS.md).

## LittleBoy v0.7: Temporal & Consequence Modeling

> **An action cannot be ethically judged only at the instant it occurs.** An
> action is ethically *unstable* if it reduces visible coercion now while
> creating hidden, cumulative, irreversible, or delayed coercion later.

Coercion is rarely confined to the moment of action: it can be delayed,
cumulative, reversible-now-but-irreversible-later, or simply *allowed to continue*
by inaction. The `littleboy.temporal` module judges an action across time —
deterministically, with no forecasting and no LLM, and never presenting an
estimate as a certain prediction. An `ActionCase` may now carry four optional,
fully-typed temporal inputs (and an `is_inaction` flag):

- **`consequences`** — a `ConsequenceSet` of per-horizon `ConsequenceEstimate`s,
  each with a *signed* `coercion_delta`, plus `probability`, `confidence`,
  `reversibility`, and `evidence_quality`;
- **`temporal_profile`** — coarse, directly-supplied per-horizon coercion;
- **`reversibility_profile`** — how fully, at what cost, and with what residual
  harm the action could be undone;
- **`cumulative_coercion_profile`** — how a single small coercion could become
  systemic if repeated, normalised, or institutionalised.

`project_temporal` combines these with the immediate coercion into a
`TemporalProjectionResult`: per-horizon coercion, an `expected_total_coercion`, a
`trend` (rising / falling / stable), `cumulative_coercion`, a `reversibility_score`,
the flags `prevents_greater_future_coercion`, `creates_long_term_dependency`, and
`reversible_now_irreversible_later`, plus `high_risk_unknowns`, `uncertainty`,
warnings, and missing data. Six rules consume it (and stay inert on non-temporal
cases, so all earlier cases behave identically):

- **LB-R019** Temporal Consequence — high long-term coercion downgrades even when
  immediate coercion is low;
- **LB-R020** Reversibility v2 — irreversible coercion needs stronger
  justification; unknown reversibility lowers confidence (complements LB-R010);
- **LB-R021** Cumulative Coercion — repetition/normalisation that makes coercion
  systemic downgrades;
- **LB-R022** Inaction Is Not Neutral — inaction that permits coercion to continue
  or grow is judged as a coercive choice;
- **LB-R023** Future Coercion Prevention — present coercion is *qualifiedly*
  justified only if it credibly prevents greater future coercion **and** meets the
  Axiom 3 conditions;
- **LB-R024** Temporal Uncertainty — high-impact but weakly-evidenced temporal
  claims lower confidence (more under stricter policy) and expose the missing data.

The comparison engine also gains an **immediate-term** and a **long-term**
ranking, and flags when they disagree. CLI: `littleboy temporal <case.json>`. See
[`docs/TEMPORAL_MODEL.md`](docs/TEMPORAL_MODEL.md),
[`docs/CONSEQUENCE_MODELING.md`](docs/CONSEQUENCE_MODELING.md), and
[`docs/CUMULATIVE_COERCION.md`](docs/CUMULATIVE_COERCION.md).

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
    builtin_rules.py# LB-R001 .. LB-R024 (incl. the language and temporal rules)
    engine.py       # RuleEngine: runs rules and synthesizes the verdict
    trace.py        # builds the ReasoningTrace
  case_builder/
    questions.py    # generates prioritised Questions for a partial case
    completeness.py # CaseCompletenessReport (can/should this be judged yet?)
    templates.py    # ScenarioTemplate + the ten built-in templates
    builder.py      # CaseBuilder (the public entry point)
    session.py      # wizard prompts + build_case_from_answers (I/O-free)
  language/
    models.py       # LanguageAct, LanguageContext, LanguageEthicsProfile, ...
    manipulation.py # transparent manipulation-phrase lexicon + detector
    scoring.py      # score_language_ethics / score_linguistic_coercion
    constructive.py # score_constructive_language
    analyzer.py     # analyze_language + bridge into the coercion model
  comparison/
    models.py       # ActionOption, ActionComparisonSet/Result, ranking/dominance/tradeoff
    dominance.py    # strict / partial / none / incomparable dominance
    ranking.py      # layered, transparent ranking (not a single score)
    tradeoffs.py    # explicit trade-off analysis
    engine.py       # ComparisonEngine (builds on EthicalEvaluator)
    report.py       # comparison JSON / text rendering
  temporal/
    models.py       # ConsequenceEstimate/Set, Temporal/Reversibility/Cumulative profiles, result
    horizon.py      # TimeHorizon ordering, aggregation weights, soft-OR
    consequences.py # assess_consequences (expected delta, worst/best plausible, uncertainty)
    reversibility.py# score_reversibility (cost + residual harm + epistemic status)
    cumulative.py   # score_cumulative_coercion (repetition-gated amplifiers)
    projection.py   # project_temporal: coercion across horizons (no import cycle)
    report.py       # temporal JSON / text rendering
  reasoning/
    report.py       # JSON / text rendering
    experiment.py   # EthicalExperiment runner (falsificatory + heuristic)
  cli.py            # evaluate / experiment / questions / build-case / templates / analyze-language / compare / temporal
tests/              # pytest suite
examples/           # sample JSON cases (incl. partial_*, language_*, comparison_*, temporal_*)
docs/               # ARCHITECTURE, ETHICAL_MODEL, RULE_ENGINE, POLICY_PROFILES,
                    #   CASE_BUILDER, SCENARIO_TEMPLATES, LANGUAGE_ETHICS,
                    #   LINGUISTIC_COERCION, COMPARISON_ENGINE, TRADEOFF_ANALYSIS,
                    #   TEMPORAL_MODEL, CONSEQUENCE_MODELING, CUMULATIVE_COERCION
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
pytest                      # 141 tests
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
littleboy analyze-language examples/language_manipulative_case.json       # linguistic coercion
littleboy analyze-language examples/language_constructive_case.json --format text
littleboy compare examples/comparison_basic.json                          # rank candidate actions
littleboy compare examples/comparison_irreversible_vs_reversible.json --policy precautionary --format text
littleboy temporal examples/temporal_low_now_high_later.json              # project coercion across time
littleboy temporal examples/temporal_cumulative_policy_risk.json --format text
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
| (see also the v0.5 language examples below) | |
| `examples/partial_medical_case.json` | `--template medical_decision` |
| `examples/partial_language_manipulation_case.json` | `--template speech_or_language_manipulation` |
| `examples/partial_emergency_case.json` | `--template emergency_intervention` |

The v0.5 **language** examples (each an `ActionCase` with a `language_act`); try
them with `littleboy analyze-language` and `littleboy evaluate`:

| File | Demonstrates | Verdict |
|------|--------------|---------|
| `examples/language_constructive_case.json` | Clear, agency-respecting, alternatives-visible language | `ACCEPTABLE` |
| `examples/language_manipulative_case.json` | False necessity + fear + manipulated consent | `NOT_ACCEPTABLE` |
| `examples/false_dichotomy_case.json` | "Either obey or destroy everything" | `NOT_ACCEPTABLE` |
| `examples/testimonial_injustice_case.json` | Dismissing a vulnerable person's testimony (LB-R016) | `NOT_ACCEPTABLE` |
| `examples/obfuscation_high_stakes_case.json` | Obscure binding notice where clarity is owed (LB-R018) | `NOT_ACCEPTABLE` |
| `examples/semantic_compression_euthanasia_case.json` | Reducing "I want to die" to a label; framing replaced | `INSUFFICIENT_DATA` |

The v0.6 **comparison** sets (each an `ActionComparisonSet`); run them with
`littleboy compare`:

| File | Demonstrates |
|------|--------------|
| `examples/comparison_basic.json` | A clear least-coercive option dominates the coercive ones |
| `examples/comparison_emergency_options.json` | Justified emergency coercion outranks inaction that permits more coercion |
| `examples/comparison_language_framing_options.json` | Constructive speech ranks above manipulative speech |
| `examples/comparison_medical_abstract_options.json` | Abstract consent-respecting option vs. pressured ones (no clinical claims) |
| `examples/comparison_irreversible_vs_reversible.json` | Reversibility vs. certainty trade-off; ranking shifts with policy |
| `examples/comparison_uncertain_data.json` | LittleBoy refuses a stable ranking (too little data) |

The v0.7 **temporal** examples; run them with `littleboy temporal` and
`littleboy evaluate`:

| File | Demonstrates | Verdict |
|------|--------------|---------|
| `examples/temporal_low_now_high_later.json` | Low coercion now, high coercion later (rising trend; LB-R019) | `NOT_ACCEPTABLE` |
| `examples/temporal_high_now_prevents_worse.json` | Temporary coercion that credibly prevents greater future coercion (LB-R023) | `ACCEPTABLE_WITH_RESERVATIONS` |
| `examples/temporal_inaction_not_neutral.json` | Inaction that permits coercion to continue/grow (LB-R022) | `NOT_ACCEPTABLE` |
| `examples/temporal_irreversible_weak_data.json` | Irreversible action on weak evidence (LB-R020/R024) | `INSUFFICIENT_DATA` |
| `examples/temporal_cumulative_policy_risk.json` | A small coercion that becomes systemic if normalised (LB-R021) | `NOT_ACCEPTABLE` |
| `examples/comparison_temporal_tradeoff.json` | A *comparison set* whose immediate and long-term rankings disagree (`littleboy compare`) | — |

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

**v0.7 — temporal & consequence modeling.** Implemented on top of v0.6: a
`littleboy.temporal` package that judges an action across time without
forecasting or any LLM. It models per-horizon consequence estimates,
reversibility (cost + residual harm + epistemic status), and cumulative coercion
(repetition-gated systemic amplifiers); `project_temporal` derives per-horizon
coercion, an expected total, a trend, and the ethically important flags
(prevents-greater-future-coercion, creates-long-term-dependency,
reversible-now-irreversible-later) while always carrying its own uncertainty,
warnings, and missing data. Six new rules (LB-R019 .. LB-R024) consume the
projection and stay inert on non-temporal cases; the comparison engine gains
immediate-term vs. long-term rankings and a conflict flag; a `temporal` CLI
command; six temporal examples; and a 141-test suite (all passing). The temporal
layer is purely additive — every pre-v0.7 case evaluates identically.

Earlier phases delivered the core models; coercion/data-quality/evidence scoring;
consent/agency models; the tri-state Axiom 3 justification; feasibility-aware
alternatives; the critical-data gate; the ethical experiment runner; the v0.3
rule engine with four policy profiles and a full reasoning trace (now
twenty-four rules); the v0.4 scenario builder; the v0.5 language & coercion
module (no NLP/LLM); and the v0.6 comparison engine. All v0.1–v0.6 inputs remain
valid.

**Deliberately not built:** any web UI, any LLM/API integration, any prediction
that looks certain, any claim to absolute truth, any heavy frameworks.

### Recommended next steps

- A deliberation/explanation layer that narrates *why* the top option beats the
  runner-up across time, and what single fact would most change the verdict or
  comparison (value of information).
- Calibrate the temporal horizon weights, the cumulative-coercion gate, and the
  coercion / language / evidence heuristics against a worked case library with
  golden-file regression tests.
- A scenario/Monte-Carlo layer that propagates the supplied probabilities and
  confidences into a *distribution* over outcomes — still deterministic given its
  inputs, still no LLM, never hiding the spread behind one number.
- **Optional** LLM-assisted indicator extraction (language and consequence)
  behind an explicit flag, with the model's suggestions shown, attributed, and
  editable — the deterministic core staying authoritative and the audit trail
  preserved.

## License

MIT.
