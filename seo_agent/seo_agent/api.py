import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from modules.crawler import Crawler
from agent.orchestrator import run_audit
from utils.sheets_writer import write_results
from config.settings import settings

# Path to the marketing folder (one level up from seo_agent/)
MARKETING_DIR = os.path.join(os.path.dirname(__file__), '..', 'marketing')

app = Flask(__name__)
CORS(app, supports_credentials=True)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)


# ── User model ───────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _run_async(coro):
    """Safe asyncio runner — works even if a loop already exists."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Serve the marketing UI ──────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(MARKETING_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(MARKETING_DIR, filename)


# ── Auth routes ──────────────────────────────────────────────────────────────
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409
    user = User(email=email, password=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({'message': 'Account created', 'email': user.email})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid email or password'}), 401
    login_user(user)
    return jsonify({'message': 'Logged in', 'email': user.email})


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out'})


@app.route('/api/me', methods=['GET'])
def me():
    if current_user.is_authenticated:
        return jsonify({'email': current_user.email})
    return jsonify({'email': None})


# ── API routes ───────────────────────────────────────────────────────────────
@app.route("/audit", methods=["POST"])
@login_required
def audit():
    data = request.get_json(force=True)
    url = (data or {}).get("url", "").strip()
    sheet_id = (data or {}).get("sheet_id") or settings.google_sheet_id or None

    if not url:
        return jsonify({"error": "URL is required"}), 400

    async def run():
        pages = await Crawler(url).crawl()
        return await run_audit(pages)

    results = _run_async(run())

    if sheet_id:
        try:
            write_results(sheet_id, results)
        except Exception as e:
            print(f"[WARN] Sheets write failed: {e}")

    return jsonify([
        {
            "url": r.url,
            "status_code": r.status_code,
            "title": r.title,
            "score": r.score,
            "meta_issues": r.meta.count(),
            "meta_detail": r.meta.to_str(),
            "broken_links": len(r.broken_links),
            "keyword_issues": r.keywords.to_str(),
            "overstuffed_keywords": r.keywords.overstuffed,
            "underoptimised": r.keywords.underoptimised,
            "flesch_score": round(r.readability.flesch_score, 1),
            "gunning_fog": round(r.readability.gunning_fog, 1),
            "readability": r.readability.grade_label or "n/a",
            "readability_below_target": r.readability.below_target,
            "suggestions": r.suggestions,
        }
        for r in results
    ])


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(port=5000, debug=False)