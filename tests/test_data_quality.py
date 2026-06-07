"""Tests for data-quality scoring, confidence, and uncertainty classification."""

from __future__ import annotations

import pytest

from littleboy.core.enums import UncertaintyLevel
from littleboy.core.models import DataQualityProfile
from littleboy.data.quality import (
    assess_data_quality,
    classify_uncertainty,
    compute_confidence,
)


def good_profile() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.9,
        source_reliability=0.9,
        specificity=0.85,
        recency=0.9,
        corroboration=0.85,
        ambiguity=0.1,
    )


def poor_profile() -> DataQualityProfile:
    return DataQualityProfile(
        completeness=0.2,
        source_reliability=0.2,
        specificity=0.2,
        recency=0.3,
        corroboration=0.1,
        ambiguity=0.8,
        missing_critical_facts=["consent record"],
    )


def test_good_data_scores_higher_than_poor_data():
    good = assess_data_quality(good_profile())
    poor = assess_data_quality(poor_profile())
    assert good.score > 0.7
    assert poor.score < 0.35
    assert good.score > poor.score


def test_missing_profile_scores_zero():
    result = assess_data_quality(None)
    assert result.score == 0.0
    assert result.reasoning  # explains why


def test_missing_critical_facts_are_surfaced():
    result = assess_data_quality(poor_profile())
    assert "consent record" in result.missing_facts


def test_ambiguity_lowers_the_score():
    clear = DataQualityProfile(ambiguity=0.0)
    murky = DataQualityProfile(ambiguity=0.9)
    assert assess_data_quality(clear).score > assess_data_quality(murky).score


def test_confidence_decreases_with_structural_unknowns():
    base = compute_confidence(0.9, 0)
    one = compute_confidence(0.9, 1)
    three = compute_confidence(0.9, 3)
    assert base > one > three
    assert 0.0 <= three <= 1.0


def test_uncertainty_classification_thresholds():
    assert classify_uncertainty(0.9) == UncertaintyLevel.LOW
    assert classify_uncertainty(0.6) == UncertaintyLevel.MODERATE
    assert classify_uncertainty(0.35) == UncertaintyLevel.HIGH
    assert classify_uncertainty(0.1) == UncertaintyLevel.CRITICAL


def test_assessment_reasoning_is_present():
    result = assess_data_quality(good_profile())
    assert result.reasoning
    assert any("data_quality_score" in line for line in result.reasoning)


def test_score_stays_in_unit_interval():
    for profile in (good_profile(), poor_profile(), DataQualityProfile()):
        score = assess_data_quality(profile).score
        assert 0.0 <= score <= 1.0
        assert classify_uncertainty(score) in set(UncertaintyLevel)


@pytest.mark.parametrize("n_unknowns", [0, 1, 2, 5])
def test_confidence_bounded(n_unknowns: int):
    assert 0.0 <= compute_confidence(0.8, n_unknowns) <= 1.0
