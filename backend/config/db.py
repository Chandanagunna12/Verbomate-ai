import os
import pymysql
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Return a new MySQL connection."""
    return pymysql.connect(
        host     = os.getenv("MYSQL_HOST", "localhost"),
        port     = int(os.getenv("MYSQL_PORT", 3306)),
        user     = os.getenv("MYSQL_USER", "root"),
        password = os.getenv("MYSQL_PASSWORD", ""),
        database = os.getenv("MYSQL_DB", "verboma"),
        cursorclass = pymysql.cursors.DictCursor,
        autocommit  = True,
    )


def init_db():
    """Create tables if they don't exist, and add missing columns safely."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Create table with ALL columns (new installs)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id                 INT AUTO_INCREMENT PRIMARY KEY,
                    name               VARCHAR(100)  NOT NULL,
                    email              VARCHAR(150)  NOT NULL UNIQUE,
                    password           VARCHAR(255)  DEFAULT NULL,
                    google_id          VARCHAR(100)  DEFAULT NULL,
                    is_verified        TINYINT(1)    DEFAULT 0,
                    otp                VARCHAR(255)  DEFAULT NULL,
                    otp_expires        DATETIME      DEFAULT NULL,
                    reset_otp          VARCHAR(255)  DEFAULT NULL,
                    reset_otp_expires  DATETIME      DEFAULT NULL,
                    reset_token        VARCHAR(255)  DEFAULT NULL,
                    reset_expires      DATETIME      DEFAULT NULL,
                    created_at         DATETIME      DEFAULT CURRENT_TIMESTAMP,
                    updated_at         DATETIME      DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ── Safely add missing columns for existing databases ──────────
            _add_column_if_missing(cur, "reset_otp",         "VARCHAR(255) DEFAULT NULL AFTER otp_expires")
            _add_column_if_missing(cur, "reset_otp_expires", "DATETIME     DEFAULT NULL AFTER reset_otp")
            _add_column_if_missing(cur, "reset_token",       "VARCHAR(255) DEFAULT NULL AFTER reset_otp_expires")
            _add_column_if_missing(cur, "reset_expires",     "DATETIME     DEFAULT NULL AFTER reset_token")

        print("[DB] Tables ready!")
    finally:
        conn.close()

    # ── Create progress tracking tables ───────────────────────────────────────
    init_progress_tables()


def _add_column_if_missing(cur, column_name: str, column_def: str):
    """Add a column to `users` only if it doesn't already exist."""
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'users'
          AND COLUMN_NAME  = %s
    """, (column_name,))
    row = cur.fetchone()
    if row and row["cnt"] == 0:
        cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
        print(f"[DB] Added missing column: {column_name}")


# ── Progress Tables ───────────────────────────────────────────────────────────

def init_progress_tables():
    """Create progress-tracking tables if they don't exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:

            # Overall stats per user
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    id                      INT AUTO_INCREMENT PRIMARY KEY,
                    user_id                 INT NOT NULL UNIQUE,
                    words_learned           INT          DEFAULT 0,
                    words_learned_week      INT          DEFAULT 0,
                    practice_minutes        INT          DEFAULT 0,
                    practice_minutes_week   INT          DEFAULT 0,
                    avg_accuracy            DECIMAL(5,1) DEFAULT 0.0,
                    accuracy_change_month   DECIMAL(5,1) DEFAULT 0.0,
                    global_rank             INT          DEFAULT 9999,
                    rank_change             INT          DEFAULT 0,
                    streak_days             INT          DEFAULT 0,
                    last_streak_date        DATE         DEFAULT NULL,
                    xp_total                INT          DEFAULT 0,
                    xp_level                INT          DEFAULT 1,
                    updated_at              DATETIME     DEFAULT CURRENT_TIMESTAMP
                                            ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Per-module progress percentage
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_module_progress (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    user_id      INT         NOT NULL,
                    module_key   VARCHAR(50) NOT NULL,
                    progress_pct INT         DEFAULT 0,
                    updated_at   DATETIME    DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_user_module (user_id, module_key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Activity log (recent activity feed)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id             INT AUTO_INCREMENT PRIMARY KEY,
                    user_id        INT          NOT NULL,
                    module_key     VARCHAR(50),
                    activity_title VARCHAR(200),
                    activity_meta  VARCHAR(200),
                    xp_earned      INT          DEFAULT 0,
                    created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        print("[DB] Progress tables ready!")
    finally:
        conn.close()