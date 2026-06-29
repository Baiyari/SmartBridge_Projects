import logging

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from config import MODEL_PATH, ML_WEIGHT, RULE_WEIGHT, RULE_WEIGHTS, RISK_BANDS
from data_loader import get_feature_matrix

logger = logging.getLogger(__name__)


def compute_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rule_score"]      = _rule_score(df)
    df["ml_score"]        = _ml_score(df) * 100
    df["composite_score"] = (df["rule_score"] * RULE_WEIGHT + df["ml_score"] * ML_WEIGHT).round(1)
    df["risk_band"]       = df["composite_score"].apply(_band)

    logger.info(f"Risk bands: {df['risk_band'].value_counts().to_dict()}")
    return df


def train_model(df: pd.DataFrame) -> RandomForestClassifier:
    X, y = get_feature_matrix(df), df["Attrition_Binary"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2,
                                                         random_state=42, stratify=y)
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_leaf=5,
        class_weight="balanced",   # IBM dataset is imbalanced (~16% attrition)
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    logger.info(f"\n{classification_report(y_test, model.predict(X_test), target_names=['Stayed', 'Left'])}")
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved → {MODEL_PATH}")
    return model


def _rule_score(df: pd.DataFrame) -> pd.Series:
    s = pd.Series(0.0, index=df.index)
    s += df["OverTime_Binary"]                             * RULE_WEIGHTS["overtime"]
    s += (df["JobSatisfaction"] <= 2).astype(int)         * RULE_WEIGHTS["low_job_satisfaction"]
    s += (df["YearsSinceLastPromotion"] >= 4).astype(int) * RULE_WEIGHTS["no_recent_promotion"]
    s += (df["WorkLifeBalance"] <= 2).astype(int)         * RULE_WEIGHTS["poor_work_life_balance"]
    s += (df["EnvironmentSatisfaction"] <= 2).astype(int) * RULE_WEIGHTS["poor_env_satisfaction"]
    s += (df["NumCompaniesWorked"] >= 4).astype(int)      * RULE_WEIGHTS["high_company_count"]
    return s.clip(0, 100)


def _ml_score(df: pd.DataFrame) -> pd.Series:
    model = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else train_model(df)
    probs = model.predict_proba(get_feature_matrix(df))[:, 1]
    return pd.Series(probs, index=df.index)


def _band(score: float) -> str:
    for band, (lo, hi) in RISK_BANDS.items():
        if lo <= score <= hi:
            return band
    return "CRITICAL"