import os
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from flask import (Blueprint, request, jsonify, redirect,
                   url_for, render_template, g, session, current_app)

from models.user import (find_by_email, find_by_id, find_by_google_id,
                         create_user, update_user, verify_password, safe_user)
from utils.otp_utils     import generate_otp, hash_otp, verify_otp, otp_expiry, is_otp_expired
from utils.session_utils import login_user, logout_user
from utils.email_service import send_otp_email, send_password_reset_email
from config.passport     import get_google_auth_url, exchange_code_for_token, get_google_user_info
from middleware.protect  import protect

auth_bp = Blueprint("auth", __name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5000")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _err(msg: str, code: int = 400):
    return jsonify({"success": False, "message": msg}), code

def _ok(data: dict, code: int = 200):
    return jsonify({"success": True, **data}), code


# ── Page Routes ───────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login_page():
    return render_template("index.html")

@auth_bp.route("/dashboard")
@protect
def dashboard_page():
    return render_template("dashboard.html")


# ── 1. Signup ─────────────────────────────────────────────────────────────────

@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    body     = request.get_json(silent=True) or request.form
    name     = (body.get("name") or "").strip()
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not name or not email or not password:
        return _err("Name, email and password are required.")
    if len(password) < 6:
        return _err("Password must be at least 6 characters.")
    if find_by_email(email):
        return _err("An account with this email already exists.")

    otp  = generate_otp()
    user = create_user(name, email, password)

    update_user(email, {
        "otp":        hash_otp(otp),
        "otp_expires": otp_expiry(),
    })

    send_otp_email(email, name, otp)
    return _ok({"message": "Account created! Check your email for the OTP."}, 201)


# ── 2. Verify OTP (signup) ────────────────────────────────────────────────────

@auth_bp.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp_route():
    body  = request.get_json(silent=True) or request.form
    email = (body.get("email") or "").strip().lower()
    otp   = (body.get("otp") or "").strip()

    if not email or not otp:
        return _err("Email and OTP are required.")

    user = find_by_email(email)
    if not user:
        return _err("User not found.", 404)
    if user.get("is_verified"):
        return _err("Email already verified.")
    if not user.get("otp"):
        return _err("No OTP found. Please request a new one.")
    if is_otp_expired(user.get("otp_expires")):
        return _err("OTP has expired. Please request a new one.")
    if not verify_otp(otp, user["otp"]):
        return _err("Invalid OTP.")

    update_user(email, {"is_verified": 1, "otp": None, "otp_expires": None})
    user = find_by_email(email)
    login_user(user)

    return _ok({"message": "Email verified! Redirecting...", "redirect": "/dashboard"})


# ── 3. Resend OTP (signup) ────────────────────────────────────────────────────

@auth_bp.route("/api/auth/resend-otp", methods=["POST"])
def resend_otp():
    body  = request.get_json(silent=True) or request.form
    email = (body.get("email") or "").strip().lower()

    if not email:
        return _err("Email is required.")

    user = find_by_email(email)
    if not user:
        return _err("User not found.", 404)
    if user.get("is_verified"):
        return _err("Email is already verified.")

    otp = generate_otp()
    update_user(email, {"otp": hash_otp(otp), "otp_expires": otp_expiry()})
    send_otp_email(email, user.get("name", ""), otp)

    return _ok({"message": "OTP resent! Check your email."})


# ── 4. Login ──────────────────────────────────────────────────────────────────

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    body     = request.get_json(silent=True) or request.form
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return _err("Email and password are required.")

    user = find_by_email(email)
    if not user or not user.get("password"):
        return _err("Invalid email or password.", 401)
    if not verify_password(password, user["password"]):
        return _err("Invalid email or password.", 401)
    if not user.get("is_verified"):
        return _err("Please verify your email before logging in.", 403)

    login_user(user)
    return _ok({"message": "Login successful!", "redirect": "/dashboard"})


# ── 5. Google OAuth – redirect ────────────────────────────────────────────────

@auth_bp.route("/api/auth/google")
def google_login():
    return redirect(get_google_auth_url())


# ── 6. Google OAuth – callback ────────────────────────────────────────────────

@auth_bp.route("/api/auth/google/callback")
def google_callback():
    code  = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return redirect("/login?error=google_denied")

    try:
        token_data  = exchange_code_for_token(code)
        google_user = get_google_user_info(token_data["access_token"])
    except Exception as e:
        current_app.logger.error(f"[Google OAuth] {e}")
        return redirect("/login?error=google_failed")

    google_id = google_user.get("sub")
    email     = google_user.get("email", "").lower()
    name      = google_user.get("name", "")

    user = find_by_google_id(google_id) or find_by_email(email)

    if not user:
        user = create_user(name, email, google_id=google_id, is_verified=True)
    else:
        if not user.get("google_id"):
            update_user(email, {"google_id": google_id, "is_verified": 1})
        user = find_by_email(email)

    login_user(user)
    return redirect("/dashboard")


# ── 7. Forgot Password — sends OTP to email ───────────────────────────────────

@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    body  = request.get_json(silent=True) or request.form
    email = (body.get("email") or "").strip().lower()

    if not email:
        return _err("Email is required.")

    user = find_by_email(email)
    # Always return OK to prevent email enumeration
    if user:
        otp = generate_otp()
        update_user(email, {
            "reset_otp":         hash_otp(otp),
            "reset_otp_expires": otp_expiry(),   # 10 minutes
            "reset_token":       None,
            "reset_expires":     None,
        })
        # Reuse send_otp_email with a reset subject, or use a dedicated one
        _send_reset_otp_email(email, user.get("name", ""), otp)

    return _ok({"message": "If that email exists, an OTP has been sent."})


def _send_reset_otp_email(to_email, name, otp):
    """Send a password-reset OTP email."""
    from utils.email_service import _send
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#7c3aed">Password Reset — VerboMate AI</h2>
      <p>Hi {name or 'there'},</p>
      <p>Use the OTP below to reset your password (expires in 10 minutes):</p>
      <div style="font-size:36px;font-weight:bold;letter-spacing:8px;
                  text-align:center;background:#F3F4F6;padding:20px;
                  border-radius:8px;margin:24px 0;color:#111">{otp}</div>
      <p style="color:#888;font-size:13px">If you didn't request this, ignore this email.</p>
    </div>"""
    _send(to_email, "Reset your VerboMate password", html)


# ── 8. Verify Reset OTP — returns a short-lived token ────────────────────────

@auth_bp.route("/api/auth/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    body  = request.get_json(silent=True) or request.form
    email = (body.get("email") or "").strip().lower()
    otp   = (body.get("otp") or "").strip()

    if not email or not otp:
        return _err("Email and OTP are required.")

    user = find_by_email(email)
    if not user:
        return _err("User not found.", 404)
    if not user.get("reset_otp"):
        return _err("No OTP found. Please request a new one.")
    if is_otp_expired(user.get("reset_otp_expires")):
        return _err("OTP has expired. Please request a new one.")
    if not verify_otp(otp, user["reset_otp"]):
        return _err("Invalid OTP. Please check and try again.")

    # OTP valid — generate a short-lived reset token (15 min)
    raw_token    = secrets.token_urlsafe(32)
    hashed_token = bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()
    expires      = datetime.now(timezone.utc) + timedelta(minutes=15)

    update_user(email, {
        "reset_otp":         None,
        "reset_otp_expires": None,
        "reset_token":       hashed_token,
        "reset_expires":     expires,
    })

    return _ok({"message": "OTP verified!", "token": raw_token})


# ── 9. Reset Password Page (GET) — kept for email-link flow ──────────────────

@auth_bp.route("/api/auth/reset-password-page", methods=["GET"])
def reset_password_page():
    token = request.args.get("token", "")
    email = request.args.get("email", "")
    return render_template("reset_password.html", token=token, email=email)

# Direct route without /api prefix for convenience
@auth_bp.route("/reset-password")
def reset_password_page_short():
    return render_template("reset_password.html")


# ── 10. Reset Password (POST) ─────────────────────────────────────────────────

@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    body         = request.get_json(silent=True) or request.form
    email        = (body.get("email") or "").strip().lower()
    raw_token    = body.get("token") or ""
    new_password = body.get("password") or ""

    if not email or not raw_token or not new_password:
        return _err("Email, token and new password are required.")
    if len(new_password) < 6:
        return _err("Password must be at least 6 characters.")

    user = find_by_email(email)
    if not user or not user.get("reset_token"):
        return _err("Invalid or expired reset link. Please start over.", 400)

    expires = user.get("reset_expires")
    if expires:
        if hasattr(expires, "tzinfo") and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return _err("Reset session has expired. Please start over.")

    if not bcrypt.checkpw(raw_token.encode(), user["reset_token"].encode()):
        return _err("Invalid or expired token. Please start over.", 400)

    new_hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    update_user(email, {"password": new_hashed, "reset_token": None, "reset_expires": None})

    return _ok({"message": "Password reset! You can now log in.", "redirect": "/login"})


# ── 11. Get Current User ──────────────────────────────────────────────────────

@auth_bp.route("/api/auth/me", methods=["GET"])
@protect
def get_me():
    return _ok({"user": safe_user(g.user)})


# ── 12. Logout ────────────────────────────────────────────────────────────────

@auth_bp.route("/api/auth/logout", methods=["POST", "GET"])
def logout():
    logout_user()
    return redirect("/login")

# @app.route("/vocabulary")
# def vocabulary():
#     return render_template("vocabulary.html")