import json
import logging
import smtplib
import urllib.request
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from config import (
    ALERT_COOLDOWN_HOURS, ALERT_THRESHOLD, ALERTS_LOG_PATH,
    EMAIL_ENABLED, HR_EMAIL_RECIPIENTS, SLACK_ENABLED, SLACK_WEBHOOK_URL,
    SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER,
)
from pattern_detector import get_active_flags

logger = logging.getLogger(__name__)


def dispatch_alerts(df: pd.DataFrame) -> list[dict]:
    log = _load_log()
    dispatched = []

    for _, row in df[df["composite_score"] >= ALERT_THRESHOLD].iterrows():
        emp_id = str(row["EmployeeNumber"])

        if emp_id in log:
            last = datetime.fromisoformat(log[emp_id]["alerted_at"])
            if datetime.utcnow() - last < timedelta(hours=ALERT_COOLDOWN_HOURS):
                continue

        msg = _build_message(row)
        if EMAIL_ENABLED: _send_email(msg, row)
        if SLACK_ENABLED: _send_slack(msg)

        record = {
            "employee_id":     emp_id,
            "composite_score": float(row["composite_score"]),
            "risk_band":       row["risk_band"],
            "alerted_at":      datetime.utcnow().isoformat(),
        }
        log[emp_id] = record
        dispatched.append(record)
        logger.info(f"Alert → Employee {emp_id} (score: {row['composite_score']:.1f})")

    _save_log(log)
    return dispatched


def _build_message(row: pd.Series) -> str:
    flags = "\n".join(f"  • {f}" for f in get_active_flags(row)) or "  • none"
    return f"""
ATTRITION RISK ALERT

Employee : {row['EmployeeNumber']} | {row.get('JobRole')} — {row.get('Department')}
Score    : {row['composite_score']:.1f}/100 ({row['risk_band']})
Tenure   : {int(row.get('YearsAtCompany', 0))} years

Signals:
{flags}

Suggested action:
{row.get('retention_suggestion') or 'Review profile and schedule a 1:1.'}
""".strip()


def _send_email(body: str, row: pd.Series) -> None:
    try:
        msg = MIMEMultipart()
        msg["From"]    = SMTP_USER
        msg["To"]      = ", ".join(HR_EMAIL_RECIPIENTS)
        msg["Subject"] = f"[{row['risk_band']}] Attrition Risk — Employee {row['EmployeeNumber']}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, HR_EMAIL_RECIPIENTS, msg.as_string())

    except Exception as e:
        logger.error(f"Email failed: {e}")


def _send_slack(body: str) -> None:
    try:
        payload = json.dumps({"text": f"```{body}```"}).encode()
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL, data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Slack failed: {e}")


def _load_log() -> dict:
    if ALERTS_LOG_PATH.exists():
        with open(ALERTS_LOG_PATH) as f:
            return json.load(f)
    return {}


def _save_log(log: dict) -> None:
    with open(ALERTS_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)