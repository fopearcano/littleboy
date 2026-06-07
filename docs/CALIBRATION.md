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

## Limitations

- The **audit corpus** is small and hand-labelled: its rates are calibration
  indicators over a curated set, not population statistics.
- The **generated corpus** gives labels independent of the heuristics, but they are
  still *synthetic* — drawn from a latent model the maintainers chose, not from the
  real world. It measures whether the heuristics recover that latent model, which
  is a strong internal check but not external validity.
- Golden-file pinning catches drift but does not *validate* correctness — a wrong
  expectation, once frozen, stays wrong until a human revisits it.
- The scoring-layer detectors are deliberately coarse (a coercion band, the data
  gate, a rising trend); they measure agreement with the labels, not whether the
  heuristic is well-calibrated against real outcomes.
