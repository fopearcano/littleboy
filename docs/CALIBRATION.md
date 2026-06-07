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
littleboy calibrate                         # run the packaged corpus
littleboy calibrate my_corpus.json --format json
```

## Limitations

- The corpus is **small and hand-labelled**: the rates are calibration indicators
  over a curated set, not population statistics, and the labels encode the
  maintainers' judgement of what *should* fire.
- Golden-file pinning catches drift but does not *validate* correctness — a wrong
  expectation, once frozen, stays wrong until a human revisits it.
- Calibration measures the **audit's** behaviour; it does not calibrate the
  coercion, evidence, or temporal heuristics, which would need their own labelled
  corpora.
