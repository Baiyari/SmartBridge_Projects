import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_MAX_TOKENS, SUGGESTION_THRESHOLD, MAX_WORKERS
from pattern_detector import get_active_flags

logger = logging.getLogger(__name__)

_client = Groq(api_key=GROQ_API_KEY)
_CACHE_PATH = Path(__file__).parent / "suggestions_cache.json"

_FALLBACKS = {
    "career_stagnation_flag": "Schedule a career development conversation and explore promotion pathways.",
    "high_burnout_flag":      "Discuss workload and consider removing overtime obligations.",
    "compensation_flag":      "Run a compensation benchmarking review for this role.",
    "low_engagement_flag":    "1:1 check-in to surface root causes of disengagement.",
    "flight_risk_flag":       "Offer a retention package or fast-track growth opportunity.",
    "performance_drop_flag":  "Initiate a structured support plan with clear 30-day milestones.",
    "absenteeism_flag":       "Review workload and connect employee with wellness resources.",
}


def generate_suggestions_for_all(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["retention_suggestion"] = ""

    at_risk = df[df["composite_score"] >= SUGGESTION_THRESHOLD]
    cache   = _load_cache()
    to_call = []

    for idx, row in at_risk.iterrows():
        cache_key = f"{row['EmployeeNumber']}_{row['composite_score']:.1f}"
        if cache_key in cache:
            df.at[idx, "retention_suggestion"] = cache[cache_key]
        else:
            to_call.append((idx, row, cache_key))

    logger.info(f"Suggestions: {len(at_risk) - len(to_call)} from cache, {len(to_call)} calling Groq")

    if to_call:
        futures = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for idx, row, cache_key in to_call:
                futures[executor.submit(_suggest, row)] = (idx, cache_key)

        for future in as_completed(futures):
            idx, cache_key = futures[future]
            suggestion = future.result()
            df.at[idx, "retention_suggestion"] = suggestion
            cache[cache_key] = suggestion

        _save_cache(cache)

    return df


def _suggest(row: pd.Series) -> str:
    flags = get_active_flags(row)

    prompt = (
        f"HR retention case: {row.get('JobRole')}, {row.get('Department')}, "
        f"{int(row.get('YearsAtCompany', 0))}yr tenure, "
        f"risk score {row.get('composite_score', 0):.0f}/100. "
        f"Signals: {', '.join(flags) if flags else 'none'}. "
        f"Give 3 specific actions HR should take this week. Numbered, one line each."
    )

    try:
        resp = _client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=GROQ_MAX_TOKENS,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You are a senior HR consultant. Be direct and specific."},
                {"role": "user",   "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Groq failed for {row['EmployeeNumber']}: {e} — using fallback")
        suggestions = [msg for flag, msg in _FALLBACKS.items() if row.get(flag, False)]
        return "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions)) or \
               "1. Schedule an immediate 1:1 with the HR manager."


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        with open(_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)