# ─────────────────────────────────────────────────────────────────────────────
# APPEND THIS BLOCK to the bottom of your existing db.py
# It adds 3 new tables without touching anything you already have.
# Then call init_progress_tables() inside init_db() after the users table block.
# ─────────────────────────────────────────────────────────────────────────────

def init_progress_tables():
    """Create progress-tracking tables if they don't exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:

            # ── Overall stats per user ────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    id                      INT AUTO_INCREMENT PRIMARY KEY,
                    user_id                 INT NOT NULL UNIQUE,
                    words_learned           INT     DEFAULT 0,
                    words_learned_week      INT     DEFAULT 0,
                    practice_minutes        INT     DEFAULT 0,
                    practice_minutes_week   INT     DEFAULT 0,
                    avg_accuracy            DECIMAL(5,1) DEFAULT 0.0,
                    accuracy_change_month   DECIMAL(5,1) DEFAULT 0.0,
                    global_rank             INT     DEFAULT 9999,
                    rank_change             INT     DEFAULT 0,
                    streak_days             INT     DEFAULT 0,
                    last_streak_date        DATE    DEFAULT NULL,
                    xp_total                INT     DEFAULT 0,
                    xp_level                INT     DEFAULT 1,
                    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP
                                            ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ── Per-module progress percentage ────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_module_progress (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    user_id      INT NOT NULL,
                    module_key   VARCHAR(50) NOT NULL,
                    progress_pct INT DEFAULT 0,
                    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_user_module (user_id, module_key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ── Activity log (recent activity feed) ───────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id             INT AUTO_INCREMENT PRIMARY KEY,
                    user_id        INT NOT NULL,
                    module_key     VARCHAR(50),
                    activity_title VARCHAR(200),
                    activity_meta  VARCHAR(200),
                    xp_earned      INT DEFAULT 0,
                    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        print("[DB] Progress tables ready!")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# In your existing init_db() function, add this one line at the end:
#
#   init_progress_tables()
#
# So it becomes:
#
#   def init_db():
#       ...existing code...
#       init_progress_tables()   ← ADD THIS
#
# ─────────────────────────────────────────────────────────────────────────────