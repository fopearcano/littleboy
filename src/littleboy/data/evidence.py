"""Structured evidence handling for LittleBoy.

Data quality (:mod:`littleboy.data.quality`) asks *how good is the information
overall?*. Evidence handling asks the sharper question: *what specific claims
are we relying on, where did each come from, and how well is each supported?*

An :class:`EvidenceSet` is a collection of :class:`EvidenceItem` s. From it we
can derive an overall evidence score and, crucially, surface which claims are
*contested* (actively disputed) and which are *unsupported* (asserted on weak or
unknown sourcing). All scoring here is a transparent, documented heuristic.

This module deliberately depends only on :mod:`littleboy.core.enums` so that the
core models can embed an ``EvidenceSet`` without creating an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import SourceType

# A reliability prior for each kind of source. These are starting points, not
# verdicts: a document can still be unreliable, a rumour occasionally right.
_SOURCE_PRIOR: dict[SourceType, float] = {
    SourceType.DIRECT_OBSERVATION: 1.0,
    SourceType.DOCUMENT: 0.9,
    SourceType.EXPERT_REPORT: 0.9,
    SourceType.LEGAL_SOURCE: 0.9,
    SourceType.MEDICAL_SOURCE: 0.9,
    SourceType.TESTIMONY: 0.7,
    SourceType.USER_STATEMENT: 0.6,
    SourceType.UNKNOWN: 0.4,
}

# A contested item's score is multiplied by this (its support is in doubt).
_CONTESTED_PENALTY = 0.6

# Items scoring below this are treated as effectively "unsupported".
_UNSUPPORTED_SCORE_THRESHOLD = 0.34


class _EvidenceBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceItem(_EvidenceBase):
    """A single claim together with how well it is evidenced."""

    claim: str = Field(description="The proposition this item supports.")
    source_type: SourceType = Field(
        default=SourceType.UNKNOWN, description="Where the claim comes from."
    )
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    specificity: float = Field(default=0.5, ge=0.0, le=1.0)
    recency: float = Field(default=0.5, ge=0.0, le=1.0)
    corroboration: float = Field(default=0.5, ge=0.0, le=1.0)
    contested: bool = Field(default=False, description="True if the claim is actively disputed.")
    notes: str = ""

    @property
    def source_prior(self) -> float:
        return _SOURCE_PRIOR.get(self.source_type, 0.4)

    @property
    def score(self) -> float:
        """A transparent 0..1 support score for this single item.

        ``mean(reliability, specificity, recency, corroboration)`` scaled by the
        source prior and a penalty if the claim is contested.
        """
        axes = (self.reliability, self.specificity, self.recency, self.corroboration)
        base = sum(axes) / len(axes)
        penalty = _CONTESTED_PENALTY if self.contested else 1.0
        return max(0.0, min(1.0, base * self.source_prior * penalty))

    @property
    def is_unsupported(self) -> bool:
        """Weakly evidenced: low overall score, or unknown source with no corroboration."""
        if self.score < _UNSUPPORTED_SCORE_THRESHOLD:
            return True
        return self.source_type == SourceType.UNKNOWN and self.corroboration < 0.2


class EvidenceSet(_EvidenceBase):
    """A collection of evidence items, with transparent aggregate measures."""

    items: list[EvidenceItem] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.items

    def average_reliability(self) -> float:
        if self.is_empty:
            return 0.0
        return sum(i.reliability for i in self.items) / len(self.items)

    def contested_claims(self) -> list[str]:
        return [i.claim for i in self.items if i.contested]

    def unsupported_claims(self) -> list[str]:
        return [i.claim for i in self.items if i.is_unsupported]

    def weakest_critical_evidence(self) -> EvidenceItem | None:
        """The lowest-scoring item -- the weakest link in the evidential chain."""
        if self.is_empty:
            return None
        return min(self.items, key=lambda i: i.score)

    def overall_evidence_score(self) -> float:
        """Mean item score, reduced in proportion to how much is contested."""
        if self.is_empty:
            return 0.0
        mean_score = sum(i.score for i in self.items) / len(self.items)
        contested_fraction = len(self.contested_claims()) / len(self.items)
        return max(0.0, min(1.0, mean_score * (1.0 - 0.4 * contested_fraction)))


@dataclass
class EvidenceAssessment:
    """The result of assessing an :class:`EvidenceSet` (or its absence)."""

    provided: bool
    score: float
    average_reliability: float = 0.0
    contested_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    weakest_claim: str | None = None
    reasoning: list[str] = field(default_factory=list)


def assess_evidence(evidence: EvidenceSet | None) -> EvidenceAssessment:
    """Assess an evidence set, returning a score plus a transparent explanation."""
    if evidence is None:
        return EvidenceAssessment(
            provided=False,
            score=0.0,
            reasoning=["no evidence set was supplied; evidence does not contribute"],
        )
    if evidence.is_empty:
        return EvidenceAssessment(
            provided=False,
            score=0.0,
            reasoning=["evidence set is empty; evidence does not contribute"],
        )

    score = evidence.overall_evidence_score()
    contested = evidence.contested_claims()
    unsupported = evidence.unsupported_claims()
    weakest = evidence.weakest_critical_evidence()

    reasoning = [
        "evidence_score is a transparent heuristic over the supplied items",
        f"{len(evidence.items)} item(s); average reliability = "
        f"{evidence.average_reliability():.2f}",
        f"overall_evidence_score = {score:.2f}",
    ]
    if contested:
        reasoning.append(f"contested claim(s): {'; '.join(contested)}")
    if unsupported:
        reasoning.append(f"unsupported / weakly-sourced claim(s): {'; '.join(unsupported)}")
    if weakest is not None:
        reasoning.append(f"weakest evidence: '{weakest.claim}' (score {weakest.score:.2f})")

    return EvidenceAssessment(
        provided=True,
        score=score,
        average_reliability=evidence.average_reliability(),
        contested_claims=contested,
        unsupported_claims=unsupported,
        weakest_claim=weakest.claim if weakest else None,
        reasoning=reasoning,
    )
