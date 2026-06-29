import json
import logging
import math
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config
from alert_manager import dispatch_alerts
from data_loader import load_and_preprocess
from pattern_detector import detect_patterns
from retention_advisor import generate_suggestions_for_all
from risk_engine import compute_risk_scores

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Auth configuration ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Database setup (SQLite) ───────────────────────────────────────────────────
engine = create_engine("sqlite:///users.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, index=True)
    email    = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserModel:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user


# ── Auth Pydantic schemas ─────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: str
    password: str

TERMINATIONS_LOG = config.BASE_DIR / "terminations_log.json"
WARNINGS_LOG     = config.BASE_DIR / "warnings_log.json"
PIP_LOG          = config.BASE_DIR / "pip_log.json"
UPLOADED_CSV     = config.BASE_DIR / "uploaded_data.csv"


# ── Pydantic request bodies ───────────────────────────────────────────────────
class TerminateRequest(BaseModel):
    reason: str
    terminated_by: str

class WarningRequest(BaseModel):
    reason: str = ""
    issued_by: str

class PipRequest(BaseModel):
    reason: str = ""
    issued_by: str


# ── Lifespan ──────────────────────────────────────────────────────────────────
_state: dict = {"df": None}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running pipeline on startup...")
    _state["df"] = _run_pipeline(send_alerts=False)
    yield


app = FastAPI(title="Attrition Risk Predictor", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8000"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


# ── Serve frontend ────────────────────────────────────────────────────────────
@app.get("/")
def serve_index():
    return FileResponse("index.html")


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.post("/auth/signup")
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or not body.password:
        raise HTTPException(400, "Email and password are required")
    if len(body.password) > 72:
        raise HTTPException(400, "Password must be 72 characters or fewer")
    if db.query(UserModel).filter(UserModel.email == email).first():
        raise HTTPException(409, "Email already registered")
    user = UserModel(email=email, password=pwd_context.hash(body.password))
    db.add(user)
    db.commit()
    token = create_access_token({"sub": email})
    return {"access_token": token, "token_type": "bearer", "email": email}


@app.post("/auth/login")
def login(body: SignupRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user or not pwd_context.verify(body.password, user.password):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token({"sub": email})
    return {"access_token": token, "token_type": "bearer", "email": email}


@app.get("/auth/me")
def me(current_user: UserModel = Depends(get_current_user)):
    return {"email": current_user.email}


# ── Existing endpoints (protected) ────────────────────────────────────────────
@app.post("/analyze")
def analyze(send_alerts: bool = True, current_user: UserModel = Depends(get_current_user)):
    df = _run_pipeline(send_alerts=send_alerts)
    _state["df"] = df
    return {
        "status": "success",
        "employees_analyzed": len(df),
        "risk_distribution": df["risk_band"].value_counts().to_dict(),
    }


@app.get("/employees")
def get_employees(
    risk_band: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user),
):
    df = _df()
    if risk_band:  df = df[df["risk_band"] == risk_band.upper()]
    if department: df = df[df["Department"].str.lower() == department.lower()]
    page = df.sort_values("composite_score", ascending=False).iloc[offset: offset + limit]
    return {"total": len(df), "employees": _to_records(page)}


@app.get("/employees/{employee_id}")
def get_employee(employee_id: int, current_user: UserModel = Depends(get_current_user)):
    df  = _df()
    row = df[df["EmployeeNumber"] == employee_id]
    if row.empty:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return _to_detail(row.iloc[0])


@app.get("/alerts")
def get_alerts(current_user: UserModel = Depends(get_current_user)):
    df = _df()
    at_risk = df[df["composite_score"] >= config.ALERT_THRESHOLD].sort_values(
        "composite_score", ascending=False
    )
    return {"threshold": config.ALERT_THRESHOLD, "count": len(at_risk), "employees": _to_records(at_risk)}


@app.get("/dashboard-summary")
def dashboard_summary(current_user: UserModel = Depends(get_current_user)):
    df = _df()
    flag_cols = [c for c in df.columns if c.endswith("_flag")]

    # Age group risk
    df2 = df.copy()
    df2["age_group"] = pd.cut(
        df2["Age"], bins=[18, 25, 35, 45, 55, 100],
        labels=["18-25", "26-35", "36-45", "46-55", "55+"]
    )
    age_group_risk = (
        df2.groupby("age_group", observed=True)["composite_score"]
        .mean().round(1).to_dict()
    )
    # Convert keys to strings (categorical labels)
    age_group_risk = {str(k): v for k, v in age_group_risk.items()}

    # Tenure risk
    df2["tenure_group"] = pd.cut(
        df2["YearsAtCompany"], bins=[-1, 1, 3, 5, 10, 100],
        labels=["0-1yr", "1-3yr", "3-5yr", "5-10yr", "10+yr"]
    )
    tenure_risk = (
        df2.groupby("tenure_group", observed=True)["composite_score"]
        .mean().round(1).to_dict()
    )
    tenure_risk = {str(k): v for k, v in tenure_risk.items()}

    # Gender distribution
    gender_distribution = df["Gender"].value_counts().to_dict() if "Gender" in df.columns else {}

    # Flag prevalence (strip _flag suffix for cleaner keys)
    flag_prevalence = {
        c.replace("_flag", ""): round(df[c].mean() * 100, 1)
        for c in flag_cols
    }

    return {
        "total_employees":     len(df),
        "avg_risk_score":      round(df["composite_score"].mean(), 1),
        "high_critical_count": int(df["risk_band"].isin(["HIGH", "CRITICAL"]).sum()),
        "risk_distribution":   df["risk_band"].value_counts().to_dict(),
        "department_risk":     df.groupby("Department")["composite_score"].mean().round(1).sort_values(ascending=False).to_dict(),
        "top_at_risk":         _to_records(df.nlargest(5, "composite_score")),
        "flag_prevalence":     flag_prevalence,
        "gender_distribution": gender_distribution,
        "age_group_risk":      age_group_risk,
        "tenure_risk":         tenure_risk,
    }


@app.get("/health")
def health():
    return {"status": "ok", "employees": len(_state["df"]) if _state["df"] is not None else 0}


# ── NEW: Upload data source ───────────────────────────────────────────────────
@app.post("/upload-datasource")
async def upload_datasource(
    file: Optional[UploadFile] = File(None),
    sheet_url: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user),
):
    if file and file.filename:
        # Save uploaded CSV to disk
        with open(UPLOADED_CSV, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        source_path = str(UPLOADED_CSV)
        logger.info(f"CSV uploaded: {file.filename} → {UPLOADED_CSV}")

    elif sheet_url:
        # Convert Google Sheets share URL to CSV export URL
        try:
            sheet_id = sheet_url.split("/d/")[1].split("/")[0]
            source_path = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            logger.info(f"Google Sheets URL resolved: {source_path}")
        except Exception:
            raise HTTPException(400, "Invalid Google Sheets URL. Make sure the sheet is publicly shared.")
    else:
        raise HTTPException(400, "Provide either a CSV file upload or a Google Sheets URL.")

    # Run full pipeline on the new source
    try:
        df = load_and_preprocess(file_path=source_path)
        df = detect_patterns(df)
        df = compute_risk_scores(df)
        df = generate_suggestions_for_all(df)
        _state["df"] = df
        logger.info(f"Pipeline complete on new source: {len(df)} employees")
        return {
            "status": "success",
            "employees_loaded": len(df),
            "risk_distribution": df["risk_band"].value_counts().to_dict(),
        }
    except ValueError as e:
        raise HTTPException(400, f"Data validation error: {e}")
    except Exception as e:
        logger.error(f"Pipeline error on upload: {e}")
        raise HTTPException(500, f"Pipeline error: {e}")


# ── NEW: Terminate employee ───────────────────────────────────────────────────
@app.post("/employees/{employee_id}/terminate")
def terminate_employee(employee_id: int, body: TerminateRequest, current_user: UserModel = Depends(get_current_user)):
    df = _df()
    row = df[df["EmployeeNumber"] == employee_id]
    if row.empty:
        raise HTTPException(404, f"Employee {employee_id} not found")

    emp = row.iloc[0]
    record = {
        "employee_id":     int(employee_id),
        "department":      _safe(emp.get("Department")),
        "job_role":        _safe(emp.get("JobRole")),
        "composite_score": _safe(emp.get("composite_score")),
        "risk_band":       _safe(emp.get("risk_band")),
        "reason":          body.reason,
        "terminated_by":   body.terminated_by,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }

    # Persist to log
    log = _load_json(TERMINATIONS_LOG)
    log.append(record)
    _save_json(TERMINATIONS_LOG, log)

    # Remove from in-memory state
    _state["df"] = df[df["EmployeeNumber"] != employee_id].copy()
    logger.info(f"Employee {employee_id} terminated by {body.terminated_by}")

    return {"status": "success", "message": f"Termination logged for Employee {employee_id}"}


# ── NEW: Warning letter ───────────────────────────────────────────────────────
@app.post("/employees/{employee_id}/warning")
def warn_employee(employee_id: int, body: WarningRequest, current_user: UserModel = Depends(get_current_user)):
    df = _df()
    row = df[df["EmployeeNumber"] == employee_id]
    if row.empty:
        raise HTTPException(404, f"Employee {employee_id} not found")

    emp = row.iloc[0]
    flag_cols  = [c for c in df.columns if c.endswith("_flag")]
    active     = [c.replace("_flag", "").replace("_", " ").title() for c in flag_cols if bool(emp.get(c, False))]
    flags_text = "; ".join(active) if active else "General disengagement signals"

    today = datetime.now().strftime("%B %d, %Y")
    letter = f"""WARNING LETTER
{'─' * 50}
Date        : {today}
To          : Employee #{employee_id} — {_safe(emp.get('JobRole'))}, {_safe(emp.get('Department'))}
From        : HR Department
Subject     : Performance & Engagement Concern
{'─' * 50}

Dear Employee #{employee_id},

This letter serves as a formal notice that your current engagement
and performance indicators have raised concerns requiring immediate
attention.

Specifically, the following signals have been detected in your
recent HR data:

  {flags_text}

Your current attrition risk score is {round(float(emp.get('composite_score', 0)), 1)}/100,
classified as {_safe(emp.get('risk_band'))} RISK.

{('Additional notes: ' + body.reason) if body.reason.strip() else ''}

We strongly encourage you to schedule a meeting with your HR
representative within 48 hours to discuss a clear path forward,
including any support resources available to you.

Failure to engage in this process may result in further formal
action in accordance with company HR policy.

Issued by   : {body.issued_by}
Department  : Human Resources
{'─' * 50}
This is an official HR document. Please retain for your records."""

    record = {
        "employee_id":     int(employee_id),
        "department":      _safe(emp.get("Department")),
        "job_role":        _safe(emp.get("JobRole")),
        "composite_score": _safe(emp.get("composite_score")),
        "risk_band":       _safe(emp.get("risk_band")),
        "reason":          body.reason,
        "issued_by":       body.issued_by,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "letter":          letter,
    }

    log = _load_json(WARNINGS_LOG)
    log.append(record)
    _save_json(WARNINGS_LOG, log)
    logger.info(f"Warning letter issued for Employee {employee_id} by {body.issued_by}")

    return {"status": "success", "message": f"Warning logged for Employee {employee_id}"}


# ── NEW: PIP (Performance Improvement Plan) ───────────────────────────────────
@app.post("/employees/{employee_id}/pip")
def pip_employee(employee_id: int, body: WarningRequest, current_user: UserModel = Depends(get_current_user)):
    df = _df()
    row = df[df["EmployeeNumber"] == employee_id]
    if row.empty:
        raise HTTPException(404, f"Employee {employee_id} not found")

    emp = row.iloc[0]
    today = datetime.now().strftime("%B %d, %Y")
    review_date = datetime.now().strftime("%B %d, %Y")  # 30 days ideally

    letter = f"""PERFORMANCE IMPROVEMENT PLAN (PIP)
{'─' * 50}
Date        : {today}
To          : Employee #{employee_id} — {_safe(emp.get('JobRole'))}, {_safe(emp.get('Department'))}
From        : HR Department
Review Date : 30 days from {review_date}
{'─' * 50}

Dear Employee #{employee_id},

This Performance Improvement Plan has been initiated to provide
structured support and clear expectations to help you succeed
in your current role.

CURRENT STATUS:
  Attrition Risk Score : {round(float(emp.get('composite_score', 0)), 1)}/100 ({_safe(emp.get('risk_band'))} RISK)

IMPROVEMENT GOALS (30-Day Plan):
  1. Attend weekly 1:1 sessions with your direct manager.
  2. Demonstrate measurable improvement in engagement scores.
  3. Complete any outstanding training or development tasks.
  4. Maintain regular and punctual attendance.

{('Manager Notes: ' + body.reason) if body.reason.strip() else ''}

Progress will be reviewed at the 30-day mark. Successful completion
of this PIP will result in removal of the performance flag.
Non-compliance may lead to further HR action.

Acknowledged by HR : {body.issued_by}
{'─' * 50}
This is an official HR document. Please retain for your records."""

    record = {
        "employee_id":     int(employee_id),
        "department":      _safe(emp.get("Department")),
        "job_role":        _safe(emp.get("JobRole")),
        "composite_score": _safe(emp.get("composite_score")),
        "risk_band":       _safe(emp.get("risk_band")),
        "notes":           body.reason,
        "issued_by":       body.issued_by,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "pip_letter":      letter,
    }

    pip_log = config.BASE_DIR / "pip_log.json"
    log = _load_json(pip_log)
    log.append(record)
    _save_json(pip_log, log)
    logger.info(f"PIP issued for Employee {employee_id} by {body.issued_by}")

    return {"status": "success", "letter": letter}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_pipeline(send_alerts: bool = True, file_path: Optional[str] = None) -> pd.DataFrame:
    df = load_and_preprocess(file_path=file_path)
    df = detect_patterns(df)
    df = compute_risk_scores(df)
    df = generate_suggestions_for_all(df)
    if send_alerts:
        dispatch_alerts(df)
    return df


def _df() -> pd.DataFrame:
    if _state["df"] is None:
        raise HTTPException(503, "Data not ready. POST /analyze first.")
    return _state["df"]


def _safe(val):
    if isinstance(val, float) and math.isnan(val): return None
    if hasattr(val, "item"): return val.item()
    return val


def _to_records(df: pd.DataFrame) -> list[dict]:
    cols = ["EmployeeNumber", "Department", "JobRole", "Age", "Gender", "YearsAtCompany",
            "composite_score", "rule_score", "ml_score", "risk_band",
            "active_flag_count", "retention_suggestion", "engagement_score"]
    available = [c for c in cols if c in df.columns]
    flag_cols = [c for c in df.columns if c.endswith("_flag")]

    records = []
    for _, row in df.iterrows():
        r = {k: _safe(row.get(k)) for k in available}
        r["active_flags"] = [f for f in flag_cols if bool(row.get(f))]
        records.append(r)
    return records


def _to_detail(row: pd.Series) -> dict:
    flag_cols = [c for c in row.index if c.endswith("_flag")]
    return {
        "employee_id":          _safe(row["EmployeeNumber"]),
        "department":           _safe(row.get("Department")),
        "job_role":             _safe(row.get("JobRole")),
        "age":                  _safe(row.get("Age")),
        "years_at_company":     _safe(row.get("YearsAtCompany")),
        "monthly_income":       _safe(row.get("MonthlyIncome")),
        "composite_score":      _safe(row.get("composite_score")),
        "rule_score":           _safe(row.get("rule_score")),
        "ml_score":             _safe(row.get("ml_score")),
        "risk_band":            _safe(row.get("risk_band")),
        "engagement_score":     _safe(row.get("engagement_score")),
        "active_flags":         {f: bool(row.get(f, False)) for f in flag_cols},
        "retention_suggestion": _safe(row.get("retention_suggestion", "")),
    }


def _load_json(path: Path) -> list:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _save_json(path: Path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)