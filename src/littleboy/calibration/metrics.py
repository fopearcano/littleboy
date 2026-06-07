"""Scoring a calibration corpus: per-entry outcomes and aggregate miss/false-alarm rates.

These metrics are the levers a maintainer tunes against. The **miss rate** is the
fraction of expected adversarial findings that failed to fire; the
**false-alarm rate** is the fraction of clean cases that nonetheless raised a red
flag. Lowering one usually raises the other, so they are reported together.
"""

from __future__ import annotations

from littleboy.calibration.models import (
    AuditCorpus,
    CalibrationOutcome,
    CalibrationReport,
    CaseDigest,
    CorpusEntry,
)

_ADVERSARIAL = "adversarial"
_CLEAN = "clean"


def score_entry(
    entry: CorpusEntry,
    *,
    all_finding_ids: set[str],
    red_flag_ids: set[str],
    judgment_stable: bool,
) -> CalibrationOutcome:
    """Score one entry against its expectations."""
    missing_expected = [f for f in entry.expect_findings if f not in all_finding_ids]
    false_alarms = [f for f in entry.forbid_findings if f in all_finding_ids]

    # A clean case that raises any red flag (serious/critical) is a false alarm,
    # unless that finding is explicitly expected for this entry.
    if entry.label == _CLEAN:
        for fid in sorted(red_flag_ids):
            if fid not in entry.expect_findings and fid not in false_alarms:
                false_alarms.append(fid)

    stability_ok = (
        entry.expect_judgment_stable is None or judgment_stable == entry.expect_judgment_stable
    )
    passed = not missing_expected and not false_alarms and stability_ok
    return CalibrationOutcome(
        id=entry.id,
        label=entry.label,
        passed=passed,
        missing_expected=missing_expected,
        false_alarms=false_alarms,
        stability_ok=stability_ok,
    )


def aggregate(
    corpus: AuditCorpus,
    outcomes: list[CalibrationOutcome],
    digests: list[CaseDigest],
) -> CalibrationReport:
    """Combine per-entry outcomes into the aggregate calibration report."""
    n_adversarial = sum(1 for e in corpus.entries if e.label == _ADVERSARIAL)
    n_clean = sum(1 for e in corpus.entries if e.label == _CLEAN)

    total_expected = sum(len(e.expect_findings) for e in corpus.entries)
    total_missed = sum(len(o.missing_expected) for o in outcomes)
    miss_rate = round(total_missed / total_expected, 4) if total_expected else 0.0

    clean_outcomes = [o for o in outcomes if o.label == _CLEAN]
    clean_with_alarm = sum(1 for o in clean_outcomes if o.false_alarms)
    false_alarm_rate = round(clean_with_alarm / n_clean, 4) if n_clean else 0.0

    n_passed = sum(1 for o in outcomes if o.passed)
    notes = [
        "miss_rate = expected adversarial findings that did not fire, over all expected findings",
        "false_alarm_rate = clean cases that raised a red flag, over all clean cases",
        "these are calibration indicators over a small corpus, not population statistics",
    ]
    return CalibrationReport(
        n_cases=len(corpus.entries),
        n_adversarial=n_adversarial,
        n_clean=n_clean,
        n_passed=n_passed,
        miss_rate=miss_rate,
        false_alarm_rate=false_alarm_rate,
        outcomes=outcomes,
        digests=digests,
        notes=notes,
    )
