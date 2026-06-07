"""Tests for structured evidence handling (brief scenario 9)."""

from __future__ import annotations

from littleboy import EvidenceItem, EvidenceSet, SourceType
from littleboy.data.evidence import assess_evidence


def test_evidence_set_detects_contested_and_unsupported_claims():
    evidence = EvidenceSet(
        items=[
            EvidenceItem(
                claim="The door was locked",
                source_type=SourceType.DIRECT_OBSERVATION,
                reliability=0.9,
                specificity=0.9,
                recency=0.9,
                corroboration=0.8,
            ),
            EvidenceItem(
                claim="The suspect confessed",
                source_type=SourceType.TESTIMONY,
                reliability=0.4,
                specificity=0.5,
                recency=0.5,
                corroboration=0.2,
                contested=True,
            ),
            EvidenceItem(
                claim="A rumour heard third-hand",
                source_type=SourceType.UNKNOWN,
                reliability=0.2,
                specificity=0.2,
                recency=0.3,
                corroboration=0.1,
            ),
        ]
    )

    assert "The suspect confessed" in evidence.contested_claims()
    # The rumour (and likely the contested low item) are unsupported.
    unsupported = evidence.unsupported_claims()
    assert "A rumour heard third-hand" in unsupported
    # The strong direct observation is neither contested nor unsupported.
    assert "The door was locked" not in evidence.contested_claims()
    assert "The door was locked" not in unsupported


def test_weakest_evidence_is_the_lowest_scoring_item():
    evidence = EvidenceSet(
        items=[
            EvidenceItem(claim="strong", source_type=SourceType.DOCUMENT, reliability=0.9),
            EvidenceItem(claim="weak", source_type=SourceType.UNKNOWN, reliability=0.1),
        ]
    )
    weakest = evidence.weakest_critical_evidence()
    assert weakest is not None
    assert weakest.claim == "weak"


def test_contested_item_scores_lower_than_identical_uncontested():
    base = dict(reliability=0.8, specificity=0.8, recency=0.8, corroboration=0.8)
    clean = EvidenceItem(claim="x", source_type=SourceType.DOCUMENT, **base)
    contested = EvidenceItem(claim="x", source_type=SourceType.DOCUMENT, contested=True, **base)
    assert contested.score < clean.score


def test_assess_evidence_reports_absence():
    result = assess_evidence(None)
    assert result.provided is False
    assert result.score == 0.0
    assert result.reasoning

    empty = assess_evidence(EvidenceSet(items=[]))
    assert empty.provided is False


def test_assess_evidence_scores_and_explains():
    evidence = EvidenceSet(
        items=[
            EvidenceItem(
                claim="x",
                source_type=SourceType.EXPERT_REPORT,
                reliability=0.9,
                specificity=0.8,
                recency=0.8,
                corroboration=0.8,
            )
        ]
    )
    result = assess_evidence(evidence)
    assert result.provided is True
    assert 0.0 < result.score <= 1.0
    assert any("evidence_score" in line or "evidence" in line for line in result.reasoning)
