import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "employees.csv"
MODEL_PATH = BASE_DIR / "rf_model.joblib"
ALERTS_LOG_PATH = BASE_DIR / "alerts_log.json"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS = 150    # 3 one-line suggestions never need more than this
MAX_WORKERS     = 5     # concurrent Groq calls

ALERT_THRESHOLD      = 65
SUGGESTION_THRESHOLD = 70   # only truly at-risk employees get AI suggestions
ALERT_COOLDOWN_HOURS = 24

RISK_BANDS = {
    "LOW":      (0,  39),
    "MEDIUM":   (40, 64),
    "HIGH":     (65, 79),
    "CRITICAL": (80, 100),
}

# weights must sum <= 100
RULE_WEIGHTS = {
    "overtime":               20,
    "low_job_satisfaction":   20,
    "no_recent_promotion":    15,
    "poor_work_life_balance": 15,
    "poor_env_satisfaction":  15,
    "high_company_count":     15,
}

ML_WEIGHT   = 0.6
RULE_WEIGHT = 0.4

EMAIL_ENABLED = False
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-password"
HR_EMAIL_RECIPIENTS = ["hr@company.com"]

SLACK_ENABLED = False
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

LOG_LEVEL = "INFO"