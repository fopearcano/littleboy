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
  (holdout agreement ~0.68, Fleiss kappa ~0.37). But the "labelers" are still
  *transparent personas authored by the maintainers*, not genuinely independent
  people — they disagree realistically, yet by construction. A real external check
  still needs labels from actual independent humans; the inter-rater machinery is
  built and waiting for them, and would report their (likely lower) agreement just
  the same.
- The **policy recommendation** is only as trustworthy as the labels and the
  ceiling above. It honestly marks policies whose confidence intervals overlap as
  `indistinguishable` (the data cannot separate them) and reports the agreement
  ceiling, so it cannot silently over-claim — but a recommendation tuned to a noisy
  target (kappa ~0.37) is a starting point for deliberation, not a settled answer.
- Golden-file pinning catches drift but does not *validate* correctness — a wrong
  expectation, once frozen, stays wrong until a human revisits it.
- The scoring-layer detectors are deliberately coarse (a coercion band, the data
  gate, a rising trend); they measure agreement with the labels, not whether the
  heuristic is well-calibrated against real outcomes.
