import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def _send(to_email, subject, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = os.getenv("MAIL_DEFAULT_SENDER")
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))          # ✅ added "utf-8"
        with smtplib.SMTP(os.getenv("MAIL_SERVER", "smtp.gmail.com"),
                          int(os.getenv("MAIL_PORT", 587))) as server:
            server.starttls()
            server.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
            server.sendmail(os.getenv("MAIL_DEFAULT_SENDER"), to_email, msg.as_bytes())  # ✅ as_bytes()
        return True
    except Exception as e:
        print(f"[Email Error] {e}")
        return False

def send_otp_email(to_email, name, otp):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#4F46E5">Welcome to Verboma, {name}!</h2>
      <p>Your OTP is (expires in 10 minutes):</p>
      <div style="font-size:36px;font-weight:bold;letter-spacing:8px;
                  text-align:center;background:#F3F4F6;padding:20px;
                  border-radius:8px;margin:24px 0">{otp}</div>
    </div>"""
    return _send(to_email, "Verify your Verboma account", html)

def send_password_reset_email(to_email, name, reset_link):
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#4F46E5">Password Reset</h2>
      <p>Hi {name}, click below to reset your password (expires in 15 minutes):</p>
      <a href="{reset_link}" style="display:inline-block;background:#4F46E5;color:#fff;
         padding:12px 24px;border-radius:6px;text-decoration:none;margin:20px 0">
        Reset Password
      </a>
    </div>"""
    return _send(to_email, "Reset your Verboma password", html)