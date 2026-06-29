import logging
from typing import Optional

import pandas as pd

from config import DATA_PATH

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "EmployeeNumber", "Age", "Attrition", "Department", "JobRole",
    "JobSatisfaction", "EnvironmentSatisfaction", "WorkLifeBalance",
    "JobInvolvement", "PerformanceRating", "YearsAtCompany",
    "YearsSinceLastPromotion", "OverTime", "MonthlyIncome",
    "NumCompaniesWorked", "DistanceFromHome", "TrainingTimesLastYear",
]

NUMERIC_COLS = [
    "Age", "JobSatisfaction", "EnvironmentSatisfaction", "WorkLifeBalance",
    "JobInvolvement", "PerformanceRating", "YearsAtCompany",
    "YearsSinceLastPromotion", "MonthlyIncome", "NumCompaniesWorked",
    "DistanceFromHome", "TrainingTimesLastYear",
]

FEATURE_COLS = [
    "Age", "OverTime_Binary", "JobSatisfaction", "EnvironmentSatisfaction",
    "WorkLifeBalance", "JobInvolvement", "PerformanceRating", "YearsAtCompany",
    "YearsSinceLastPromotion", "MonthlyIncome", "NumCompaniesWorked",
    "DistanceFromHome", "TrainingTimesLastYear",
    "engagement_score", "stagnation_ratio", "income_percentile", "burnout_score",
]


def load_and_preprocess(file_path: Optional[str] = None) -> pd.DataFrame:
    # Use provided path, else default from config
    source = file_path if file_path else str(DATA_PATH)

    try:
        df = pd.read_csv(source)
    except Exception as e:
        raise FileNotFoundError(f"Could not load data from '{source}': {e}")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns: {missing}. "
            f"Please upload a valid IBM HR Analytics dataset with all required columns."
        )

    df = df.drop_duplicates(subset="EmployeeNumber").copy()

    df["Attrition_Binary"] = (df["Attrition"] == "Yes").astype(int)
    df["OverTime_Binary"]  = (df["OverTime"]  == "Yes").astype(int)

    df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
    df[NUMERIC_COLS] = df[NUMERIC_COLS].fillna(df[NUMERIC_COLS].median())

    # Derived features
    df["engagement_score"] = df[["JobSatisfaction", "EnvironmentSatisfaction",
                                  "WorkLifeBalance", "JobInvolvement"]].mean(axis=1)

    df["stagnation_ratio"]  = df["YearsSinceLastPromotion"] / df["YearsAtCompany"].replace(0, 1)
    df["income_percentile"] = df.groupby("JobRole")["MonthlyIncome"].rank(pct=True)
    df["burnout_score"]     = df["OverTime_Binary"] + (4 - df["WorkLifeBalance"])

    logger.info(f"Loaded {len(df)} employees from '{source}'")
    return df


def get_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df[FEATURE_COLS]