from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from models.user import find_by_id


def protect(f):
    """
    Decorator to protect routes using Flask session.

    - For API routes  → returns 401 JSON
    - For page routes → redirects to /login

    Usage:
        @auth_bp.route("/dashboard")
        @protect
        def dashboard():
            user = g.user  # set by this decorator
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import g
        user_id = session.get("user_id")

        if not user_id:
            # If it's an AJAX/API call, return JSON
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Login required."}), 401
            return redirect(url_for("auth.login_page"))

        user = find_by_id(user_id)
        if not user:
            session.clear()
            return redirect(url_for("auth.login_page"))

        g.user = user
        return f(*args, **kwargs)

    return decorated