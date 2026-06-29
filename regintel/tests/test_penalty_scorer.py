"""
Unit tests for the penalty scoring engine.

These tests exercise pure logic only (no Groq API, no ChromaDB), so they
run instantly and offline — run with:  pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
from src.scoring.penalty_scorer import score_gap, score_and_rank_gaps, parse_deadline_days
from src.vectorstore.chroma_manager import GapMatch


def _make_gap(
    obligation_type: str = "reporting",
    deadline_text: str | None = "within 30 days",
    similarity_score: float = 0.3,
    is_gap: bool = True,
) -> GapMatch:
    return GapMatch(
        obligation={
            "id": "test-id-1",
            "clause_text": "The bank shall report X within 30 days.",
            "obligation_type": obligation_type,
            "deadline_text": deadline_text,
            "circular_number": "RBI/2026-27/001",
            "regulator": "RBI",
            "applicable_entity": "Banks",
        },
        best_policy_match="Bank shall report X within 45 days.",
        similarity_score=similarity_score,
        is_gap=is_gap,
    )


def test_parse_deadline_days():
    assert parse_deadline_days("within 30 days") == 30
    assert parse_deadline_days("within 30 calendar days") == 30
    assert parse_deadline_days("immediately") == 0
    assert parse_deadline_days("with immediate effect") == 0
    assert parse_deadline_days("within 2 weeks") == 14
    assert parse_deadline_days("within three months") == 90
    assert parse_deadline_days(None) is None
    
    # Date-based parsing relative to now
    future_date = datetime.now() + timedelta(days=10)
    future_date_str = future_date.strftime("%B %d, %Y")
    assert parse_deadline_days(f"by {future_date_str}") == 10


def test_score_is_within_bounds():
    gap = _make_gap()
    scored = score_gap(gap)
    assert 0.0 <= scored.penalty_score <= 100.0


def test_higher_severity_type_scores_higher():
    low = score_gap(_make_gap(obligation_type="other"))
    high = score_gap(_make_gap(obligation_type="capital_liquidity"))
    assert high.penalty_score > low.penalty_score


def test_shorter_deadline_increases_urgency():
    far = score_gap(_make_gap(deadline_text="within 90 days"))
    near = score_gap(_make_gap(deadline_text="within 5 days"))
    assert near.penalty_score > far.penalty_score


def test_lower_similarity_increases_staleness_component():
    close_match = score_gap(_make_gap(similarity_score=0.9))
    far_match = score_gap(_make_gap(similarity_score=0.1))
    assert far_match.penalty_score > close_match.penalty_score


def test_score_components_populated():
    scored = score_gap(_make_gap(similarity_score=0.3))
    assert scored.severity_component > 0
    assert scored.urgency_component > 0
    assert scored.staleness_component > 0
    assert scored.best_policy_match == "Bank shall report X within 45 days."
    assert scored.applicable_entity == "Banks"
    assert scored.days_remaining == 30


def test_risk_band_thresholds():
    assert score_gap(_make_gap(obligation_type="capital_liquidity", deadline_text="within 3 days", similarity_score=0.0)).risk_band == "Critical"
    assert score_gap(_make_gap(obligation_type="other", deadline_text="within 365 days", similarity_score=1.0)).risk_band == "Low"


def test_score_and_rank_filters_non_gaps_and_sorts_descending():
    gaps = [
        _make_gap(obligation_type="other", is_gap=False),
        _make_gap(obligation_type="capital_liquidity", deadline_text="within 2 days", is_gap=True),
        _make_gap(obligation_type="governance", deadline_text="within 100 days", is_gap=True),
    ]
    ranked = score_and_rank_gaps(gaps)
    assert len(ranked) == 2  # the non-gap is excluded
    assert ranked[0].penalty_score >= ranked[1].penalty_score
