import os
import sys

# Fix path FIRST before any other imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

# Fix Windows encoding issue
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Load .env from both possible locations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_mail import Mail
from flask_session import Session
from datetime import timedelta
import requests

app = Flask(
    __name__,
    template_folder="../",
    static_folder="../",
)

# ── Config ────────────────────────────────────────────────────────────────────
app.config["SECRET_KEY"]                 = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_TYPE"]               = "filesystem"

# ── Session Cookie Fix ────────────────────────────────────────────────────────
app.config["SESSION_COOKIE_SAMESITE"]    = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"]    = True
app.config["SESSION_COOKIE_SECURE"]      = os.getenv("FLASK_ENV") == "production"

app.config["MAIL_SERVER"]                = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"]                  = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]               = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"]              = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"]              = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"]        = os.getenv("MAIL_DEFAULT_SENDER")

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5000").split(",")
CORS(app, supports_credentials=True, origins=allowed_origins)

# ── Extensions ────────────────────────────────────────────────────────────────
Session(app)
Mail(app)

# ── DB Init (with error logging) ──────────────────────────────────────────────
print(f"[DEBUG] MYSQL_HOST = {os.getenv('MYSQL_HOST')}", flush=True)
print(f"[DEBUG] MYSQL_PORT = {os.getenv('MYSQL_PORT')}", flush=True)
print(f"[DEBUG] MYSQL_USER = {os.getenv('MYSQL_USER')}", flush=True)
print(f"[DEBUG] MYSQL_DB   = {os.getenv('MYSQL_DB')}", flush=True)

try:
    from config.db import init_db
    with app.app_context():
        init_db()
    print("[DB] Connected successfully!", flush=True)
except Exception as e:
    print(f"[DB ERROR] {e}", flush=True)
    raise

# ── Blueprints ────────────────────────────────────────────────────────────────
from controllers.auth_controller import auth_bp
app.register_blueprint(auth_bp)

from controllers.progress_routes import progress_bp
app.register_blueprint(progress_bp)

# ── Core Routes ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health")
def health():
    return {"status": "Verboma API running"}, 200

# ── Groq AI Proxy ─────────────────────────────────────────────────────────────
@app.route("/api/claude", methods=["POST"])
def claude_proxy():
    data = request.get_json(silent=True) or {}

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return jsonify({"error": {"message": "GROQ_API_KEY not set in .env"}}), 500

    messages = []
    if data.get("system"):
        messages.append({"role": "system", "content": data["system"]})
    messages.extend(data.get("messages", []))

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": data.get("max_tokens", 1000),
                "temperature": 0.7,
            },
            timeout=60,
        )
        groq_data = resp.json()

        if resp.status_code == 200:
            text = groq_data["choices"][0]["message"]["content"]
            return jsonify({"content": [{"type": "text", "text": text}]}), 200
        else:
            return jsonify({"error": groq_data}), resp.status_code

    except Exception as e:
        return jsonify({"error": {"message": str(e)}}), 500

# ── Page Routes ───────────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/vocabulary")
def vocabulary():
    return render_template("vocabulary.html")

@app.route("/speaking")
def speaking():
    return render_template("speaking.html")

@app.route("/grammar")
def grammar():
    return render_template("grammar.html")

@app.route("/listening")
def listening():
    return render_template("listening.html")

@app.route("/writing")
def writing():
    return render_template("writing.html")

@app.route("/interview")
def interview():
    return render_template("interview.html")

@app.route("/video-lessons")
def video_lessons():
    return render_template("video_lessons.html")

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    is_dev = os.getenv("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=is_dev)