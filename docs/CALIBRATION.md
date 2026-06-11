# LittleBoy calibration corpus (v0.9)

> The audit's red flags are heuristics. To tune them honestly you need a labelled
> set of cases and two numbers: **how often does it miss, and how often does it
> cry wolf?** — pinned by golden-file regression so drift cannot slip through.

## Why a calibration corpus

The adversarial audit (v0.8) raises red flags on how a case is *described*. Like
any detector, it can **miss** (an adversarial case that should be flagged is not)
and it can **false-alarm** (a clean case is flagged anyway). Tuning a threshold to
catch more adversarial cases usually flags more clean ones too. You cannot manage
that trade-off without measuring it, and you cannot measure it without a labelled
corpus. `littleboy.calibration` provides one, scores it, and freezes the result.

## The corpus

An `AuditCorpus` is a list of `CorpusEntry` objects, each a labelled case:

- `label` — `"adversarial"` (red flags expected) or `"clean"` (none should fire);
- `case` — a full, inline `ActionCase` (the corpus is self-contained and
  deterministic);
- `expect_findings` — finding ids that **should** appear (a *miss* if absent);
- `forbid_findings` — finding ids that **must not** appear (a *false alarm* if
  present);
- `expect_judgment_stable` — the expected audit stability, or `None` to skip.

The default corpus ships inside the package (`littleboy/calibration/audit_corpus.json`)
so `littleboy calibrate` works anywhere. It pairs the v0.8 adversarial examples
(each with the specific finding it should raise) with clean cases (low-coercion,
constructive-language, and a deliberately *poorly-worded but benign* case that
must **not** trip a red flag).

## The two metrics

`run_corpus` audits every entry and computes:

- **miss rate** — expected adversarial findings that did not fire, over all
  expected findings;
- **false-alarm rate** — clean cases that nonetheless raised a red flag
  (serious/critical), over all clean cases.

They are reported together because lowering one typically raises the other. A
clean case that raises any serious/critical finding is counted as a false alarm
even if no specific finding was forbidden, so the audit cannot quietly start
flagging benign cases. The current default corpus runs at **miss rate 0.0** and
**false-alarm rate 0.0** — the baseline a maintainer must preserve while changing
thresholds.

## Golden-file regression

`golden_payload` produces a deterministic digest of the run — the two rates, the
pass count, and a per-case `CaseDigest` (sorted finding ids, red flags, stability,
and the audit's max risk axes). The digest is stored at
`tests/golden/audit_corpus.golden.json`, and a regression test re-runs the corpus
and asserts the digest is unchanged. **Any drift in the audit's behaviour — a new
flag, a changed severity, a flipped stability — fails the test loudly.** When a
change is intended, regenerate the golden file:

```bash
LITTLEBOY_UPDATE_GOLDEN=1 pytest tests/test_calibration.py::test_golden_regression
```

## How to tune against it

1. Change an audit threshold (e.g. a severity boundary in `audit/red_flags.py`).
2. `littleboy calibrate` — read the new miss / false-alarm rates and the per-case
   PASS/FAIL lines.
3. If the trade-off is acceptable, regenerate the golden file; if not, revert.
4. Add new corpus entries (adversarial and clean) as new manipulation patterns are
   discovered, so the metrics keep pace with the threats.

```bash
littleboy calibrate                         # run both corpora (audit + scoring)
littleboy calibrate --scope audit           # just the audit corpus
littleboy calibrate my_corpus.json --format json
```

## Scoring-layer calibration (v0.10)

The audit corpus measures whether the *audit* flags the right cases. v0.10 extends
the same discipline to the underlying **scoring layers**, so every layer — not only
the audit — has measured miss and false-alarm rates. A `ScoringCorpus` of labelled
cases is run through the full evaluator, and each layer is treated as a transparent
binary detector over the report:

| Layer | Detector (predicts "positive" iff …) | Label |
|-------|--------------------------------------|-------|
| **coercion** | `coercion_score >= policy.coercion_moderate` | `coercive` |
| **data_sufficiency** | verdict is not `INSUFFICIENT_DATA` | `adequate_data` |
| **temporal** | temporal projection has data and trend is `rising` | `rising_coercion` |

For each labelled layer, a labelled-positive the detector misses is a **miss**, and
a labelled-negative it flags is a **false alarm**, giving a per-layer `miss_rate`
and `false_alarm_rate`. The end-to-end `verdict` label gives a **verdict accuracy**.

### Confidence intervals and per-policy breakdown (v0.11)

The corpus is larger in v0.11, and each rate now carries a deterministic
**Wilson score 95% confidence interval** (`wilson_ci`, a closed-form function of
the counts — no randomness), so a "0.0 miss rate" over a small sample is honestly
reported as, say, `[0.0, 0.22]` rather than as certainty. The whole corpus is also
re-run under **each policy mode** (`per_policy`), because the detectors use policy
thresholds: a lower `coercion_moderate` flags more borderline cases, so the
coercion **false-alarm rate rises under stricter policies** — exactly the
sensitivity/precision trade-off a maintainer needs to see. Verdict accuracy is
reported only against each entry's own policy (the verdict is policy-dependent by
design). Everything is pinned by the scoring golden file
(`tests/golden/scoring_corpus.golden.json`). `littleboy calibrate --scope scoring`:

```text
CALIBRATION (scoring): verdict_accuracy=1.00 (21/21)
  coercion: miss_rate=0.00  false_alarm_rate=0.00  (n=21)
  data_sufficiency: miss_rate=0.00  false_alarm_rate=0.00  (n=21)
  temporal: miss_rate=0.00  false_alarm_rate=0.00  (n=5)
```

Changing a coercion or temporal threshold now moves a measurable number: a wrong
change shows up as a miss or false alarm on the relevant layer (with shifted
confidence intervals and per-policy rates), or as a verdict mismatch, and fails the
golden test.

### Independently-labelled corpus at scale (v0.12)

The packaged corpus is small and its labels were written by the same hands as the
heuristics. To calibrate *at scale* with **independent** labels, `generate_scoring_corpus`
synthesises many cases from latent parameters and labels each **from those latent
parameters, never from the evaluator**: a latent severity `s` gives ground-truth
`coercive = s >= 0.5`; a latent adequacy `d` gives `adequate_data = d >= 0.5`. The
observed coercion and data profiles are built from `s`/`d`, and the heuristic
detectors then predict over them — so agreement is a genuine measurement, not a
tautology. Generation is fully deterministic given the seed (a fixed
`random.Random(seed)`), so nothing is stored on disk and the corpus is
reproducible.

On the default generated corpus (n=120, seed=0) the coercion detector shows a
**false-alarm rate around 0.43** against the latent labels — it flags "coercive"
far more readily than the `s >= 0.5` definition (by design, the engine leans toward
flagging coercion) — while data-sufficiency shows a **miss rate around 0.20**.
These are exactly the kind of honest, quantified findings a small hand-labelled
corpus cannot give. Each rate carries its Wilson interval, and the intervals
**tighten as n grows** (`width ~ 1/sqrt(n)`): the coercion false-alarm interval is
~0.38 wide at n=40 and ~0.16 wide at n=320. A golden file
(`tests/golden/scoring_generated.golden.json`) pins the n=120/seed=0 metrics, so
heuristic drift is caught at scale too.

```bash
littleboy calibrate --scope scoring --generated --n 200    # large, independently-labelled run
```

### External-validity reliability (v0.13)

The scoring corpora measure whether each *layer* behaves as labelled. The strongest
honest check is different: how often does the engine's **verdict** agree with an
*independent human judgment*? A small `OutcomeCorpus` carries verdict labels
authored by a human panel — **not** derived from the heuristics — split into
`dev` (where thresholds may be tuned) and `holdout` (reported, never tuned
against). `run_reliability` computes, **per policy and per split**, how often the
engine's verdict matches the human label, both *exactly* and on a coarser
**disposition** (permissible / impermissible / insufficient), each with a Wilson
interval, and lists every disagreement.

This surfaces *which policy tracks human judgment best*: on the packaged holdout
set, `standard` agrees ~0.88 of the time, while `precautionary` agrees only ~0.25
(it is far more conservative than the panel) — a real, measured, sub-1.0
reliability with honestly wide intervals (the corpus is small). The result is
golden-pinned (`tests/golden/outcome_reliability.golden.json`).

```bash
littleboy calibrate --scope reliability    # per-policy agreement with held-out human labels
```

### Independent labelling at scale + policy recommendation (v0.14)

A single human label hides a hard truth: **people disagree about ethics**, and a
reliability number is only meaningful next to *how much the labelers agreed with
each other*. v0.14 grows the held-out outcome set an order of magnitude — to **160
cases**, each judged by a **panel of three independent labelers** — and reports
inter-labeller agreement alongside per-policy reliability.

**Independent labelers.** Each labeler is a *different, transparent* judgment rule
over the observable case (coercion severity, data adequacy, consent), authored
separately from the engine and from one another: a `lenient` persona that only
condemns severe coercion, a `median` persona, and a `strict` persona that condemns
much earlier. They genuinely disagree on borderline cases. The panel's majority is
the **consensus** (`human_verdict`); each persona's raw verdict is kept in `labels`
so agreement can be measured. Generation is deterministic given the seed
(`generate_outcome_corpus`, `default_labelled_outcome_corpus`), so the corpus is
reproducible without storing 160 cases on disk.

**Inter-labeller agreement is the ceiling.** `inter_rater_agreement` computes, on
the coarse disposition classes, the mean **pairwise percent agreement** and
**Fleiss' kappa** (chance-corrected). On the holdout set the three labelers agree
only ~**0.68** of the time (kappa ~**0.37** — "fair"). That is the ceiling: *no
policy can be expected to match the consensus more often than the labelers match
one another*, so a policy reporting 0.92 disposition agreement is doing well
**relative to a noisy target**, not approaching perfection. The ceiling is carried
on every `SplitReliability` (`inter_rater`) and surfaced by `littleboy calibrate
--scope reliability --labelled` (the `--labelled` flag swaps the small packaged
corpus for the large multi-labeller one):

```text
  [holdout] n=80  inter-rater ceiling: agreement=0.68 kappa=0.37
    permissive     exact=0.56 CI[0.45,0.67]  disposition=0.93
    standard       exact=0.54 CI[0.43,0.64]  disposition=0.90
    strict         exact=0.46 CI[0.36,0.57]  disposition=0.82
    precautionary  exact=0.46 CI[0.36,0.57]  disposition=0.74
```

**A policy-recommendation layer.** Different stakeholders want different policies,
and that should be shown, not hidden. `recommend_policy_for_stakeholder(corpus,
labeler=...)` (and `recommend_policy(report)`) takes a stakeholder's held-out
judgments and recommends the policy whose verdicts best match them — by disposition
accuracy by default, or `exact`. Crucially it shows the **trade-offs**: the full
ranking with Wilson intervals, the set of policies whose intervals **overlap the
leader's** (so the data *cannot* separate them — `indistinguishable`), and the
agreement ceiling as an over-fitting caveat. Because the labelers genuinely differ,
the recommendation genuinely diverges by stakeholder:

```text
stakeholder=lenient    -> permissive     acc=0.86   ties with: standard
stakeholder=median     -> permissive     acc=0.92   ties with: standard, strict
stakeholder=strict     -> precautionary  acc=1.00   ties with: strict
stakeholder=consensus  -> permissive     acc=0.92   ties with: standard, strict
```

A lenient stakeholder is best served by `permissive`; a strict stakeholder by
`precautionary` (a perfect match — because the strict persona and the precautionary
policy condemn at similar coercion levels). The trade-off is explicit: choosing
`precautionary` to satisfy the strict stakeholder would drop consensus disposition
agreement from 0.92 to 0.74. The recommendation is golden-pinned
(`tests/golden/labelled_outcome_reliability.golden.json`).

```bash
littleboy calibrate --scope reliability --labelled        # 160-case panel + inter-rater ceiling
littleboy recommend-policy --stakeholder strict           # best policy for one stakeholder
littleboy recommend-policy --stakeholder lenient --metric exact
littleboy recommend-policy                                 # against panel consensus
```

### Real labels from CSV + a fitted-threshold recommender (v0.15)

The persona panel is a stand-in. Two v0.15 additions take the next step toward
external validity, both **deterministic, stdlib-only, and purely additive**.

**Real, independent labels via CSV.** `littleboy.calibration.labels` imports actual
human verdicts from a `case_id,labeler,verdict[,split]` CSV and overlays them onto
the known cases by id (`outcome_corpus_from_csv`, `apply_labels`, `parse_labels_csv`,
`labels_to_csv` for the round-trip / template export). The resulting `OutcomeCorpus`
runs through the **existing** `run_reliability` / `recommend_policy` /
`fit_threshold_policy` **unchanged** — the engine is only ever *measured against* the
labels, never trained on them. The consensus rule is transparent: majority vote,
ties broken toward the **more cautious** reading (when independent judges split
evenly, the consensus should not over-claim permissibility). A round-trip
(`labels_to_csv` → `parse_labels_csv` → `apply_labels`) reproduces per-labeller
reliability exactly, which is the regression test that the import path is faithful.

```bash
littleboy recommend-policy --stakeholder strict --labels-csv my_labels.csv
```

**A fitted-threshold recommender.** Beyond the four coarse built-in policies,
`fit_threshold_policy` searches a deterministic grid of the two coercion thresholds
(`coercion_moderate`, `max_coercion_for_acceptable`) for the set that best matches a
stakeholder — **fitting on the dev split only**, then scoring the chosen thresholds
on the **never-fitted holdout**. A fitted set is turned back into a real
`PolicyProfile` and run through the *real* engine, so no verdict logic is
duplicated. The result is shown **side-by-side with the nearest built-in** so the
gain from fitting is auditable, with confidence intervals on both and the
inter-labeller ceiling as the caveat:

```text
FITTED POLICY for 'strict' (fitted on dev, scored on holdout):
  thresholds: coercion_moderate=0.3 max_coercion_for_acceptable=0.35 (base: standard)
  fitted   1.00 CI[0.95,1.00]   (dev fit 0.97)
  nearest  strict         0.91 CI[0.83,0.96]   gain=+0.09
  - fitting did NOT clearly beat 'strict' on the holdout (1.00 vs 0.91); the
    intervals overlap, so prefer the simpler built-in policy
```

The honest headline: on this corpus fitting gives only a **small holdout gain**
(+0.04 to +0.09) and in **every** case the confidence intervals overlap the nearest
built-in's, so `distinguishable_from_nearest` is `False` and the tool tells you to
**prefer the simpler built-in**. The consensus fit is even more instructive — it
beats `standard` on dev (0.97) but does *worse* on the holdout (0.87 vs 0.93): a
textbook over-fit, surfaced rather than hidden. This is the dev/holdout discipline
doing its job. Pinned by `tests/golden/fitted_policy.golden.json`.

```bash
littleboy recommend-policy --stakeholder strict --fit       # ranking + fitted side-by-side
littleboy recommend-policy --fit                            # fit to the consensus
```

### Cross-validated fitting + a packaged independent set (v0.16)

A single dev/holdout split gives the fitted policy's gain as **one point**, which can
be lucky. v0.16 makes it a **claim with a variance**, and ships a genuinely
independent labelled set to run it all against.

**k-fold cross-validation** (`cross_validate_threshold_policy`). The cases are pooled
into `k` deterministic folds; each fold **fits thresholds on its training part and
scores them — and the nearest built-in — on its held-out part**. The reported gain
is the *procedure's* generalisation: `mean_gain ± gain_std` (plus min/max), a
`fitting_helps` flag that is true only when the mean stays positive one standard
deviation down, and a `threshold_stability` read (how often the same thresholds
won). Internally a verdict matrix is computed once, so CV costs one full grid
evaluation regardless of `k`. The fitter can now also optionally tune the
**data-quality gate** and the **irreversibility floor** (`data_gate_grid`,
`reversibility_grid`), not just the two coercion thresholds.

This is strictly more honest than one holdout: on the large synthetic corpus, the
single-split fit for the `strict` stakeholder reported "intervals overlap, prefer
the built-in", but 5-fold CV shows the gain is in fact **robust** — mean **+0.069 ±
0.054**, positive one σ down, with the modal thresholds (0.30, 0.35) stable across
**all** folds — so `fitting_helps` is `True`. One point hid a real effect; the
spread revealed it. Pinned by `tests/golden/cross_validated_fit.golden.json`.

**A packaged independent labelled set** (`default_independent_outcome_corpus`). The
16 v0.13 cases are relabelled by a **three-person panel** (`ann`, `ben`, `cleo`)
whose verdicts live in `independent_labels.csv` and were **hand-authored as
independent human judgments — written without consulting the engine's output**, and
disagreeing more messily than the rule-based personas. They are imported through the
**v0.15 CSV path** and inherit the v0.13 dev/holdout split (so the holdout is never
inspected during tuning). Their agreement is honestly **lower and messier** than the
synthetic panel — dev percent agreement ~0.54 (Fleiss kappa ~0.15), holdout ~0.67
(kappa ~0.40) — and the existing `run_reliability` / `recommend_policy` /
`fit_threshold_policy` / `cross_validate_threshold_policy` all run against it
**unchanged**. On this small set, fitting buys **nothing** over the nearest built-in
(CV mean gain ~0.00), which is exactly what a tiny, noisy holdout should report.

```bash
littleboy recommend-policy --stakeholder strict --cv --folds 5   # gain as mean +/- spread
littleboy recommend-policy --independent                         # against the independent panel
littleboy recommend-policy --independent --cv                    # both together
```

### Calibrated inference + a larger external set (v0.17)

The v0.16 `fitting_helps` flag was a rule of thumb (mean gain minus one standard
deviation). v0.17 replaces the heuristic with **real statistical inference**, and
grows the external set so the inference has something to bite on. Everything is
stdlib-only and exact (`calibration/stats.py` implements the Student-t CDF from the
regularised incomplete beta by continued fraction, tested against closed forms).

**The corrected resampled t-test.** CV fold gains are *not* independent — every
fold shares most of its training data with every other — so a naive t-test over
fold gains is overconfident. `cv_gain_inference` runs **repeated, stratified
k-fold CV** (folds balanced by disposition class, a different deterministic
partition per repetition) and applies the **Nadeau–Bengio correction**: the
variance is `s² · (1/m + 1/(k−1))`, whose `1/(k−1)` train/test-overlap term means
**repeating CV cannot manufacture confidence** (the standard error is floored at
`s/√(k−1)`, a property under test). The result is a mean gain over the nearest
built-in with a **95% confidence interval and a real p-value**. The
assumption-light cross-check is an **exact sign test** over paired out-of-fold
predictions: among cases where exactly one side was right, the p-value is an exact
binomial tail. `fitting_helps` is now `p < alpha` *and* a positive mean.

On the synthetic 160-case panel, the `strict`-stakeholder gain that v0.16 could
only call "robust" now carries numbers: **mean +0.069, 95% CI [+0.029, +0.108],
corrected t = 3.49 (df = 49), p = 0.0010**, with the sign test agreeing
(fitted-only correct 11, nearest-only 0, p = 0.0010). And the interval **tightens
as n grows**, turning non-significance into significance honestly:

| n (cases) | mean gain | 95% CI | width | p |
|-----------|-----------|--------|-------|------|
| 40 | +0.050 | [−0.015, +0.115] | 0.129 | 0.126 |
| 80 | +0.050 | [+0.004, +0.096] | 0.091 | 0.033 |
| 160 | +0.069 | [+0.029, +0.108] | 0.079 | 0.001 |

**A larger external set: 40 diverse cases × 5 labellers.** The 16-case v0.16 set
was too small for inference. `external_case_bank` deterministically generates **40
cases that vary every axis a human judge weighs** (severity, data adequacy,
consent, reversibility, evidence presence — so "insufficient data" is a live
option), each carrying its salient facts in its description for auditability. The
labels in `external_labels.csv` were **hand-authored per case against those facts**
by five labellers with different temperaments (mainstream / severity-driven /
epistemically-demanding / lenient-under-consent / consent-protective) — written
without consulting the engine's output and not computed by any rule in this
codebase. Their agreement is genuinely messy (dev percent agreement ~0.56, Fleiss
kappa ~0.28; holdout ~0.73, kappa ~0.53), and policy reliabilities are far lower
than on the easy fully-specified panel (holdout disposition 0.40–0.85, `permissive`
leading). On this set the inference reports **mean gain −0.020, p = 0.41** —
fitting does **not** demonstrably beat the nearest built-in here, and now that's a
calibrated statement, not a hunch. Pinned by
`tests/golden/cv_gain_inference.golden.json`.

```bash
littleboy recommend-policy --stakeholder strict --inference      # p-value on the fitting gain
littleboy recommend-policy --external                            # the 40-case x 5-labeller set
littleboy recommend-policy --external --inference --repeats 10   # both together
```

### Case-level disagreement explanations (v0.18)

A reliability table says *how often* the engine disagrees with a labeller. v0.18
says **why, case by case**: every opaque `disagreements` entry becomes an
inspectable `DisagreementExplanation`, built on the existing `ReasoningTrace` (it
re-derives nothing) and evaluation-only (no verdict changes).

**Policy-vs-policy: a true trace diff + the minimal parameter account.** Both
sides are engine evaluations, so the divergence can be pinned exactly:

- **rule deltas** (`TraceDelta`) — rules whose *outcome* changed (status, severity,
  blocker, verdict effect), e.g. `LB-R002: failed/blocker -> passed/warning`;
- **threshold flips** (`ThresholdFlip`) — the coercion / data-quality / evidence
  scores are computed *before* any policy applies, so when the same score crosses a
  limit under one policy only, that is the parametric mechanism:
  `coercion_score=0.65 vs max_coercion_for_acceptable: 0.6 (crossed) -> 0.75 (not crossed)`;
- the **minimal parameter account** (`minimal_policy_accounts`) — the rigorous
  part: the smallest set(s) of policy parameters that, moved from side A's values
  to side B's, make the engine actually produce side B's verdict. Every candidate
  hybrid profile is **re-evaluated through the real engine** (nothing inferred from
  the trace), and the search proceeds by increasing size, so every returned set is
  provably minimal — the policy-parameter analogue of the deliberation layer's
  minimal flip sets.

**Engine-vs-label: decisive factors + the bridge.** The human side has no trace,
so the honest explanation is: the engine's **decisive factors** (blockers, caps,
downgrades, the data gate — straight from the trace), **which built-in policies
agree** with the label (exactly, or on disposition), and the parameter account
toward the **nearest agreeing policy** (the *bridge*). Every diagnosis is specific:

```text
DISAGREEMENT ext-0007: engine[standard] = INSUFFICIENT_DATA  vs  label[consensus] = NOT_ACCEPTABLE
  decisive (side A):
    - LB-R004 Data Quality Rule [blocker]: Epistemic basis 0.27 is below the policy minimum 0.35.
  bridge policy: permissive
  minimal parameter account(s) (verified by re-evaluation):
    - min_data_quality_for_approval: 0.35 -> 0.25
```

— the engine declined for data reasons; the panel condemned; lowering the data
gate (one parameter) aligns them. When no single account exists the explanation
says which kind of impasse it is: a **within-disposition** disagreement ("the
difference is in degree, not in kind"), or **no built-in policy agrees even on
disposition** ("this disagreement is not a threshold question within the built-in
policy family") — the cases worth a human look, now separable from mere threshold
quibbles. `explain_reliability_disagreements` yields exactly one explanation per
reliability-table disagreement (a test pins the counts), and everything is
golden-pinned (`tests/golden/disagreement_explanation.golden.json`).

```bash
littleboy explain-disagreement ext-0007 --external --against consensus    # engine vs the panel
littleboy explain-disagreement ext-0004 --external --against hana         # engine vs one labeller
littleboy explain-disagreement case.json --against precautionary          # policy vs policy on any case
littleboy explain-disagreement --all --external --against hana            # every disagreement, one line each
```

### Fact accounts & the unified explanation (v0.19)

v0.18 explained engine-vs-labeller gaps through one lens: which *policy* change
would align the engine. But a disagreement can have a second, entirely different
explanation: maybe the labeller **knows (or assumes) a fact the case leaves
unknown**. v0.19 adds the **fact route** and unifies the two.

**Minimal fact accounts** (`minimal_fact_accounts`). The case's genuine unknowns
and their candidate resolutions come from the deliberation layer's existing probes
(`build_probe_specs` — the same composable `case -> case` transforms behind value
of information and minimal flip sets). The search is the *targeted* counterpart of
a minimal flip set: instead of flipping to any other verdict, the joint resolution
must make the engine produce **the labeller's verdict exactly**. Increasing-size
search, every candidate re-evaluated through the real engine, so each account is
verified and provably minimal — e.g. `consent = REFUSED`, or `long-term
consequences are worse than described`.

**The unified explanation.** Every engine-vs-labeller disagreement now carries a
`bridge_classification` naming which engine-verified routes to agreement exist:

- **`policy-bridgeable`** — some built-in policy reproduces the label exactly (the
  parameter account shows the smallest change);
- **`fact-bridgeable`** — resolving the case's unknowns reaches the label (the
  labeller may know something the case does not state);
- **`both`** — genuinely ambiguous between values and facts. The packaged
  independent set has a textbook case: `policy_strict_borderline` vs `cleo`
  (engine: acceptable-with-reservations; cleo: ethically suspicious) — *either*
  treat unknown consent as a blocker (`unknown_consent_is_blocker: False -> True`,
  the policy route) *or* learn that consent was refused (`consent = REFUSED`, the
  fact route). The explanation says so and adds: which is right depends on whether
  the labeller weighs values differently or knows something the case does not
  state;
- **`neither`** — no parameter and no fact resolution (within search limits)
  aligns the engine: flagged as **worth a human look**. On the external set vs the
  consensus, 17 of 21 disagreements are `neither` — mostly cases where the panel
  condemned on data the engine refuses to judge: a real normative difference, now
  separated from threshold quibbles and fact gaps.

The `--all` summary classifies every line and prints a tally
(`classification tally: fact-bridgeable: 5  neither: 17  policy-bridgeable: 3`),
so a reliability table's disagreements decompose at a glance into *policy
questions*, *fact questions*, and *genuine divergence*.

```bash
littleboy explain-disagreement policy_strict_borderline --independent --against cleo   # a 'both' case
littleboy explain-disagreement ext-0034 --external --against consensus                 # a fact-bridgeable case
littleboy explain-disagreement --all --external --against hana                         # tally at the end
```

### The corpus-level diagnosis report (v0.20)

The per-case explanations answer "why this case?"; `diagnose_disagreements`
answers **"where does the disagreement with this labeller come from, overall?"**
— one auditable report per (labeller × policy), a deterministic aggregation of
the engine-verified per-case explanations (nothing new is inferred, and the
per-case classification index is included so every number drills back down).

The report decomposes the disagreement into its **kinds**, each fraction with a
Wilson interval: threshold questions (`policy-bridgeable`), epistemic questions
(`fact-bridgeable`), ambiguous (`both`), and genuine divergence (`neither`). It
then ranks the **recurring bridging parameters and facts** — a parameter or fact
counts once per disagreement it bridges — and turns them into a concrete
**tuning agenda**:

```text
DIAGNOSIS: engine[standard] vs hana (n=40)
  agreement: 15/40 = 0.38  CI[0.24,0.53]   (inter-labeller ceiling: 0.64)
  disagreement breakdown (n=25):
    policy-bridgeable    3/25 = 0.12  CI[0.04,0.30]
    fact-bridgeable      5/25 = 0.20  CI[0.09,0.39]
    both                 0/25 = 0.00  CI[0.00,0.13]
    neither             17/25 = 0.68  CI[0.48,0.83]
  tuning agenda:
    1. policy: 'min_data_quality_for_approval' bridges 4/25 disagreement(s) (ext-0007, ...)
    2. policy: 'min_confidence' bridges 2/25 disagreement(s) (ext-0014, ext-0027)
    4. facts: establishing 'long-term consequences are worse than described' aligns 4/25 ...
    6. review: 17/25 disagreement(s) are genuine divergence (...) -- candidates for human review
```

The reading is direct: hana's divergence from the engine is **mostly genuine**
(0.68 of it, CI [0.48, 0.83] — largely the panel condemning on data the engine
refuses to judge), a quarter is **the data gate and consequence unknowns** (one
parameter bridges 4 cases; one fact 4 more), and almost none is the coercion
thresholds. A reliability number became a work list. The diagnosis agreement is
the *same measurement* as the reliability table's exact accuracy (a test pins
them equal), and the whole report is golden-pinned
(`tests/golden/disagreement_diagnosis.golden.json`).

```bash
littleboy diagnose --external --against hana              # the full report
littleboy diagnose --external                             # vs the panel consensus
littleboy diagnose --external --against hana --split holdout --format json
```

### The dry-run tuner (v0.21)

The diagnosis ends in a tuning agenda; `tune_dry_run` closes the loop from agenda
to **decision** — without ever touching the built-in profiles. Given a base policy
and parameter overrides (validated and coerced through `PolicyProfile` itself, so
garbage is rejected exactly as it would be anywhere else), it reports the full
before/after impact with **nothing silent**:

- **every verdict flip**, with its direction (`gains a verdict`, `declines to
  insufficient data`, `more`/`less permissive`) and a transition summary;
- **agreement with every labeller and the consensus**, per split, before vs after,
  each with Wilson intervals and deltas — so the cost to one stakeholder of
  pleasing another is on the table;
- **which golden files would break** if the change were adopted, each checked by
  *recomputation* over its underlying packaged corpus (verdict flips for the
  outcome-backed goldens; verdict-or-detector-band changes for the scoring
  goldens; full audit-output comparison for the audit golden, which reads
  `coercion_moderate`) — or honestly marked `unchecked` where the golden depends
  on non-packaged data.

The flagship example — the diagnosis's top agenda item,
`min_data_quality_for_approval: 0.35 -> 0.25` on the external set:

```text
TUNE (dry run): 'standard' + 1 change(s) on n=40
  verdict flips: 3/40   (all: INSUFFICIENT_DATA -> NOT_ACCEPTABLE, "gains a verdict")
  stakeholder agreement (exact, before -> after):
    emil  holdout  0.35 -> 0.45 (+0.10)   <- gains
    fay   holdout  0.50 -> 0.40 (-0.10)   <- loses
  net deltas: consensus +0.050  emil +0.075  fay -0.075  hana +0.050 ...
  golden impact: WOULD BREAK cv_gain_inference, disagreement_diagnosis, scoring_generated
```

The decision picture is complete: the change pleases emil, hana and the consensus,
**costs fay** (the epistemically-demanding labeller who endorsed the engine's
refusals) exactly what it gains emil, and would require regenerating three named
golden files deliberately. The report says so itself: *an improvement in agreement
is not by itself a justification — a gate that declines to judge on poor data may
be doing its epistemic job.* Dryness is under test: `DEFAULT_PROFILES` and every
verdict under the built-ins are asserted unchanged after a run. Pinned by
`tests/golden/tuning_impact.golden.json`.

```bash
littleboy tune --set min_data_quality_for_approval=0.25 --external      # the full impact
littleboy tune --set coercion_moderate=0.2 --base strict --independent  # any base, any corpus
littleboy tune --set min_confidence=0.2 --external --no-goldens --format json
littleboy tune --set min_data_quality_for_approval=0.25 --external \
  --save my_policy.json --name research_gate_025      # v0.22: adopt as a named policy file
```

A vetted candidate can be **saved as a named policy** (v0.22): `--save` writes a
`NamedPolicy` JSON (profile + clock-free provenance: base, exact changes,
description) with the full tuning-impact report alongside
(`<stem>.impact.json`), and every `--policy` option then accepts the file —
reports carry the custom name (`policy_label`) so it is never mistaken for a
built-in. And the calibration suite treats it as a first-class subject (v0.23):
`calibrate --scope reliability --with-policy my_policy.json` and
`recommend-policy --with-policy ...` add it as a row/candidate under its own
name, `diagnose`/`explain-disagreement` carry the name in their reports, and a
loaded file's provenance is **verified against its profile** (tampering warned
loudly, never silently trusted). See
[`docs/POLICY_PROFILES.md`](POLICY_PROFILES.md).

## Limitations

- The **audit corpus** is small and hand-labelled: its rates are calibration
  indicators over a curated set, not population statistics.
- The **generated corpus** gives labels independent of the heuristics, but they are
  still *synthetic* — drawn from a latent model the maintainers chose, not from the
  real world. It measures whether the heuristics recover that latent model, which
  is a strong internal check but not external validity.
- The **outcome (reliability) corpus** is the closest to external validity. v0.14
  grows it to 160 cases with a three-labeler panel and reports inter-labeller
  agreement, so the reliability intervals are now read against an honest ceiling
  (holdout agreement ~0.68, Fleiss kappa ~0.37). v0.15 adds a CSV import so *real*
  independent labels can be dropped in and run through the same machinery — but the
  *packaged* labels are still **transparent personas authored by the maintainers**,
  not genuinely independent people. They disagree realistically, yet by
  construction. The import path is built and waiting for actual human labels, and
  would report their (likely lower) agreement just the same.
- The **policy recommendation** is only as trustworthy as the labels and the
  ceiling above. It honestly marks policies whose confidence intervals overlap as
  `indistinguishable` (the data cannot separate them) and reports the agreement
  ceiling, so it cannot silently over-claim — but a recommendation tuned to a noisy
  target (kappa ~0.37) is a starting point for deliberation, not a settled answer.
- The **fitted-threshold policy** fits the two coercion thresholds (and, optionally,
  the data-quality gate and irreversibility floor) over a fixed grid, holding every
  other parameter at the base profile's value; it is not a general optimiser.
  **Calibrated inference** (v0.17) gives the fitting gain a corrected-t p-value and
  an exact sign test instead of a rule of thumb — but the Nadeau–Bengio correction
  is itself an approximation (the exact CV variance is unidentifiable), the sign
  test conditions on disagreements, and a significant gain is still bounded by the
  inter-labeller ceiling, not a licence to chase the labels.
- The **external labelled set** (v0.17: 40 diverse cases × 5 labellers, alongside
  the 16-case v0.16 set) is the most honest data here, imported through the same
  CSV path real labels would use — but its labels, while hand-authored per case
  *without consulting the engine's output*, were still written by the maintainers,
  not collected from genuinely unrelated people. Genuine external validity needs
  exactly that collection step; the machinery (CSV import, inter-rater agreement,
  reliability, recommendation, fitting, inference) is all in place, waiting for it.
- The **disagreement explanations** (v0.18/v0.19) explain the *engine's* side
  fully (its trace is complete), but the human side only indirectly — via which
  policy change or which fact resolution would bridge the gap. A `neither`
  classification means the label is unreachable by threshold moves or by
  resolving the case's *modelled* unknowns; it does not say *why the human judged
  as they did*. The parameter account is relative to the exposed
  parameterisation, and the fact account is relative to the probe vocabulary —
  a divergence could rest on a consideration neither captures. Both searches are
  also size-capped, so "no account" means "no small account".
- The **diagnosis report** (v0.20) inherits all of the above: its fractions and
  agenda are only as good as the per-case classifications beneath them, the
  Wilson intervals are wide on small disagreement counts (the report shows
  them), and a "tuning agenda" is an *agenda*, not a recommendation — bridging a
  labeller by loosening the data gate may be exactly the wrong move if the gate
  is doing its epistemic job. The numbers say where alignment is cheap, not
  where it is right.
- The **dry-run tuner** (v0.21) measures impact on the corpora it is given and
  on the packaged golden corpora — not on the world. Its golden checks are by
  recomputation but at the granularity stated in each reason (verdict flips,
  detector bands, audit dumps); fitting goldens derive candidate grids from the
  base profile, so a base change can affect them even without verdict flips
  (the report says so, and defers to pytest for certainty). And the same caveat
  as the agenda, doubled: the tuner shows the complete cost ledger of a change;
  it does not — and cannot — say whether the change is *right*.
- Golden-file pinning catches drift but does not *validate* correctness — a wrong
  expectation, once frozen, stays wrong until a human revisits it.
- The scoring-layer detectors are deliberately coarse (a coercion band, the data
  gate, a rising trend); they measure agreement with the labels, not whether the
  heuristic is well-calibrated against real outcomes.
