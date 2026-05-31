from flask import Blueprint, request, jsonify, session
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

progress_bp = Blueprint("progress", __name__)


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


# ── GET /api/progress/me ─────────────────────────────────────────────────────
@progress_bp.route("/api/progress/me", methods=["GET"])
def get_my_progress():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    conn = _get_conn()
    try:
        with conn.cursor() as cur:

            # ── overall stats ────────────────────────────────────────────────
            cur.execute("SELECT * FROM user_progress WHERE user_id = %s", (user_id,))
            progress = cur.fetchone()

            # ── per-module progress ──────────────────────────────────────────
            cur.execute("""
                SELECT module_key, progress_pct
                FROM user_module_progress
                WHERE user_id = %s
            """, (user_id,))
            modules_raw = cur.fetchall()
            modules = {r["module_key"]: r["progress_pct"] for r in modules_raw}

            # ── recent activity (last 4 entries) ────────────────────────────
            cur.execute("""
                SELECT module_key, activity_title, activity_meta, xp_earned, created_at
                FROM user_activity
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 4
            """, (user_id,))
            activity = cur.fetchall()

        if not progress:
            return jsonify({
                "success": True,
                "progress": {
                    "words_learned": 0,
                    "words_learned_week": 0,
                    "practice_minutes": 0,
                    "practice_minutes_week": 0,
                    "avg_accuracy": 0,
                    "accuracy_change_month": 0,
                    "global_rank": 0,
                    "rank_change": 0,
                    "streak_days": 0,
                    "xp_total": 0,
                    "xp_level": 1,
                },
                "modules": {},
                "activity": [],
            })

        # Serialize datetime fields in activity
        clean_activity = []
        for a in activity:
            clean_activity.append({
                "module_key":     a["module_key"],
                "activity_title": a["activity_title"],
                "activity_meta":  a["activity_meta"],
                "xp_earned":      a["xp_earned"],
                "created_at":     str(a["created_at"]),
            })

        return jsonify({
            "success": True,
            "progress": {
                "words_learned":         progress["words_learned"],
                "words_learned_week":    progress["words_learned_week"],
                "practice_minutes":      progress["practice_minutes"],
                "practice_minutes_week": progress["practice_minutes_week"],
                "avg_accuracy":          float(progress["avg_accuracy"]),
                "accuracy_change_month": float(progress["accuracy_change_month"]),
                "global_rank":           progress["global_rank"],
                "rank_change":           progress["rank_change"],
                "streak_days":           progress["streak_days"],
                "xp_total":              progress["xp_total"],
                "xp_level":              progress["xp_level"],
            },
            "modules":  modules,
            "activity": clean_activity,
        })

    finally:
        conn.close()


# ── POST /api/progress/update ────────────────────────────────────────────────
@progress_bp.route("/api/progress/update", methods=["POST"])
def update_progress():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    data = request.get_json(force=True) or {}
    module_key     = data.get("module_key", "general")
    words          = int(data.get("words_learned", 0))
    minutes        = int(data.get("practice_minutes", 0))
    accuracy       = data.get("accuracy")
    xp             = int(data.get("xp_earned", 0))
    activity_title = data.get("activity_title", "")
    activity_meta  = data.get("activity_meta", "")
    module_pct     = data.get("module_progress_pct")

    conn = _get_conn()
    try:
        with conn.cursor() as cur:

            # ── upsert user_progress row ─────────────────────────────────────
            cur.execute("SELECT id FROM user_progress WHERE user_id = %s", (user_id,))
            exists = cur.fetchone()

            if exists:
                sets = [
                    "words_learned = words_learned + %s",
                    "words_learned_week = words_learned_week + %s",
                    "practice_minutes = practice_minutes + %s",
                    "practice_minutes_week = practice_minutes_week + %s",
                    "xp_total = xp_total + %s",
                ]
                vals = [words, words, minutes, minutes, xp]

                if accuracy is not None:
                    sets.append("avg_accuracy = ROUND(avg_accuracy * 0.8 + %s * 0.2, 1)")
                    vals.append(float(accuracy))

                vals.append(user_id)
                cur.execute(
                    f"UPDATE user_progress SET {', '.join(sets)} WHERE user_id = %s",
                    vals
                )
                cur.execute("""
                    UPDATE user_progress
                    SET xp_level = GREATEST(1, FLOOR(xp_total / 500))
                    WHERE user_id = %s
                """, (user_id,))

            else:
                cur.execute("""
                    INSERT INTO user_progress
                        (user_id, words_learned, words_learned_week,
                         practice_minutes, practice_minutes_week,
                         avg_accuracy, accuracy_change_month,
                         global_rank, rank_change,
                         streak_days, xp_total, xp_level)
                    VALUES (%s,%s,%s,%s,%s,%s,0,9999,0,1,%s,1)
                """, (
                    user_id, words, words, minutes, minutes,
                    float(accuracy) if accuracy is not None else 0,
                    xp
                ))

            # ── upsert user_module_progress ──────────────────────────────────
            if module_pct is not None:
                cur.execute("""
                    INSERT INTO user_module_progress (user_id, module_key, progress_pct)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE progress_pct = %s
                """, (user_id, module_key, int(module_pct), int(module_pct)))

            # ── insert activity log ──────────────────────────────────────────
            if activity_title:
                cur.execute("""
                    INSERT INTO user_activity
                        (user_id, module_key, activity_title, activity_meta, xp_earned)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, module_key, activity_title, activity_meta, xp))

        return jsonify({"success": True})

    finally:
        conn.close()


# ── POST /api/progress/streak ────────────────────────────────────────────────
@progress_bp.route("/api/progress/streak", methods=["POST"])
def update_streak():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT streak_days, last_streak_date
                FROM user_progress WHERE user_id = %s
            """, (user_id,))
            row = cur.fetchone()

            if not row:
                return jsonify({"success": False, "error": "No progress row"})

            from datetime import date
            today = date.today()
            last  = row.get("last_streak_date")

            if last is None or (today - last).days == 1:
                cur.execute("""
                    UPDATE user_progress
                    SET streak_days = streak_days + 1, last_streak_date = %s
                    WHERE user_id = %s
                """, (today, user_id))
            elif (today - last).days > 1:
                cur.execute("""
                    UPDATE user_progress
                    SET streak_days = 1, last_streak_date = %s
                    WHERE user_id = %s
                """, (today, user_id))

        return jsonify({"success": True})
    finally:
        conn.close()