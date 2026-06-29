from __future__ import annotations

import logging
import os
import traceback
import time
import sqlite3
import hashlib
import secrets

from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.serving import WSGIRequestHandler
from python.ai_module import SmartStudyAI
from python.file_utils import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WSGIRequestHandler.timeout = 600

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = None
app.secret_key = secrets.token_hex(32)  # Secure random secret key

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DATABASE SETUP ---
DB_PATH = "smartstudy.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_email(email: str):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

def create_user(name: str, email: str, password: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hash_password(password))
        )
        conn.commit()

# --- AI MODEL LOADING ---
logger.info("Loading AI models at startup...")
ai = SmartStudyAI()
logger.info("Models ready.")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- AUTH ROUTES ---

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "All fields are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if get_user_by_email(email):
        return jsonify({"error": "An account with this email already exists."}), 409

    try:
        create_user(name, email, password)
        user = get_user_by_email(email)
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        return jsonify({"success": True, "name": user["name"], "email": user["email"]})
    except Exception as e:
        logger.error("Signup failed: %s", e)
        return jsonify({"error": "Signup failed. Please try again."}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = get_user_by_email(email)
    if not user or user["password_hash"] != hash_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    return jsonify({"success": True, "name": user["name"], "email": user["email"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me", methods=["GET"])
def me():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "name": session["user_name"],
            "email": session["user_email"]
        })
    return jsonify({"logged_in": False})


# --- MAIN ROUTES ---

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    start = time.time()

    try:
        level = request.form.get("level", "undergraduate")
        if level not in ("school", "undergraduate", "advanced"):
            level = "undergraduate"

        raw_text = request.form.get("raw_text", "").strip()
        file = request.files.get("file")

        if raw_text:
            text = raw_text
            logger.info("Using raw text input (%d characters)", len(text))
        elif file and file.filename != "":
            if not allowed_file(file.filename):
                return jsonify({"error": "Unsupported format. Use PDF, DOCX, or TXT."}), 400

            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            logger.info("File saved: %s", file_path)

            text = extract_text(file_path)
            logger.info("Extracted %d characters", len(text))
        else:
            return jsonify({"error": "No input provided. Upload a file or paste text."}), 400

        if not text.strip():
            return jsonify({"error": "No readable text found in the document."}), 422

        text = " ".join(text.split()[:3000])
        logger.info("Text trimmed to 3000 words")

        logger.info("Running summarization...")
        summary = ai.summarize(text, level)

        logger.info("Running simplification...")
        simplified = ai.simplify(text, level)

        logger.info("Running structuring...")
        structured = ai.structure(text, level)

        keywords = ai.extract_keywords(text)

        elapsed = round(time.time() - start, 1)
        logger.info("Done in %ss", elapsed)

        return jsonify({
            "simplified":  simplified,
            "summary":     summary,
            "structured":  structured,
            "keywords":    keywords,
            "word_count":  ai.word_count(text),
            "compression": ai.compression_ratio(text, summary),
            "confidence":  min(95, max(60, 100 - abs(ai.compression_ratio(text, summary) - 85))),
            "level":       level,
            "elapsed":     elapsed,
        })

    except Exception as e:
        logger.error("Processing failed: %s", traceback.format_exc())
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=False, threaded=True)