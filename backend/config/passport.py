import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPES           = "openid email profile"


def get_google_auth_url(state: str = "") -> str:
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "state":         state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_code_for_token(code: str) -> dict:
    payload = {
        "code":          code,
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "grant_type":    "authorization_code",
    }
    resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_google_user_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(GOOGLE_USERINFO, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()