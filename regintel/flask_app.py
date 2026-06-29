import os
import sys
import json
import hmac
import base64
import hashlib
import sqlite3
import tempfile
import traceback
from pathlib import Path
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from config import Settings
from src.agent.orchestrator import RegIntelPipeline
from src.storage.audit_log import get_audit_history
from src.utils.groq_healthcheck import check_groq_model

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'regintel-secret-key-change-in-prod')

DB_PATH = Path("data/audit_log.db")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def _init_users_table():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def _make_token(email: str, name: str) -> str:
    payload = json.dumps({
        "email": email,
        "name": name,
        "exp": (datetime.utcnow() + timedelta(days=30)).isoformat()
    })
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(
        app.config['SECRET_KEY'].encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"

def _verify_token(token: str):
    """Returns payload dict or None if invalid/expired."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(
            app.config['SECRET_KEY'].encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if datetime.fromisoformat(payload["exp"]) < datetime.utcnow():
            return None
        return payload
    except Exception:
        return None

# Initialize users table at startup
_init_users_table()

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

pipeline = None
try:
    print("Loading Settings...", flush=True)
    settings = Settings.load()

    print(f"Running Groq health check against model '{settings.groq_model}'...", flush=True)
    health = check_groq_model(settings)
    if not health.ok:
        print("=" * 70, file=sys.stderr, flush=True)
        print("GROQ HEALTH CHECK FAILED — pipeline will NOT be initialized.", file=sys.stderr, flush=True)
        print(health.message, file=sys.stderr, flush=True)
        if health.detail:
            print(f"Detail: {health.detail}", file=sys.stderr, flush=True)
        print("=" * 70, file=sys.stderr, flush=True)
    else:
        print(health.message, flush=True)
        print("Initializing RegIntelPipeline...", flush=True)
        pipeline = RegIntelPipeline(settings)
        print("RegIntelPipeline successfully initialized.", flush=True)
except Exception as e:
    print(f"Error initializing RegIntelPipeline: {e}", file=sys.stderr, flush=True)
    traceback.print_exc()
    pipeline = None

# ---------------------------------------------------------------------------
# Static routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/app.js")
def serve_js():
    return send_from_directory("frontend", "app.js")

@app.route("/styles.css")
def serve_css():
    return send_from_directory("frontend", "styles.css")

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    conn = _get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "An account with this email already exists."}), 409

        password_hash = generate_password_hash(password)
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, created_at)
        )
        conn.commit()
    finally:
        conn.close()

    token = _make_token(email, name)
    return jsonify({"token": token, "user": {"name": name, "email": email}}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT name, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    token = _make_token(email, row["name"])
    return jsonify({"token": token, "user": {"name": row["name"], "email": email}})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing token."}), 401
    token = auth_header[7:]
    payload = _verify_token(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token."}), 401
    return jsonify({"user": {"name": payload["name"], "email": payload["email"]}})

# ---------------------------------------------------------------------------
# Audit endpoints (unauthenticated — unchanged)
# ---------------------------------------------------------------------------

@app.route("/api/audit", methods=["POST"])
def api_audit():
    if not pipeline:
        return jsonify({
            "error": (
                "Pipeline not initialized — the Groq health check failed at "
                "startup. Check the server terminal for the specific reason "
                "(deprecated model, incompatible tool-calling format, or bad "
                "API key) and fix GROQ_MODEL / GROQ_API_KEY in .env, then "
                "restart the server."
            )
        }), 500

    uploaded_files = []
    if "file" in request.files:
        uploaded_files = request.files.getlist("file")
    elif "files" in request.files:
        uploaded_files = request.files.getlist("files")
    else:
        for key in request.files:
            uploaded_files.extend(request.files.getlist(key))

    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        return jsonify({"error": "No files uploaded."}), 400

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_paths = []
            for file in uploaded_files:
                if not file.filename:
                    continue
                if not file.filename.lower().endswith(".pdf"):
                    return jsonify({"error": f"Invalid file format: {file.filename}. Only PDF files are allowed."}), 400
                tmp_path = Path(tmp_dir) / file.filename
                file.save(str(tmp_path))
                tmp_paths.append(tmp_path)

            if not tmp_paths:
                return jsonify({"error": "No valid files to process."}), 400

            print(f"Running audit on files: {[p.name for p in tmp_paths]}", flush=True)
            results = pipeline.run_batch(tmp_paths)

        response_results = []
        for r in results:
            if r.error:
                response_results.append({
                    "circular_number": r.circular_number,
                    "regulator": r.regulator,
                    "obligations_found": r.obligations_found,
                    "gaps_detected": r.gaps_detected,
                    "error": r.error,
                    "gaps": []
                })
            else:
                gaps_list = []
                for gap in r.scored_gaps:
                    gaps_list.append({
                        "obligation_id": gap.obligation_id,
                        "clause_text": gap.clause_text,
                        "risk_band": gap.risk_band,
                        "penalty_score": gap.penalty_score,
                        "regulator": gap.regulator,
                        "applicable_entity": gap.applicable_entity,
                        "circular_number": gap.circular_number,
                        "deadline_text": gap.deadline_text,
                        "days_remaining": gap.days_remaining,
                        "best_policy_match": gap.best_policy_match,
                        "similarity_score": gap.similarity_score
                    })
                response_results.append({
                    "circular_number": r.circular_number,
                    "regulator": r.regulator,
                    "obligations_found": r.obligations_found,
                    "gaps_detected": r.gaps_detected,
                    "error": None,
                    "gaps": gaps_list
                })

        return jsonify({"results": response_results})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Internal server error during audit execution: {str(e)}"}), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    try:
        history = get_audit_history()
        return jsonify({"history": history})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Internal server error fetching history: {str(e)}"}), 500


@app.route("/api/report/<path:circular_number>")
@app.route("/api/report")
def api_report(circular_number=None):
    if circular_number is None:
        circular_number = request.args.get("circular_number")
    if not circular_number:
        return jsonify({"error": "Missing circular number or report file identifier."}), 400

    reports_dir = Path("outputs/reports")
    clean_param = circular_number.strip()

    report_file = reports_dir / clean_param
    if report_file.exists() and report_file.is_file():
        return send_file(report_file, mimetype="application/pdf", as_attachment=True, download_name=report_file.name)

    safe_name = clean_param.replace("/", "-")
    report_file = reports_dir / f"gap_report_{safe_name}.pdf"
    if report_file.exists() and report_file.is_file():
        return send_file(report_file, mimetype="application/pdf", as_attachment=True, download_name=report_file.name)

    report_file = reports_dir / f"{safe_name}.pdf"
    if report_file.exists() and report_file.is_file():
        return send_file(report_file, mimetype="application/pdf", as_attachment=True, download_name=report_file.name)

    return jsonify({"error": f"Report file not found for identifier: {circular_number}"}), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)