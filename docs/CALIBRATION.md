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
- Golden-file pinning catches drift but does not *validate* correctness — a wrong
  expectation, once frozen, stays wrong until a human revisits it.
- The scoring-layer detectors are deliberately coarse (a coercion band, the data
  gate, a rising trend); they measure agreement with the labels, not whether the
  heuristic is well-calibrated against real outcomes.
