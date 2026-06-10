# LittleBoy

A rational ethical evaluation engine built on a single foundational axiom:

> **The fundamental ethical evil is coercion.
> The ethical good is the minimization or absence of coercion.**

LittleBoy takes a structured description of an action — who acts, who is
affected, the coercion involved, the consent, the evidence, the alternatives —
and returns a **transparent, explained verdict** with an honest account of its
own uncertainty. It is a reasoning engine, not a user interface and not a
language model.

This is **v0.20**, which turns the per-case classifications into a **corpus-level
diagnosis report**: `littleboy diagnose --against hana` decomposes the
disagreement with a labeller into its kinds — threshold questions
(policy-bridgeable), epistemic questions (fact-bridgeable), ambiguous (both), and
genuine divergence (neither) — each fraction with a Wilson interval, ranks the
**recurring bridging parameters and facts** (a parameter or fact counts once per
disagreement it bridges), and emits a concrete **tuning agenda** ("the data gate
bridges 4 of 25; consequence unknowns 4 more; 17 are genuine divergence, for
human review") — so a reliability number becomes a work list, with every figure
drillable back to its engine-verified per-case explanation. (v0.19 added fact
accounts and the unified classification; v0.18 made disagreements inspectable
case by case: trace diffs, threshold flips, and the engine-verified minimal
parameter account; v0.17 gave the fitting gain a real p-value —
Nadeau–Bengio corrected t over repeated stratified CV + an exact sign test — and a
40-case × 5-labeller external set; v0.16 added k-fold cross-validated fitting and
a 16-case independent panel; v0.15 imported real labels from CSV and added the
single-split fitted-threshold recommender; v0.14 grew the held-out set to a
160-case panel and added inter-labeller agreement + a policy-recommendation layer;
v0.13 added external-validity calibration and globally-cost-optimal probabilistic
planning; v0.12 let domains drive the planner and calibrated at scale with
independent labels; v0.11 made minimal intake cost-aware and interactive; v0.10
added multi-fact value of information and the minimal-sufficient-case planner;
v0.9 the deliberation & value-of-information layer; v0.8 adversarial audit & bias
testing; v0.7 temporal & consequence modeling; v0.6 the comparison engine; v0.5
the language module; v0.4 the scenario builder; v0.3 the rule engine and policy
layer.) See
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
[`docs/CONSEQUENCE_MODELING.md`](docs/CONSEQUENCE_MODELING.md),
[`docs/CUMULATIVE_COERCION.md`](docs/CUMULATIVE_COERCION.md),
[`docs/ADVERSARIAL_AUDIT.md`](docs/ADVERSARIAL_AUDIT.md),
[`docs/BIAS_TESTING.md`](docs/BIAS_TESTING.md),
[`docs/RED_FLAGS.md`](docs/RED_FLAGS.md),
[`docs/DELIBERATION.md`](docs/DELIBERATION.md),
[`docs/VALUE_OF_INFORMATION.md`](docs/VALUE_OF_INFORMATION.md),
[`docs/CALIBRATION.md`](docs/CALIBRATION.md), and
[`docs/MINIMAL_SUFFICIENT_CASE.md`](docs/MINIMAL_SUFFICIENT_CASE.md) for the full
design and formal model.

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

## LittleBoy v0.8: Adversarial Audit & Bias Testing

> **A rational ethical engine must not merely evaluate actions. It must also
> evaluate the conditions under which the action is being described.** LittleBoy
> must judge not only the action, but also the description through which the
> action becomes visible.

Every verdict is only as good as the case it was given — and a case is a
*description*, which can be shaped to lead a conclusion. The `littleboy.audit`
module is LittleBoy auditing itself against its inputs, deterministically and with
no NLP/LLM: every finding cites what it saw and what to ask next, and the
indicators are **risk flags, not proofs** (it does not claim to detect
manipulation or bias perfectly).

- **Red flags** (`AuditFinding`, severity `info`/`warning`/`serious`/`critical`):
  deterministic detectors over consent, coercion, evidence, language, temporal,
  and comparison structure — false consent, justification without a cessation
  condition, low structured coercion under manipulative language, irreversible
  action on weak evidence, missing counterevidence, authority capture, and more.
  See [`docs/RED_FLAGS.md`](docs/RED_FLAGS.md).
- **Adversarial risk** (`AdversarialRiskProfile`, 12 axes): leading language,
  missing counterevidence, one-sided description, false necessity/dichotomy, fake
  alternatives, hidden power asymmetry, hidden vulnerability, consent
  contamination, ideological capture, overconfidence, data laundering.
- **Bias indicators** (`BiasProfile`, 10 axes): agent, status, authority, outcome,
  survivorship, availability, framing, **language-beauty**, sympathy, and
  dehumanization risk. Beautiful language can distort judgment toward approval;
  poor expression can hide moral value — the beauty axis warns in **both**
  directions. See [`docs/BIAS_TESTING.md`](docs/BIAS_TESTING.md).
- **Adversarial stress tests** (`StressTestResult`): "what if the coercion is
  under-reported / consent is contaminated / the affected testimony is missing /
  alternatives were not disclosed / the language is leading / the long-term is
  worse / the option only looks best because data are missing?" — each with a
  plausibility and whether the verdict could change.
- **Ideological-capture checks**: is the coercion axiom applied too narrowly or as
  a slogan? — care-as-control, freedom-as-pressure, safety-as-domination,
  "natural"/"traditional" normalisation, autonomy-ignoring-vulnerability,
  utility-hiding-coercion, physical-force tunnel vision. The audit detects
  *distorted application* of the axiom, never replacing it.

The audit is **opt-in**, so default evaluation is unchanged. With
`evaluate(case, audit=True)` the rule-engine trace is preserved and the audit is a
separate, labelled layer (`report.audit_report`): a **critical** red flag then
bears on the verdict — high coercion → cannot confidently approve; irreversible →
blocked (`INSUFFICIENT_DATA`); consent central → consent-integrity warning; high
ideological-capture risk → requires explicit review; high language-beauty bias →
warns that persuasive form may be distorting judgment. Any critical finding marks
the judgment **unstable** and lowers confidence. Comparisons can be audited per
option and across the set; if the best option wins mostly because data about its
competitors are missing, the ranking is marked unstable. CLI:
`littleboy audit <case.json>`, `littleboy evaluate … --audit`,
`littleboy compare … --audit`. See
[`docs/ADVERSARIAL_AUDIT.md`](docs/ADVERSARIAL_AUDIT.md),
[`docs/BIAS_TESTING.md`](docs/BIAS_TESTING.md), and
[`docs/RED_FLAGS.md`](docs/RED_FLAGS.md).

## LittleBoy v0.9: Deliberation & Value of Information

> A verdict is not an explanation. LittleBoy should say **why** the verdict (or
> the winning option) came out as it did, and **what single fact would most
> change it.**

A bare verdict hides which factor was decisive and how close the call was. The
`littleboy.deliberation` layer (built on top of the evaluator and comparison
engine) adds two things, deterministically and with no LLM:

- **Narration** — orders the factors that drove the verdict into *decisive*
  (blockers / caps / downgrades, from the reasoning trace), *supporting* (coercion
  level, consent, Axiom 3 justification, alternatives), and *context*
  (confidence); for a comparison it names the lexicographic layer on which the
  runner-up lost.
- **Value of information** — among the genuine unknowns, which one, if resolved,
  would most change the verdict? Each unknown is resolved to each plausible value
  (consent GIVEN/REFUSED, reversibility 1.0/0.0, a feasible less-coercive
  alternative or none, the Axiom 3 conditions established or refuted, …), the
  **deterministic evaluator is re-run**, and the swing in verdict and confidence
  is measured. The unknown with the largest swing is the `most_informative` one,
  with the exact counterfactual resolutions recorded. A case with no material
  unknowns is reported `stable_under_information`; a comparison whose winner would
  change is `ranking_robust = False`.

No probabilities are invented — every value traces to an explicit re-evaluation.

v0.9 also ships an **adversarial calibration corpus** (`littleboy.calibration`):
labelled adversarial and clean cases, scored by the audit into a **miss rate**
(expected flags that did not fire) and a **false-alarm rate** (clean cases flagged
anyway), pinned by **golden-file regression** so any drift in the audit's
behaviour fails a test. The default corpus runs at miss rate 0.0 / false-alarm
rate 0.0 — the baseline to preserve while tuning thresholds. CLI:
`littleboy deliberate <case.json>` (add `-c` for a comparison set) and
`littleboy calibrate`. See [`docs/DELIBERATION.md`](docs/DELIBERATION.md),
[`docs/VALUE_OF_INFORMATION.md`](docs/VALUE_OF_INFORMATION.md), and
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.10: Multi-fact VoI & Minimal-Sufficient-Case Planning

> Don't ask for everything that is missing — ask only for **what could change the
> verdict**, smallest set first, in priority order.

v0.9 found the single most informative unknown. But a verdict can survive every
single resolution yet flip when two facts move **together**. v0.10 adds:

- **Multi-fact value of information** (`minimal_flip_sets`): probes now expose
  their resolutions as composable `case -> case` transforms, so the search can try
  *combinations* of unknowns. It searches combinations of increasing size and stops
  at the first size that flips the verdict, so every result is a **minimal flip
  set** — no proper subset would flip it alone. A `DeliberationReport` now carries
  `minimal_flip_sets`, `smallest_flip_size`, and `verdict_robust_to_combinations`.
- **Minimal-sufficient-case planner** (`Deliberator.question_plan`,
  `CaseBuilder.minimal_questions`): turns the VoI search into a
  `MinimalQuestionPlan` that lists **only the questions that could change the
  verdict** — *critical* if a fact flips it alone, *high* if it is part of a
  minimal combination — and omits questions that can only move confidence. CLI:
  `littleboy questions <case.json> --minimal`.
- **Scoring-layer calibration**: the audit calibration corpus (v0.9) is joined by a
  **scoring corpus** that gives the coercion, data-sufficiency, and temporal layers
  each a measured **miss rate** and **false-alarm rate** (plus an end-to-end
  verdict accuracy), pinned by its own golden file. CLI:
  `littleboy calibrate --scope scoring` (or `all`, the default).

Everything stays deterministic, typed, and additive — the verdict itself is
unchanged. See [`docs/MINIMAL_SUFFICIENT_CASE.md`](docs/MINIMAL_SUFFICIENT_CASE.md),
[`docs/VALUE_OF_INFORMATION.md`](docs/VALUE_OF_INFORMATION.md), and
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.11: Cost-aware, interactive minimal intake

> Ask the **cheapest** questions that could settle the verdict, one at a time,
> re-planning after each answer — and report how good the calibration really is.

v0.10 found the *smallest* set of unknowns to resolve. But answers differ in
effort: stating who consented is cheap; gathering corroborated evidence or
forecasting long-term consequences is expensive. v0.11 adds:

- **Cost-aware planning** (`cheapest_flip_set`): each question carries a `cost`
  (`DEFAULT_QUESTION_COSTS`, overridable), and the planner searches *all* sufficient
  sets for the **lowest total cost** — so two cheap questions can be preferred over
  one expensive one. The plan exposes `cheapest_set` / `cheapest_set_cost`, marks
  `in_cheapest_set`, and orders cheapest-set members first. With uniform costs it
  reduces to the smallest set.
- **Interactive minimal intake** (`run_minimal_intake`, behind
  `littleboy build-case --minimal --from <case.json>`): a loop that asks the top
  cheapest, verdict-relevant question, applies the answer, **re-plans on the
  updated case**, and repeats until the verdict is *settled* (no remaining unknown
  could change it). Re-planning matters: resolving one fact can make another newly
  decisive or newly irrelevant. The loop is I/O-free (it takes an answer callback),
  so it is deterministic and testable.
- **Calibration with confidence intervals, per policy**: the scoring corpus is
  larger (21 cases) and each miss/false-alarm rate carries a deterministic **Wilson
  95% confidence interval**; the corpus is re-run under **each policy mode**, so the
  coercion false-alarm rate visibly rises under stricter thresholds — the
  precision/sensitivity trade-off, measured.

Deterministic, typed, additive. See
[`docs/MINIMAL_SUFFICIENT_CASE.md`](docs/MINIMAL_SUFFICIENT_CASE.md) and
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.12: Domain-driven intake & independently-labelled calibration

> Let the domain declare what is cheap to learn and what answers are possible; and
> measure the heuristics against labels they did not write.

- **Case-supplied cost/answer models**: an `ActionCase` may carry `intake_hints`
  with `question_costs` (`field -> cost`, merged over the defaults) and
  `answer_values` (`field -> plausible answer strings`, which *replace* a probe's
  default counterfactual resolutions). So a domain drives the planner: it can make
  a question expensive, or declare that consent here can only be `given` — and if
  the only plausible answer cannot flip the verdict, that question drops out.
- **Expected-cost lookahead**: `expected_cost_first_question` is an expectimax that,
  assuming answers are uniform over each probe's plausible resolutions, picks the
  first question minimising *expected total cost to settle* — a slightly costlier
  question can win if it needs fewer follow-ups. Opt in with
  `run_minimal_intake(strategy="lookahead")` or `build-case --minimal --strategy
  lookahead`.
- **Independently-labelled calibration at scale**: `generate_scoring_corpus` builds
  a large corpus deterministically (fixed seed), labelling each case from latent
  severity/adequacy parameters — **not** from the evaluator — so agreement is a
  genuine measurement. On n=120 the coercion detector shows a ~0.43 false-alarm
  rate against the latent labels (it flags coercion readily, by design) and
  data-sufficiency a ~0.20 miss rate; Wilson intervals tighten as n grows
  (~0.38 wide at n=40 → ~0.16 at n=320). CLI: `littleboy calibrate --scope scoring
  --generated --n 200`.

Deterministic, typed, additive. See
[`docs/MINIMAL_SUFFICIENT_CASE.md`](docs/MINIMAL_SUFFICIENT_CASE.md) and
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.13: External validity & probabilistic planning

> Measure agreement with held-out *human* judgment, per policy; and plan the
> cheapest questionnaire over what answers are actually *likely*.

- **External-validity reliability**: a small `OutcomeCorpus` carries verdict labels
  authored by a human panel — **independent of the heuristics** — split into `dev`
  (tunable) and `holdout` (reported, never tuned against). `run_reliability`
  reports, **per policy and per split**, how often the engine's verdict matches the
  human label — both *exactly* and on a coarse **disposition** (permissible /
  impermissible / insufficient) — each with a Wilson interval, and lists every
  disagreement. On the packaged holdout set `standard` tracks the panel best
  (~0.88) while `precautionary` is far more conservative (~0.25): a real, measured,
  sub-1.0 reliability with honestly wide intervals. CLI: `littleboy calibrate
  --scope reliability`.
- **Probabilistic, globally-optimal planning**: `intake_hints.answer_probabilities`
  (`field -> {answer -> probability}`) lets the expected-cost lookahead weight
  answers by a non-uniform distribution. The lookahead is an **expectimax** — it
  chooses the cost-minimising question at every node, so it yields the globally
  cost-optimal questionnaire (not a greedy one), and the *probabilities can change
  which question to ask first*: a cheap question whose answers rarely settle the
  verdict loses to a costlier one whose answers usually do.
  `expected_questionnaire_cost` returns the optimal expected total.

Deterministic, typed, additive — the verdict itself is unchanged. See
[`docs/MINIMAL_SUFFICIENT_CASE.md`](docs/MINIMAL_SUFFICIENT_CASE.md) and
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.14: Independent labelling at scale & policy recommendation

> A reliability number is only meaningful next to **how much the labelers agreed
> with each other** — and different stakeholders deserve different policies, shown
> with their trade-offs, not one answer pretending to be universal.

- **Multi-labeller corpus at scale**: `generate_outcome_corpus` /
  `default_labelled_outcome_corpus` builds a held-out outcome set an order of
  magnitude larger (**160 cases**), each judged by a **panel of three independent
  labelers** — `lenient`, `median`, `strict` — each a different, transparent
  judgment rule authored separately from the engine and from one another. The
  panel's majority is the **consensus**; each labeler's raw verdict is kept so
  agreement can be measured. Deterministic given the seed.
- **Inter-labeller agreement as the ceiling**: `inter_rater_agreement` reports the
  mean pairwise **percent agreement** and **Fleiss' kappa** (chance-corrected) on
  the coarse disposition. On the holdout the three labelers agree only ~**0.68**
  (kappa ~**0.37**), and this ceiling rides on every `SplitReliability` — *no policy
  can be expected to match the consensus more often than the labelers match each
  other*, so a policy at 0.92 disposition agreement is doing well against a **noisy
  target**, not approaching perfection.
- **Policy-recommendation layer**: `recommend_policy_for_stakeholder(corpus,
  labeler=…)` (and `recommend_policy(report)`) takes a stakeholder's held-out
  judgments and recommends the policy whose verdicts best match them (by
  disposition, or `exact`), **with the trade-offs shown**: the full ranking with
  Wilson intervals, the policies whose intervals **overlap the leader's** (so the
  data cannot separate them), and the agreement ceiling as an over-fitting caveat.
  Because the labelers genuinely differ, the recommendation diverges by stakeholder
  — a `lenient` stakeholder is best served by `permissive`, a `strict` one by
  `precautionary` (a perfect match) — and the cost of satisfying the strict
  stakeholder (consensus agreement dropping 0.92 → 0.74) is made explicit. CLI:
  `littleboy recommend-policy --stakeholder strict`.

Deterministic, typed, additive — the verdict itself is unchanged. See
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.15: Real labels from CSV & a fitted-threshold recommender

> The persona panel is a stand-in. Let *real* independent labels drop in and run
> through the same machinery — and when a stakeholder wants better than a coarse
> built-in policy, fit one **honestly**: on the dev split, scored on the holdout,
> shown next to the nearest built-in so an over-fit can't hide.

- **Real, independent labels via CSV** (`littleboy.calibration.labels`): import
  actual human verdicts from a `case_id,labeler,verdict[,split]` CSV
  (`outcome_corpus_from_csv`, `apply_labels`, `parse_labels_csv`; `labels_to_csv`
  for a template / round-trip export) and overlay them onto the known cases by id.
  The resulting `OutcomeCorpus` runs through the **existing** `run_reliability`,
  `recommend_policy`, and `fit_threshold_policy` **unchanged** — the engine is only
  ever *measured against* the labels, never trained on them. The consensus rule is
  transparent (majority; ties broken toward the more cautious reading), and a
  round-trip reproduces per-labeller reliability exactly. CLI: `littleboy
  recommend-policy --labels-csv my_labels.csv`.
- **A fitted-threshold recommender** (`fit_threshold_policy`): beyond the four
  built-in policies, search a deterministic grid of the two coercion thresholds for
  the set best matching a stakeholder — **fitting on dev only**, then scoring the
  chosen thresholds on the **never-fitted holdout**. A fitted set is turned back
  into a real `PolicyProfile` and run through the *real* engine (no verdict logic
  duplicated). The fitted policy is shown **side-by-side with the nearest built-in**
  with confidence intervals on both, the `gain_over_nearest`, a
  `distinguishable_from_nearest` flag (true only if the intervals don't overlap),
  and the inter-labeller ceiling as the caveat. On the current corpus fitting gives
  only a small holdout gain and the intervals always overlap — so the tool tells you
  to **prefer the simpler built-in**, and the consensus fit (better on dev, worse on
  holdout) is flagged as a textbook over-fit. CLI: `littleboy recommend-policy
  --stakeholder strict --fit`.

Deterministic, typed, stdlib-only, additive — the verdict itself is unchanged. See
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.16: Cross-validated fitting & a packaged independent set

> One holdout point can be lucky. Report the fitted policy's gain as a **mean ±
> spread across folds** — and ship a genuinely independent labelled set, authored
> without consulting the engine, to run the whole stack against.

- **k-fold cross-validation** (`cross_validate_threshold_policy`): the cases are
  pooled into `k` deterministic folds; each fold **fits thresholds on its training
  part and scores them — and the nearest built-in — on its held-out part**. The
  result is the *procedure's* generalisation: `mean_gain ± gain_std` (with min/max),
  a `fitting_helps` flag (true only when the mean stays positive one σ down), and a
  `threshold_stability` read. A verdict matrix is computed once, so CV costs one grid
  evaluation regardless of `k`. The fitter can now also optionally tune the
  **data-quality gate** and **irreversibility floor**. This is strictly more honest
  than one holdout: for the `strict` stakeholder the single-split fit said "intervals
  overlap, prefer the built-in", but 5-fold CV shows the gain is robust (**+0.069 ±
  0.054**, modal thresholds stable across all folds) — one point hid a real effect.
- **A packaged independent labelled set** (`default_independent_outcome_corpus`): the
  16 v0.13 cases relabelled by a **three-person panel** (`ann`/`ben`/`cleo`) whose
  verdicts live in `independent_labels.csv` and were **hand-authored as independent
  human judgments — written without consulting the engine's output**, disagreeing
  more messily than the rule-based personas (dev percent agreement ~0.54, Fleiss
  kappa ~0.15). Imported through the **v0.15 CSV path**, inheriting the v0.13
  dev/holdout split, it runs through `run_reliability` / `recommend_policy` /
  `fit_threshold_policy` / `cross_validate_threshold_policy` **unchanged** — and on
  this small, noisy set fitting honestly buys ~nothing over the nearest built-in.
  CLI: `littleboy recommend-policy --independent --cv`.

Deterministic, typed, stdlib-only, additive — the verdict itself is unchanged. See
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.17: Calibrated inference & a larger external set

> "Fitting helps" should be a statistical claim, not a hunch — a p-value from a
> test that knows CV folds overlap, on a labelled set diverse enough to matter.

- **Calibrated CV inference** (`cv_gain_inference`): repeated, **stratified**
  k-fold CV (folds balanced by disposition; a different deterministic partition per
  repetition), with the gain over the nearest built-in tested by the
  **Nadeau–Bengio corrected resampled t-test** — its `s²·(1/m + 1/(k−1))` variance
  correction accounts for overlapping training sets, so the standard error is
  floored at `s/√(k−1)` and **repeating CV cannot manufacture confidence** (a
  property under test). Cross-checked by an **exact sign test** over paired
  out-of-fold predictions. All stdlib: `calibration/stats.py` implements the
  Student-t CDF via the regularised incomplete beta (continued fraction), tested
  against closed forms (Cauchy, df=2, symmetry). On the synthetic panel the
  `strict` gain v0.16 called "robust" now reads **+0.069, 95% CI [+0.029, +0.108],
  p = 0.0010** (sign test 11 vs 0, p = 0.0010), and the interval **tightens with
  n**: width 0.129 (n=40, p=0.13) → 0.091 (n=80, p=0.03) → 0.079 (n=160, p=0.001).
- **A larger external labelled set** (`default_external_outcome_corpus`):
  `external_case_bank` deterministically generates **40 diverse cases** (severity,
  data adequacy, consent, reversibility, and evidence all vary, so "insufficient
  data" is a live option; each case's description states its facts for
  auditability), and `external_labels.csv` carries **5 hand-authored labellers'**
  verdicts per case — written against the case facts, without consulting the
  engine's output, by five different temperaments. Agreement is genuinely messy
  (dev kappa ~0.28), policy reliabilities drop to realistic levels (holdout
  disposition 0.40–0.85), and the inference honestly reports that fitting does
  **not** demonstrably help here (mean −0.020, p = 0.41). CLI:
  `littleboy recommend-policy --external --inference`.

Deterministic, typed, stdlib-only, additive — the verdict itself is unchanged. See
[`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.18: Case-level disagreement explanations

> A reliability table says *how often* the engine disagrees. It should also say
> **why** — case by case, down to the one parameter or rule that accounts for it.

- **Policy-vs-policy: a true trace diff** (`explain_policy_disagreement`): rules
  whose *outcome* changed between the two evaluations (`TraceDelta`, e.g.
  `LB-R002: failed/blocker -> passed/warning`); **threshold flips**
  (`ThresholdFlip`) where the same policy-independent score crosses a limit under
  one policy only (`coercion_score=0.65 vs max_coercion_for_acceptable: 0.6
  (crossed) -> 0.75 (not crossed)`); and the **minimal parameter account**
  (`minimal_policy_accounts`) — the smallest set(s) of policy parameters that,
  moved to the other policy's values, make the engine *actually produce* the other
  verdict. Every candidate hybrid profile is re-evaluated through the real engine,
  and the search proceeds by increasing size, so each account is provably minimal —
  the policy-parameter analogue of the deliberation layer's minimal flip sets.
- **Engine-vs-labeller** (`explain_label_disagreement`,
  `explain_reliability_disagreements`): the human side has no trace, so the honest
  explanation is the engine's **decisive factors** (blockers, caps, downgrades,
  the data gate — straight from the trace), **which built-in policies agree** with
  the label, and the parameter account toward the nearest agreeing policy (the
  *bridge*) — e.g. *"the engine declined on the data gate (LB-R004); `permissive`
  reproduces the panel's verdict; the one-parameter account is
  `min_data_quality_for_approval: 0.35 -> 0.25`"*. Impasses are diagnosed
  specifically: **within-disposition** ("degree, not kind") vs **no built-in
  agrees even on disposition** ("not a threshold question") — separating the cases
  worth a human look from threshold quibbles. One explanation per reliability
  disagreement, count-pinned by test. CLI: `littleboy explain-disagreement
  ext-0007 --external --against consensus` (or `--against <policy>` on any case
  JSON, or `--all` for one line per disagreement).

Deterministic, typed, evaluation-only, additive — the verdict itself is unchanged.
See [`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.19: Fact accounts & the unified explanation

> A labeller who diverges from the engine is doing one of two things: weighing
> values differently, or assuming a fact the case leaves unknown. The explanation
> should search **both routes** — and say when it found neither.

- **Minimal fact accounts** (`minimal_fact_accounts`): the case's genuine unknowns
  and their candidate resolutions come from the deliberation layer's existing
  probes (`build_probe_specs` — the same composable `case -> case` transforms
  behind value of information and minimal flip sets), and the search is the
  *targeted* counterpart of a minimal flip set: the joint resolution must make the
  engine produce **the labeller's verdict exactly** (not just any different one).
  Increasing-size search, every candidate re-evaluated through the real engine —
  verified and provably minimal, e.g. `consent = REFUSED`.
- **The unified classification** (`bridge_classification`): every
  engine-vs-labeller disagreement is classified by which engine-verified routes to
  agreement exist — **`policy-bridgeable`** (a built-in policy reproduces the
  label; the parameter account shows the smallest change), **`fact-bridgeable`**
  (resolving unknowns reaches the label — the labeller may know something the case
  doesn't state), **`both`** (genuinely ambiguous between values and facts: on the
  packaged independent set, `policy_strict_borderline` vs `cleo` is bridged
  *either* by `unknown_consent_is_blocker: False -> True` *or* by
  `consent = REFUSED`, and the explanation says which question that poses), or
  **`neither`** (worth a human look — on the external set vs consensus, 17 of 21,
  mostly the panel condemning on data the engine refuses to judge: a real
  normative difference, now separated from threshold quibbles and fact gaps).
  `littleboy explain-disagreement --all` classifies every line and prints the
  tally.

Deterministic, typed, evaluation-only, additive — the verdict itself is unchanged.
See [`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## LittleBoy v0.20: The corpus-level diagnosis report

> The per-case explanations answer "why this case?". The diagnosis answers
> **"where does the disagreement with this labeller come from, overall?"** — and
> turns the answer into a work list.

- **`diagnose_disagreements`**: one auditable report per (labeller × policy) — a
  deterministic aggregation of the engine-verified per-case explanations (nothing
  new is inferred; the per-case classification index is included so every number
  drills back down). It reports agreement with its Wilson interval against the
  inter-labeller ceiling, then decomposes the disagreements into
  **policy-bridgeable / fact-bridgeable / both / neither** fractions, each with
  its own interval. The diagnosis agreement is the *same measurement* as the
  reliability table's exact accuracy — a test pins them equal.
- **Recurring accounts & the tuning agenda**: bridging parameters and facts are
  ranked by how many disagreements each would align (counted once per case), then
  rendered as an agenda — on the external set vs `hana`:
  `'min_data_quality_for_approval' bridges 4/25`, `establishing 'long-term
  consequences are worse than described' aligns 4/25`, and `17/25 are genuine
  divergence — candidates for human review`. The reading is direct: hana's
  divergence is mostly genuine (0.68, CI [0.48, 0.83]), a quarter is the data
  gate and consequence unknowns, and almost none is the coercion thresholds. The
  docs are explicit that this is an *agenda, not a recommendation*: the numbers
  say where alignment is cheap, not where it is right. CLI:
  `littleboy diagnose --external --against hana [--split holdout] [--format json]`.

Deterministic, typed, evaluation-only, additive — the verdict itself is unchanged.
See [`docs/CALIBRATION.md`](docs/CALIBRATION.md).

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
  audit/
    models.py       # AuditFinding/Report, Adversarial/Bias profiles, StressTestResult
    red_flags.py    # deterministic consent/coercion/evidence/language/temporal/comparison detectors
    bias.py         # BiasProfile indicators (incl. language-beauty bias, both directions)
    adversarial.py  # AdversarialRiskProfile, ideological-capture checks, verdict adjustment
    stress.py       # AdversarialStressTester (audit_case / audit_evaluation / audit_comparison)
    report.py       # audit JSON / text rendering
  deliberation/
    models.py       # DeliberationReport, InformationValue, MinimalFlipSet, MinimalQuestionPlan, ...
    voi.py          # value of information: composable probes, single/multi-fact + cheapest-set search
    narrate.py      # narrate why a verdict / top option holds
    minimal_case.py # plan_minimal_questions: cheapest-first, verdict-relevant questions
    intake.py       # interactive minimal-intake loop (I/O-free) + answer application
    engine.py       # Deliberator (deliberate / deliberate_comparison / question_plan)
    report.py       # deliberation + question-plan + intake JSON / text rendering
  calibration/
    models.py       # Audit + Scoring corpora, digests, CalibrationReport / ScoringCalibrationReport
    metrics.py      # per-entry audit scoring + miss / false-alarm aggregation
    corpus.py       # load / run the audit corpus, build digests, golden payload
    scoring.py      # run the scoring corpus + per-policy + Wilson confidence intervals
    generator.py    # deterministic corpus generators: scoring (latent labels) + multi-labeller outcomes
    reliability.py  # external-validity reliability, inter-labeller agreement, per-stakeholder policy recommendation
    labels.py       # import real independent labels from CSV; transparent consensus; round-trip
    fitting.py      # fit a threshold policy (single split, k-fold CV, calibrated gain inference)
    stats.py        # stdlib-only Student-t CDF, corrected-t machinery, exact sign test
    explain.py      # disagreement explanations: trace diffs, parameter + fact accounts, classification
    diagnosis.py    # corpus-level diagnosis: classification fractions, recurring accounts, tuning agenda
    audit_corpus.json     # the packaged, self-contained audit calibration corpus
    scoring_corpus.json   # the packaged scoring-layer calibration corpus
    outcome_corpus.json   # the packaged held-out, human-labelled outcome corpus
    independent_labels.csv# an independent three-person panel's verdicts for the outcome cases
    external_labels.csv   # five hand-authored labellers' verdicts for the 40-case external bank
  reasoning/
    report.py       # JSON / text rendering
    experiment.py   # EthicalExperiment runner (falsificatory + heuristic)
  cli.py            # evaluate / experiment / questions / build-case / templates / analyze-language / compare / temporal / audit / deliberate / calibrate / recommend-policy / explain-disagreement / diagnose
tests/              # pytest suite (incl. golden/ for calibration regression)
examples/           # sample JSON cases (incl. partial_*, language_*, comparison_*, temporal_*, audit_*, voi_*)
docs/               # ARCHITECTURE, ETHICAL_MODEL, RULE_ENGINE, POLICY_PROFILES,
                    #   CASE_BUILDER, SCENARIO_TEMPLATES, LANGUAGE_ETHICS,
                    #   LINGUISTIC_COERCION, COMPARISON_ENGINE, TRADEOFF_ANALYSIS,
                    #   TEMPORAL_MODEL, CONSEQUENCE_MODELING, CUMULATIVE_COERCION,
                    #   ADVERSARIAL_AUDIT, BIAS_TESTING, RED_FLAGS,
                    #   DELIBERATION, VALUE_OF_INFORMATION, CALIBRATION,
                    #   MINIMAL_SUFFICIENT_CASE
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
pytest                      # 294 tests
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
littleboy build-case --minimal --from examples/voi_consent_pivotal.json   # interactive: only verdict-changing questions
littleboy analyze-language examples/language_manipulative_case.json       # linguistic coercion
littleboy analyze-language examples/language_constructive_case.json --format text
littleboy compare examples/comparison_basic.json                          # rank candidate actions
littleboy compare examples/comparison_irreversible_vs_reversible.json --policy precautionary --format text
littleboy temporal examples/temporal_low_now_high_later.json              # project coercion across time
littleboy temporal examples/temporal_cumulative_policy_risk.json --format text
littleboy audit examples/audit_fake_consent.json                          # adversarial audit of the description
littleboy evaluate examples/audit_hidden_coercion.json --audit --format text   # evaluate + audit
littleboy compare examples/comparison_uncertain_data.json --audit         # audit the comparison
littleboy deliberate examples/voi_consent_pivotal.json                    # why, + the fact that most changes the verdict
littleboy deliberate examples/comparison_voi_pivotal.json --compare       # deliberate over a comparison
littleboy questions examples/voi_consent_pivotal.json --minimal           # only the questions that could change the verdict
littleboy calibrate                                                       # audit + scoring + reliability
littleboy calibrate --scope scoring --generated --n 200                   # large, independently-labelled corpus
littleboy calibrate --scope reliability                                   # per-policy agreement with held-out human labels
littleboy calibrate --scope reliability --labelled                        # 160-case panel + inter-labeller ceiling
littleboy recommend-policy --stakeholder strict                           # best policy for a stakeholder, trade-offs shown
littleboy recommend-policy --stakeholder lenient --metric exact --format text
littleboy recommend-policy --stakeholder strict --fit                     # also fit custom thresholds (dev) vs nearest built-in (holdout)
littleboy recommend-policy --stakeholder strict --cv --folds 5            # k-fold CV: gain over nearest built-in, mean +/- spread
littleboy recommend-policy --stakeholder strict --inference               # calibrated p-value on the fitting gain (corrected t + sign test)
littleboy recommend-policy --labels-csv my_labels.csv                     # use real labels (case_id,labeler,verdict[,split])
littleboy recommend-policy --independent                                  # against the packaged independent three-person panel
littleboy recommend-policy --external --inference                         # the 40-case x 5-labeller external set + inference
littleboy explain-disagreement ext-0007 --external --against consensus    # WHY the engine diverges from the panel, case-level
littleboy explain-disagreement examples/policy_permissive_case.json --against permissive   # trace diff between two policies
littleboy explain-disagreement policy_strict_borderline --independent --against cleo       # a 'both' case: policy OR fact route
littleboy explain-disagreement --all --external --against hana            # one line per disagreement + classification tally
littleboy diagnose --external --against hana                              # corpus-level diagnosis: fractions, recurring accounts, agenda
littleboy build-case --minimal --from examples/voi_consent_pivotal.json --strategy lookahead
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

The v0.8 **audit** examples; run them with `littleboy audit` (or
`littleboy evaluate --audit`):

| File | Demonstrates |
|------|--------------|
| `examples/audit_hidden_coercion.json` | Low structured coercion, highly manipulative language (inconsistency red flag) |
| `examples/audit_fake_consent.json` | Consent claimed under pressure, by a third party (critical consent red flag) |
| `examples/audit_beautiful_language_bad_content.json` | A bad action described beautifully (persuasive counterfeit) |
| `examples/audit_ugly_language_good_content.json` | A good action described poorly (language-beauty bias, other direction) |
| `examples/audit_missing_counterevidence.json` | A coercive action evidenced only by the actor's own say-so |
| `examples/audit_authority_capture.json` | Authority used to suppress questioning |
| `examples/audit_protection_as_paternalism.json` | "For your own good": care/protection used as control |
| `examples/audit_freedom_as_social_pressure.json` | "No one is forcing you": freedom language hiding social pressure |
| `examples/comparison_audit_framing_bias.json` | A *comparison set* whose ranking leans on a thinly-evidenced front-runner (`littleboy compare --audit`) |

The v0.9 **deliberation** examples; run them with `littleboy deliberate`:

| File | Demonstrates |
|------|--------------|
| `examples/voi_consent_pivotal.json` | A case fully specified except consent — the single pivotal unknown (GIVEN → acceptable-with-reservations, REFUSED → ethically suspicious) |
| `examples/comparison_voi_pivotal.json` | A *comparison set* (`--compare`) whose winner flips when one option's unknown is resolved |

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

**v0.20 — the corpus-level diagnosis report.** Implemented on top of v0.19.
`diagnose_disagreements` aggregates the engine-verified per-case explanations
into one auditable report per (labeller × policy): agreement with a Wilson
interval against the inter-labeller ceiling; the disagreement decomposed into
`policy-bridgeable` / `fact-bridgeable` / `both` / `neither` fractions (each with
its interval, summing to the disagreement count); the **recurring bridging
parameters and facts** ranked by how many disagreements each would align (counted
once per case, with the case ids); a human-readable **tuning agenda** ending in a
review line for the genuine-divergence cases; and the per-case classification
index so every number drills back down. Consistency is pinned by tests: the
diagnosis agreement equals the reliability table's exact accuracy, and the
fractions equal the per-case classification tally. On the external set vs `hana`:
agreement 0.38, divergence 68% genuine (CI [0.48, 0.83]), the data gate bridging
4/25 and consequence unknowns 4/25 — a reliability number turned into a work
list. New CLI `diagnose` (`--against`, `--split`, corpus flags, text/JSON); a
diagnosis golden file; a 294-test suite (all passing). Purely additive — the
verdict itself is unchanged.

Earlier phases delivered the core models; coercion/data-quality/evidence scoring;
consent/agency models; the tri-state Axiom 3 justification; feasibility-aware
alternatives; the critical-data gate; the ethical experiment runner; the v0.3
rule engine with four policy profiles and a full reasoning trace (twenty-four
rules); the v0.4 scenario builder; the v0.5 language & coercion module (no
NLP/LLM); the v0.6 comparison engine; the v0.7 temporal & consequence model; the
v0.8 adversarial audit & bias testing; the v0.9 deliberation &
value-of-information layer; the v0.10 multi-fact VoI & minimal-case planner; the
v0.11 cost-aware interactive intake; the v0.12 domain-driven intake &
independently-labelled calibration; the v0.13 external-validity reliability &
probabilistic planning; the v0.14 panel labelling at scale, inter-labeller
agreement & policy recommendation; the v0.15 real-labels CSV import &
single-split fitted-threshold recommender; the v0.16 cross-validated fitting &
16-case independent panel; the v0.17 calibrated CV inference & 40-case external
set; the v0.18 case-level disagreement explanations (trace diffs + minimal
parameter accounts); and the v0.19 fact accounts & unified classification. All
v0.1–v0.19 inputs remain valid.

**Deliberately not built:** any web UI, any LLM/API integration, any opaque bias
detection, any prediction that looks certain, any claim to absolute truth, any
heavy frameworks. The aim is to make LittleBoy **harder to manipulate and easier
to interrogate, not more dogmatic**.

### Recommended next steps

- Collect labels from **people genuinely unconnected to the project** for the
  external case bank (each case's description already states its facts; the CSV
  path, agreement, reliability, recommendation, inference, explanations, and the
  diagnosis all run unchanged), and publish the resulting real agreement, gain
  inference, and diagnosis report.
- Close the loop from agenda to action: a **dry-run tuner** that takes one agenda
  item (a parameter change or a rule adjustment), applies it as a candidate
  profile, and reports the full before/after impact — reliability on every
  labeller, the dev/holdout splits, and the golden diffs it would cause — so a
  tuning decision is made with its costs visible, never silently.
- Let `intake_hints` declare fully custom unknowns (probe fields, resolutions, costs,
  and probabilities) so domains beyond the built-in fields can drive the planner —
  which would also widen the fact-account vocabulary case by case.
- **Optional** LLM-assisted indicator extraction (language, consequence, audit)
  behind an explicit flag, with the model's suggestions shown, attributed, and
  editable — the deterministic core staying authoritative and the audit trail
  preserved.

## License

MIT.
