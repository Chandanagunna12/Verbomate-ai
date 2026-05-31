import random
import string
import bcrypt
from datetime import datetime, timedelta, timezone

OTP_LENGTH  = 6
OTP_EXPIRES = 10  # minutes


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    try:
        return bcrypt.checkpw(plain_otp.encode(), hashed_otp.encode())
    except Exception:
        return False


def otp_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRES)


def is_otp_expired(expiry) -> bool:
    if expiry is None:
        return True
    if hasattr(expiry, "tzinfo") and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expiry