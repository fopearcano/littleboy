"""Loading and running the adversarial calibration corpus.

``run_corpus`` audits every entry with the :class:`AdversarialStressTester`,
builds a deterministic :class:`CaseDigest` for each (pinned by golden-file tests),
and aggregates the miss / false-alarm metrics. The default corpus is shipped as a
self-contained JSON resource inside the package so ``littleboy calibrate`` works
anywhere.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from littleboy.audit.models import AuditReport, AuditSeverity, severity_rank
from littleboy.audit.stress import AdversarialStressTester
from littleboy.calibration.metrics import aggregate, score_entry
from littleboy.calibration.models import (
    AuditCorpus,
    CalibrationReport,
    CaseDigest,
)

_DEFAULT_RESOURCE = "audit_corpus.json"
_SERIOUS = severity_rank(AuditSeverity.SERIOUS)


def load_corpus(path: str | Path) -> AuditCorpus:
    """Load a corpus from a JSON file."""
    return AuditCorpus.model_validate_json(Path(path).read_text(encoding="utf-8"))


def default_corpus() -> AuditCorpus:
    """Load the packaged default calibration corpus."""
    text = (
        resources.files("littleboy.calibration")
        .joinpath(_DEFAULT_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return AuditCorpus.model_validate_json(text)


def _digest(entry_id: str, label: str, audit: AuditReport) -> CaseDigest:
    all_ids = sorted({f.finding_id for f in audit.findings})
    red_ids = sorted(
        {f.finding_id for f in audit.findings if severity_rank(f.severity) >= _SERIOUS}
    )
    return CaseDigest(
        id=entry_id,
        label=label,
        judgment_stable=audit.judgment_stable,
        red_flags=red_ids,
        all_findings=all_ids,
        max_severity=audit.max_severity.value,
        adversarial_max_risk=audit.adversarial_risk_profile.max_risk,
        bias_max_risk=audit.bias_profile.max_risk,
    )


def run_corpus(corpus: AuditCorpus) -> CalibrationReport:
    """Audit every entry and return the aggregate calibration report."""
    outcomes = []
    digests = []
    for entry in corpus.entries:
        audit = AdversarialStressTester(entry.policy).audit_case(entry.case)
        all_ids = {f.finding_id for f in audit.findings}
        red_ids = {f.finding_id for f in audit.findings if severity_rank(f.severity) >= _SERIOUS}
        outcomes.append(
            score_entry(
                entry,
                all_finding_ids=all_ids,
                red_flag_ids=red_ids,
                judgment_stable=audit.judgment_stable,
            )
        )
        digests.append(_digest(entry.id, entry.label, audit))
    return aggregate(corpus, outcomes, digests)


def golden_payload(report: CalibrationReport) -> dict:
    """The stable subset of a report compared by golden-file regression tests."""
    return {
        "n_cases": report.n_cases,
        "n_adversarial": report.n_adversarial,
        "n_clean": report.n_clean,
        "n_passed": report.n_passed,
        "miss_rate": report.miss_rate,
        "false_alarm_rate": report.false_alarm_rate,
        "digests": [d.model_dump(mode="json") for d in report.digests],
    }
