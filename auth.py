"""
auth.py
-------
Authentication + account validation. Accounts themselves now live in the
`users` table (db.py) instead of a hardcoded dictionary — every student
registers their own unique username, email, and password, and can
recover a forgotten password via emailed one-time code (see
email_service.py and app_pages/login.py).

Security notes (documented so it's easy to harden further for a real
production rollout — see SETUP_GUIDE.md):
  * Passwords are stored as salted PBKDF2-SHA256 hashes (`hash_password` in
    db.py). Accounts created before the switch still hold an unsalted SHA-256
    digest; login still accepts one, but `app.py` routes those accounts
    through `show_mandatory_password_change()` on first sign-in, which
    re-hashes the password to PBKDF2.
  * A lightweight per-session login-attempt throttle is included below
    as a cheap defence against rapid brute-forcing from the UI.
"""

from __future__ import annotations

import re
import time

import db

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 30

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{4,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def authenticate(username: str, password: str):
    """Returns (success: bool, role: str | None)."""
    ok, user = db.verify_login(username, password)
    if not ok:
        return False, None
    return True, user["role"]


def authenticate_by_email(email: str, password: str):
    """Email-based variant — used by the student sign-in form.
    Returns (success: bool, role: str | None, user_dict | None)."""
    ok, user = db.verify_login_by_email(email, password)
    if not ok:
        return False, None, None
    return True, user["role"], user


def validate_registration(username, email, full_name, password, confirm_password):
    """Returns a list of human-readable problems; empty list = all good."""
    problems = []
    username = (username or "").strip()
    email = (email or "").strip()
    full_name = (full_name or "").strip()

    if not USERNAME_RE.match(username):
        problems.append("Username must be 4–32 characters: letters, numbers, dots, dashes, or underscores only.")
    elif db.username_exists(username):
        problems.append("That username is already taken — please choose another.")

    if not EMAIL_RE.match(email):
        problems.append("Please enter a valid email address.")
    elif db.email_exists(email):
        problems.append("An account already exists with that email address.")

    if len(full_name) < 2:
        problems.append("Please enter your full name.")

    if len(password) < 8:
        problems.append("Password must be at least 8 characters long.")
    elif password != confirm_password:
        problems.append("Passwords do not match.")

    return problems


def check_lockout(session_state) -> float:
    """Returns seconds remaining in lockout (0 if not locked out)."""
    locked_until = session_state.get("_login_locked_until", 0)
    remaining = locked_until - time.time()
    return max(0.0, remaining)


def register_failed_attempt(session_state):
    attempts = session_state.get("_login_attempts", 0) + 1
    session_state["_login_attempts"] = attempts
    if attempts >= MAX_LOGIN_ATTEMPTS:
        session_state["_login_locked_until"] = time.time() + LOCKOUT_SECONDS
        session_state["_login_attempts"] = 0


def clear_attempts(session_state):
    session_state["_login_attempts"] = 0
    session_state["_login_locked_until"] = 0
