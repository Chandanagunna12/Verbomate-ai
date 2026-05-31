import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

print("Testing email config...")
print(f"MAIL_SERVER: {os.getenv('MAIL_SERVER')}")
print(f"MAIL_PORT: {os.getenv('MAIL_PORT')}")
print(f"MAIL_USERNAME: {os.getenv('MAIL_USERNAME')}")
print(f"MAIL_PASSWORD length: {len(os.getenv('MAIL_PASSWORD', ''))}")

try:
    server = smtplib.SMTP(os.getenv("MAIL_SERVER", "smtp.gmail.com"), 587)
    server.starttls()
    print("TLS connection OK")
    server.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
    print("Login OK!")
    server.quit()
    print("Email config is working!")
except Exception as e:
    print(f"ERROR: {e}")