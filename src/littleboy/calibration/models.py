"""Typed models for the adversarial calibration corpus (v0.9).

A *calibration corpus* is a labelled set of cases — both adversarial (where audit
red flags *should* fire) and clean (where they should *not*) — together with the
findings each case is expected to raise. Running the corpus produces a
:class:`CalibrationReport` with two headline numbers a maintainer can tune
against: the **miss rate** (expected adversarial flags that did not fire) and the
**false-alarm rate** (clean cases that nonetheless raised a red flag). Golden-file
regression tests pin the per-case digests so that any drift in the audit's
behaviour is caught.

Cases are stored inline so the corpus is self-contained and deterministic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.models import ActionCase


class _CalBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpusEntry(_CalBase):
    """One labelled case in the calibration corpus."""

    id: str
    label: str = Field(description="'adversarial' (flags expected) or 'clean' (no red flags).")
    description: str = ""
    case: ActionCase
    policy: str = "standard"
    expect_findings: list[str] = Field(
        default_factory=list,
        description="finding_ids that SHOULD be present (a miss if absent).",
    )
    forbid_findings: list[str] = Field(
        default_factory=list,
        description="finding_ids that must NOT be present (a false alarm if present).",
    )
    expect_judgment_stable: bool | None = Field(
        default=None, description="Expected audit stability, or None to not check."
    )


class AuditCorpus(_CalBase):
    """A labelled corpus of cases for calibrating the adversarial audit."""

    title: str = ""
    description: str = ""
    entries: list[CorpusEntry] = Field(default_factory=list)


class CaseDigest(_CalBase):
    """A deterministic digest of one case's audit, pinned by golden-file tests."""

    id: str
    label: str
    judgment_stable: bool
    red_flags: list[str] = Field(default_factory=list)
    all_findings: list[str] = Field(default_factory=list)
    max_severity: str = "info"
    adversarial_max_risk: float = 0.0
    bias_max_risk: float = 0.0


class CalibrationOutcome(_CalBase):
    """How one corpus entry scored against its expectations."""

    id: str
    label: str
    passed: bool
    missing_expected: list[str] = Field(default_factory=list)
    false_alarms: list[str] = Field(default_factory=list)
    stability_ok: bool = True


class CalibrationReport(_CalBase):
    """Aggregate calibration result over the whole corpus."""

    n_cases: int = 0
    n_adversarial: int = 0
    n_clean: int = 0
    n_passed: int = 0
    miss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    false_alarm_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    outcomes: list[CalibrationOutcome] = Field(default_factory=list)
    digests: list[CaseDigest] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
