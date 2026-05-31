import bcrypt
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def _get_conn():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "verboma"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

def find_by_email(email):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
            return cur.fetchone()
    finally:
        conn.close()

def find_by_id(user_id):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()
    finally:
        conn.close()

def find_by_google_id(google_id):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
            return cur.fetchone()
    finally:
        conn.close()

def create_user(name, email, password=None, google_id=None, is_verified=False):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email, password, google_id, is_verified) VALUES (%s,%s,%s,%s,%s)",
                (name, email.lower().strip(), hashed, google_id, int(is_verified))
            )
        return find_by_email(email)
    finally:
        conn.close()

def update_user(email, fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [email.lower().strip()]
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {set_clause} WHERE email = %s", values)
    finally:
        conn.close()

def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def safe_user(user):
    return {
        "id": user["id"],
        "name": user.get("name"),
        "email": user.get("email"),
        "is_verified": bool(user.get("is_verified")),
        "created_at": str(user.get("created_at")),
    }