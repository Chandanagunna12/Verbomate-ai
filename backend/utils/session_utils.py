from flask import session


def login_user(user: dict) -> None:
    """Store user info in Flask session."""
    session["user_id"]    = user["id"]
    session["user_email"] = user["email"]
    session["user_name"]  = user["name"]
    session.permanent     = True


def logout_user() -> None:
    """Clear the session."""
    session.clear()


def get_current_user_id() -> int | None:
    return session.get("user_id")


def is_logged_in() -> bool:
    return "user_id" in session