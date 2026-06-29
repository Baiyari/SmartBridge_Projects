"""
Penalty exposure scoring for detected compliance gaps.

Combines three signals into a single 0-100 risk score so remediation
work can be prioritised by financial impact rather than circular order:
  1. Historical RBI/SEBI enforcement severity for the obligation type
  2. Deadline proximity (days remaining, parsed heuristically)
  3. Policy staleness (how semantically distant the closest internal
     policy is, as a proxy for how out-of-date it likely is)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from dateutil.parser import parse as parse_date

from src.vectorstore.chroma_manager import GapMatch

# Indicative historical enforcement severity by obligation type, derived
# from publicly disclosed RBI/SEBI penalty orders. Expressed as a base
# score out of 60 (the remaining 40 points come from deadline + staleness).
_SEVERITY_WEIGHTS: dict[str, int] = {
    "capital_liquidity": 60,
    "kyc_aml": 55,
    "reporting": 45,
    "disclosure": 40,
    "governance": 35,
    "deadline": 50,
    "other": 25,
}

_DAYS_PATTERN = re.compile(r"(\d+)\s*(?:calendar\s*)?days?", re.IGNORECASE)
_WEEKS_PATTERN = re.compile(r"(\d+)\s*weeks?", re.IGNORECASE)
_MONTHS_PATTERN = re.compile(r"(\d+)\s*months?", re.IGNORECASE)
_IMMEDIATE_PATTERN = re.compile(r"\b(?:immediate(?:ly)?|forthwith|with immediate effect|come into effect immediately)\b", re.IGNORECASE)

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fifteen": 15, "thirty": 30, "sixty": 60, "ninety": 90
}


@dataclass
class ScoredGap:
    obligation_id: str
    clause_text: str
    obligation_type: str
    circular_number: str | None
    regulator: str | None
    applicable_entity: str | None
    similarity_score: float
    deadline_text: str | None
    days_remaining: int | None
    best_policy_match: str | None
    severity_component: float
    urgency_component: float
    staleness_component: float
    penalty_score: float  # 0-100, higher = more urgent / higher risk
    risk_band: str  # "Critical" | "High" | "Medium" | "Low"


def parse_deadline_days(deadline_text: str | None) -> int | None:
    """Extract numeric days from deadline text if present."""
    if not deadline_text:
        return None
        
    text = deadline_text.strip().lower()
        
    if _IMMEDIATE_PATTERN.search(text):
        return 0
        
    # Translate common word numbers to digits
    for word, num in _WORD_NUMBERS.items():
        text = re.sub(rf"\b{word}\b", str(num), text)
        
    # Try days pattern first
    match = _DAYS_PATTERN.search(text)
    if match:
        return int(match.group(1))
        
    # Try weeks pattern
    match = _WEEKS_PATTERN.search(text)
    if match:
        return int(match.group(1)) * 7
        
    # Try months pattern
    match = _MONTHS_PATTERN.search(text)
    if match:
        return int(match.group(1)) * 30
        
    try:
        clean_text = re.sub(r'^(?:by|on or before|until|from)\s+', '', deadline_text.strip(), flags=re.IGNORECASE)
        dt = parse_date(clean_text, fuzzy=True)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return (dt.date() - datetime.now().date()).days
    except (ValueError, TypeError, OverflowError):
        pass
        
    return None


def _deadline_urgency(deadline_text: str | None, days: int | None) -> float:
    """Return 0-25 points: shorter stated deadlines score higher urgency.
    Obligations with no explicit deadline get a moderate default score,
    since open-ended duties still carry ongoing exposure."""
    if not deadline_text:
        return 12.0
    if days is None:
        return 15.0  # qualitative deadline (e.g. "immediately") -> elevated

    if days <= 0:
        return 25.0
    if days <= 7:
        return 20.0
    if days <= 30:
        return 15.0
    if days <= 90:
        return 10.0
    return 5.0


def _staleness_score(similarity_score: float) -> float:
    """Return 0-15 points: the further the closest policy is semantically,
    the staler/weaker existing coverage is presumed to be."""
    return round((1.0 - min(similarity_score, 1.0)) * 15.0, 2)


def _risk_band(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def score_gap(gap: GapMatch) -> ScoredGap:
    """Compute a single 0-100 penalty exposure score for one detected gap."""
    obligation_type = gap.obligation.get("obligation_type") or "other"
    severity = _SEVERITY_WEIGHTS.get(obligation_type, _SEVERITY_WEIGHTS["other"])
    
    deadline_text = gap.obligation.get("deadline_text")
    days_remaining = parse_deadline_days(deadline_text)
    urgency = _deadline_urgency(deadline_text, days_remaining)
    
    staleness = _staleness_score(gap.similarity_score)

    total = round(min(severity + urgency + staleness, 100.0), 2)

    return ScoredGap(
        obligation_id=gap.obligation["id"],
        clause_text=gap.obligation["clause_text"],
        obligation_type=obligation_type,
        circular_number=gap.obligation.get("circular_number") or None,
        regulator=gap.obligation.get("regulator") or None,
        applicable_entity=gap.obligation.get("applicable_entity") or None,
        similarity_score=gap.similarity_score,
        deadline_text=deadline_text or None,
        days_remaining=days_remaining,
        best_policy_match=gap.best_policy_match,
        severity_component=float(severity),
        urgency_component=float(urgency),
        staleness_component=float(staleness),
        penalty_score=total,
        risk_band=_risk_band(total),
    )


def score_and_rank_gaps(gaps: list[GapMatch]) -> list[ScoredGap]:
    """Score every gap and return them sorted highest-risk first."""
    scored = [score_gap(g) for g in gaps if g.is_gap]
    return sorted(scored, key=lambda s: s.penalty_score, reverse=True)
