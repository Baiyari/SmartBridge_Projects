import logging

import pandas as pd

logger = logging.getLogger(__name__)

FLAG_DESCRIPTIONS = {
    "absenteeism_flag":       "High absenteeism / burnout-driven absence",
    "low_engagement_flag":    "Low overall engagement",
    "performance_drop_flag":  "Below-average performance rating",
    "career_stagnation_flag": "No promotion in 4+ years",
    "flight_risk_flag":       "Has worked at 4+ companies",
    "compensation_flag":      "Paid below 25th percentile for role",
    "high_burnout_flag":      "Overtime + poor work-life balance",
}


def detect_patterns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["absenteeism_flag"]       = (df["OverTime_Binary"] == 1) & (df["WorkLifeBalance"] <= 2)
    df["low_engagement_flag"]    = df["engagement_score"] <= 2.0
    df["performance_drop_flag"]  = df["PerformanceRating"] <= 2
    df["career_stagnation_flag"] = df["YearsSinceLastPromotion"] >= 4
    df["flight_risk_flag"]       = df["NumCompaniesWorked"] >= 4
    df["compensation_flag"]      = df["income_percentile"] <= 0.25
    df["high_burnout_flag"]      = df["burnout_score"] >= 3

    flag_cols = [c for c in df.columns if c.endswith("_flag")]
    df["active_flag_count"] = df[flag_cols].sum(axis=1)

    logger.info(f"Avg flags/employee: {df['active_flag_count'].mean():.2f}")
    return df


def get_active_flags(row: pd.Series) -> list[str]:
    return [desc for flag, desc in FLAG_DESCRIPTIONS.items() if row.get(flag, False)]