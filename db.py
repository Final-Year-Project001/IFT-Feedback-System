"""
db.py
-----
SQLite persistence layer — single database file, cached connection via
st.cache_resource, with Write-Ahead Logging (WAL) and 30s busy timeout.

Tables:
  users              — accounts (student AND admin), hashed with PBKDF2-HMAC-SHA256
                       with per-user salt and legacy SHA-256 fallback verification.
  password_resets     — one-time OTP codes for the "forgot password" flow.
  academic_sessions   — academic years (e.g. 2025/2026) with active/default flags.
  feedback            — student submissions with UNIQUE(username, category, session).
  admin_notes         — per-category administrative action notes.
  admin_audit_log     — tamper-evident audit log with snapshots for guarded deletion.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from config import (
    CURRENT_SESSION,
    ALL_SESSIONS_LABEL,
    ADMIN_SEED_ACCOUNTS,
    SEED_ADMINS_ON_STARTUP,
)

# Optional durability layer. `storage` is a no-op unless a backup repository and
# token are configured, so importing it here cannot change local behaviour — and
# `storage` deliberately imports `db` only lazily, which keeps this from being a
# circular import. The import is guarded anyway: a durability aid must never be
# able to stop the database from opening.
try:
    import storage
except Exception:  # pragma: no cover - defensive only
    storage = None

try:
    import db_backend
except Exception:  # pragma: no cover - defensive only
    db_backend = None

DB_PATH = str(Path(__file__).resolve().parent / "futo_feedback.db")

# Every value of `session` that means "do not filter by session" (C-06).
#
# The canonical one is `config.ALL_SESSIONS_LABEL`, and nothing generates
# anything but that any more. The two legacy spellings stay here on purpose:
# this list is a READ-side guard, and an admin's browser can still be holding
# the old value in a query parameter or a cached widget key from before the
# rename. Dropping them would turn a harmless stale label into a silently
# empty dashboard — the filter matches nothing and looks like the data is gone.
_AGGREGATE_ALIASES = frozenset({ALL_SESSIONS_LABEL, "All Sessions", "All"})


_ACTIVE_BACKEND = ["sqlite"]


def _note_backend(name: str) -> None:
    """Records which backend this process opened. Read by `get_db` consumers."""
    _ACTIVE_BACKEND[0] = name


def active_backend() -> str:
    """`"sqlite"` or `"postgresql"` — which database this process is using.

    Exposed so the sidebar can state it plainly. During a presentation that is
    worth more than it looks: if the app ever comes up on the wrong backend, the
    difference is visible immediately rather than discovered as "my feedback is
    gone".
    """
    return _ACTIVE_BACKEND[0]


@st.cache_resource
def _connect():
    """Opens the shared connection and creates/migrates the schema.

    The `@st.cache_resource` body runs ONCE per server process, so anything
    that has to happen repeatedly cannot live in here — see `get_db`, which is
    the plain wrapper every caller actually uses.
    Two backends, chosen by configuration and nothing else.

      * **SQLite (default).** A file beside this module. Used whenever
        `FUTO_POSTGRES_URL` is unset, which is every local run and every test.
      * **PostgreSQL.** Selected by `FUTO_POSTGRES_URL`, for deployment on a host
        whose disk is wiped between requests. `db_backend` translates the SQL as
        it passes through — placeholders and the `AUTOINCREMENT` DDL — so the
        functions below are written once and work against either.

    The two paths cannot silently merge: the backend is chosen once per process,
    and `DB_PATH` is not touched at all when PostgreSQL is in use.
    """
    if db_backend is not None and db_backend.is_postgres():
        conn = db_backend.connect()
        if conn is None:
            raise RuntimeError(
                "FUTO_POSTGRES_URL is set but the connection could not be "
                "opened. Check the URL, the credentials, and that the host "
                "accepts connections from the deployment platform."
            )
        _note_backend("postgresql")
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        _note_backend("sqlite")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            level TEXT,
            created_at TEXT NOT NULL
        )"""
    )

    conn.execute(
        """CREATE TABLE IF NOT EXISTS password_resets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reset_user ON password_resets(username)")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS academic_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL
        )"""
    )

    # Seed default session if empty
    sess_row = conn.execute("SELECT COUNT(*) FROM academic_sessions").fetchone()
    if sess_row and sess_row[0] == 0:
        conn.execute(
            """INSERT INTO academic_sessions (session_name, is_active, is_default, created_at, created_by)
               VALUES (?, 1, 1, ?, 'system')""",
            (CURRENT_SESSION, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )

    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL,
            student_level TEXT,
            rating INTEGER,
            comment TEXT,
            timestamp TEXT,
            additional_info TEXT,
            sentiment TEXT,
            sentiment_score REAL,
            sentiment_engine TEXT,
            sentiment_confidence REAL,
            sentiment_cues TEXT,
            admin_corrected_sentiment TEXT,
            corrected_by TEXT,
            corrected_at TEXT,
            context_data TEXT,
            session TEXT NOT NULL DEFAULT '{CURRENT_SESSION}',
            UNIQUE(username, category, session)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cat ON feedback(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON feedback(session)")

    # Ensure all columns exist defensively.
    #
    # This is load-bearing, not tuning: it is how an older database gains the
    # columns added in later versions of this app. `PRAGMA table_info` has no
    # PostgreSQL equivalent, so the column list is read from
    # `information_schema` instead — which is why this is the one PRAGMA in the
    # file that gets translated rather than dropped. Getting it wrong fails at
    # startup, on every deploy, before anyone sees the app.
    if active_backend() == "postgresql":
        existing_cols = {row[0] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?",
            ("feedback",)).fetchall()}
    else:
        existing_cols = {row[1] for row in
                         conn.execute("PRAGMA table_info(feedback)").fetchall()}
    for col_name, col_type in [
        ("sentiment_score", "REAL"), ("sentiment_engine", "TEXT"),
        ("sentiment_confidence", "REAL"), ("sentiment_cues", "TEXT"),
        ("admin_corrected_sentiment", "TEXT"), ("corrected_by", "TEXT"),
        ("corrected_at", "TEXT"), ("session", "TEXT"),
    ]:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE feedback ADD COLUMN {col_name} {col_type}")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_notes(
            category TEXT PRIMARY KEY,
            note TEXT,
            updated_by TEXT,
            updated_at TEXT
        )"""
    )

    # F-01: Admin Audit Log with snapshot JSON for guarded deletion & rollback
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target_username TEXT NOT NULL,
            target_full_name TEXT,
            target_email TEXT,
            target_role TEXT,
            target_level TEXT,
            performed_by TEXT NOT NULL,
            performed_at TEXT NOT NULL,
            feedback_rows_deleted INTEGER NOT NULL DEFAULT 0,
            reset_rows_deleted INTEGER NOT NULL DEFAULT 0,
            admin_corrections_deleted INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            snapshot TEXT
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON admin_audit_log(target_username)")

    # F-08: the tombstone that stops `seed_admins` recreating a deliberately
    # deleted account. Separate from the audit log so that expiring audit rows
    # cannot quietly un-tombstone a deletion — see _admin_deletion_tombstones().
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_deletion_tombstones(
            username TEXT PRIMARY KEY,
            created_at TEXT
        )"""
    )

    # Housekeeping: purge expired/used OTP codes
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM password_resets WHERE used = 1 OR expires_at < ?", (now_str,))
    conn.commit()

    # Sweep once at connect, so a freshly started process never shows an
    # expired entry. `get_db()` (below) keeps it current from then on — this
    # call alone would only ever fire once per process, which is exactly the
    # bug that made the trail grow forever.
    _purge_expired_audit_rows(conn)
    return conn


# How often the retention sweep is allowed to run. Hourly is far more often
# than the 5-day window needs and cheap enough to be invisible (one indexed
# DELETE that usually matches zero rows).
_SWEEP_INTERVAL_SECONDS = 3600
_last_sweep_at = 0.0


def get_db():
    """Returns the shared connection, running periodic housekeeping on the way.

    Every module-level function in this file calls this, so it is the one place
    that is guaranteed to run on every page load — which is what makes the
    retention sweep actually happen.

    It is a plain wrapper rather than the `@st.cache_resource` itself on
    purpose. When the sweep lived inside the cached function body it ran
    exactly ONCE per server process, so on a long-running deployment the audit
    trail kept accumulating expired entries indefinitely and an administrator
    saw deletions that should have aged out weeks earlier. The fix is to make
    the cache hold only the connection, and put the time-gated work outside it.
    """
    global _last_sweep_at
    conn = _connect()

    # Durable-backup heartbeat. This is the cheapest possible call — a stat and
    # a comparison — and it only does work when a backup repository is actually
    # configured. It lives here because this function is already documented as
    # the one place guaranteed to run on every page load, so the uploader notices
    # a changed database without `db.py` knowing anything about how it works.
    if storage is not None:
        try:
            storage.note_activity()
        except Exception:
            pass

    now = time.time()
    if now - _last_sweep_at >= _SWEEP_INTERVAL_SECONDS:
        _last_sweep_at = now
        try:
            _purge_expired_audit_rows(conn)
        except Exception:
            # Housekeeping must never take the app down with it. A failed sweep
            # means an expired entry lingers until the next one succeeds.
            conn.rollback()
    return conn


# The test suite (and anything else that needs a genuinely fresh connection)
# calls `db.get_db.clear()`. Preserve that entry point on the wrapper so the
# cache can still be dropped, and so `get_db` keeps reading as the public API.
get_db.clear = _connect.clear


# ══════════════════════════════════════════════════════════════
#  USERS / ACCOUNTS & CRYPTOGRAPHY (PBKDF2-HMAC-SHA256)
# ══════════════════════════════════════════════════════════════

def hash_password(password: str, salt: str | None = None) -> str:
    """Derives a salted PBKDF2-HMAC-SHA256 hash (100,000 rounds)."""
    if not salt:
        salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"pbkdf2:sha256:100000${salt}${derived}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies against PBKDF2 hash, with backwards-compatible legacy SHA-256 fallback."""
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2:sha256:"):
        parts = stored_hash.split("$")
        if len(parts) == 3:
            salt = parts[1]
            expected = parts[2]
            calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac.compare_digest(calc, expected)
    # Legacy unsalted SHA-256 fallback
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


def _admin_deletion_tombstones() -> set[str]:
    """Usernames of accounts that were deliberately deleted and not restored.

    `seed_admins` runs on every app start with an `if not exists` check, so
    without this a seeded admin removed through the User Management page
    reappeared on the next page load with its config password (`password123`)
    intact — the deletion silently undid itself.

    This used to be derived from `admin_audit_log`, which made the tombstone's
    lifetime depend on how long audit rows happen to be kept. Once audit rows
    started expiring (F-08) that coupling became an actual bug: a tombstone
    would silently evaporate 5 days after the deletion, and `seed_admins` would
    helpfully recreate the account with the default password. So the
    tombstone now lives in its own table with no expiry, and the audit log is
    free to be purged without consequence. A restore clears it.
    """
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT username FROM admin_deletion_tombstones WHERE username IS NOT NULL"
        ).fetchall()
    except Exception:
        return set()
    return {(r[0] or "").strip().lower() for r in rows if r[0]}


def _set_deletion_tombstone(username: str, present: bool):
    """Records or clears the tombstone for one account.

    Best-effort: the deletion itself has already been committed by the time
    this is called, so a failure here must not roll the account back.
    """
    key = (username or "").strip().lower()
    if not key:
        return
    try:
        conn = get_db()
        if present:
            # SQLite spells this `INSERT OR REPLACE`; PostgreSQL spells it as an
            # explicit conflict clause. Written out rather than rewritten by
            # pattern because the two conflict actions are genuinely different
            # operations, and `OR REPLACE` also silently resets columns that
            # `DO UPDATE` would leave alone.
            if active_backend() == "postgresql":
                conn.execute(
                    "INSERT INTO admin_deletion_tombstones (username, created_at) "
                    "VALUES (?, datetime('now')) "
                    "ON CONFLICT (username) DO UPDATE SET created_at = EXCLUDED.created_at",
                    (key,),
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO admin_deletion_tombstones (username, created_at) "
                    "VALUES (?, datetime('now'))",
                    (key,),
                )
        else:
            conn.execute("DELETE FROM admin_deletion_tombstones WHERE username = ?", (key,))
        conn.commit()
    except Exception:
        pass


def seed_admins(admin_accounts: list):
    """Insert seed admin accounts from config if configured and not already existing."""
    if not SEED_ADMINS_ON_STARTUP:
        return
    conn = get_db()
    tombstoned = _admin_deletion_tombstones()
    for acct in admin_accounts:
        # Check if already exists (case-insensitive)
        row = conn.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?)", (acct["username"],)).fetchone()
        if row:
            continue
        if (acct["username"] or "").lower() in tombstoned:
            # Deleted through the admin UI — honour that decision instead of
            # resurrecting the account on the next reload.
            continue
        conn.execute(
            """INSERT INTO users (username, email, full_name, password_hash, role, level, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (acct["username"], acct["email"], acct["full_name"],
             hash_password(acct["password"]), "admin", "Staff",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    conn.commit()


def username_exists(username: str) -> bool:
    """Case-insensitive check — usernames are treated with canonical identity."""
    conn = get_db()
    row = conn.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?)", ((username or "").strip(),)).fetchone()
    return row is not None


def email_exists(email: str) -> bool:
    """Case-insensitive check for email uniqueness."""
    conn = get_db()
    row = conn.execute("SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)", ((email or "").strip(),)).fetchone()
    return row is not None


def create_user(username: str, email: str, full_name: str, password: str, role: str, level: str) -> tuple[bool, str]:
    """Inserts a new user record with friendly error handling."""
    conn = get_db()
    u_clean = (username or "").strip()
    e_clean = (email or "").strip().lower()
    fn_clean = (full_name or "").strip()
    try:
        conn.execute(
            """INSERT INTO users (username, email, full_name, password_hash, role, level, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (u_clean, e_clean, fn_clean, hash_password(password), role, level,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError as e:
        conn.rollback()
        err = str(e).lower()
        if "username" in err:
            return False, "This username is already taken. Please choose another."
        elif "email" in err:
            return False, "An account is already registered with this email address."
        return False, "An account with these details already exists."
    except Exception as e:
        conn.rollback()
        return False, f"Could not create account: {e}"


def get_user(username: str) -> dict | None:
    """Case-insensitive lookup by username."""
    conn = get_db()
    row = conn.execute(
        "SELECT username, email, full_name, password_hash, role, level FROM users WHERE LOWER(username) = LOWER(?)",
        ((username or "").strip(),),
    ).fetchone()
    if not row:
        return None
    return {"username": row[0], "email": row[1], "full_name": row[2],
            "password_hash": row[3], "role": row[4], "level": row[5]}


def get_user_by_email(email: str) -> dict | None:
    """Case-insensitive lookup by email address."""
    conn = get_db()
    row = conn.execute(
        "SELECT username, email, full_name, password_hash, role, level FROM users WHERE LOWER(email) = LOWER(?)",
        ((email or "").strip(),),
    ).fetchone()
    if not row:
        return None
    return {"username": row[0], "email": row[1], "full_name": row[2],
            "password_hash": row[3], "role": row[4], "level": row[5]}


def password_is_legacy(username: str) -> bool:
    """True if this account's stored hash is the pre-PBKDF2 unsalted SHA-256.

    A legacy row is not rejected — `verify_password` still accepts one, so
    those accounts can sign in — but the hash it holds is worth attacking with
    precomputed tables, and it stays that way until the password is changed.

    Login no longer silently re-hashes on success (it used to, which upgraded
    the row but left the user on the password they had already been reusing
    everywhere else). Instead the caller asks this and forces a real change,
    so both the storage and the habit are fixed at once.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE LOWER(username) = LOWER(?)",
        ((username or "").strip(),),
    ).fetchone()
    if row is None or not row[0]:
        return False
    return not str(row[0]).startswith("pbkdf2:sha256:")


def verify_login(username: str, password: str) -> tuple[bool, dict | None]:
    """Returns (success: bool, user_dict_or_None)."""
    user = get_user(username)
    if user is None:
        return False, None
    if verify_password(password, user["password_hash"]):
        return True, user
    return False, None


def verify_login_by_email(email: str, password: str) -> tuple[bool, dict | None]:
    """Email-based login for students."""
    user = get_user_by_email(email)
    if user is None:
        return False, None
    if verify_password(password, user["password_hash"]):
        return True, user
    return False, None


def update_password(username: str, new_password: str):
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE LOWER(username) = LOWER(?)",
        (hash_password(new_password), (username or "").strip()),
    )
    conn.commit()


def admin_set_password(username: str, new_password: str) -> tuple[bool, str]:
    """Resets another account's password from the admin User Management screen.

    This is the supported replacement for the old "delete futo_feedback.db to
    change the admin password" advice — see SETUP_GUIDE.md.
    """
    user = get_user(username)
    if user is None:
        return False, f"No account named '{username}' exists."
    if len(new_password or "") < 8:
        return False, "The new password must be at least 8 characters long."
    try:
        update_password(user["username"], new_password)
        return True, f"The password for '{user['username']}' has been changed."
    except Exception:
        return False, "The password could not be changed. No changes were saved."


def filter_by_username(df: "pd.DataFrame", username: str) -> "pd.DataFrame":
    """Case-insensitively selects one student's rows from a feedback DataFrame.

    Every other user lookup in this module matches with LOWER(username), so
    pages must not compare `df["username"] == username` exactly — that is the
    inconsistency that let half the app disagree with the other half.
    """
    if df is None or df.empty or "username" not in df.columns:
        return df.iloc[0:0] if df is not None else pd.DataFrame()
    target = str(username or "").strip().lower()
    mask = df["username"].astype("string").str.strip().str.lower() == target
    return df[mask]


# ══════════════════════════════════════════════════════════════
#  PASSWORD RESET (OTP)
# ══════════════════════════════════════════════════════════════

def create_password_reset(username: str) -> str:
    """Generates a fresh 6-digit OTP, stores its hash, returns the plain OTP."""
    conn = get_db()
    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO password_resets (username, otp_hash, expires_at, attempts, used, created_at)
           VALUES (?,?,?,0,0,?)""",
        ((username or "").strip(), hash_password(otp), expires_at, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    return otp


def verify_password_reset(username: str, otp: str) -> tuple[bool, str]:
    """Returns (ok, message). On success, marks the OTP used."""
    conn = get_db()
    u_clean = (username or "").strip()
    row = conn.execute(
        """SELECT id, otp_hash, expires_at, attempts, used FROM password_resets
           WHERE LOWER(username) = LOWER(?) ORDER BY id DESC LIMIT 1""",
        (u_clean,),
    ).fetchone()
    if row is None:
        return False, "No reset request found. Please request a new code."
    reset_id, otp_hash, expires_at, attempts, used = row
    if used:
        return False, "This code has already been used. Please request a new one."
    if datetime.now() > datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S"):
        return False, "This code has expired. Please request a new one."
    if attempts >= 5:
        return False, "Too many incorrect attempts. Please request a new code."
    if not verify_password(otp, otp_hash):
        conn.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?", (reset_id,))
        conn.commit()
        return False, "Incorrect verification code. Please check your email and try again."
    conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (reset_id,))
    conn.commit()
    return True, "Code verified."


def create_password_reset_for_email(email: str) -> tuple[str | None, str]:
    """Generates an OTP for the account owning `email`.

    Email-only recovery: callers hand over an email address because a user
    who has forgotten their username can still remember the address they
    registered with. Returns the canonical username plus the plain OTP, or
    ``(None, reason)`` when no account holds that address.
    """
    user = get_user_by_email(email)
    if user is None:
        return None, "no_account"
    return user["username"], create_password_reset(user["username"])


def get_pending_resets_by_email(email: str) -> list[dict]:
    """Returns pending password-reset rows for the account owning `email`.

    Used by the verify step so recovery can be completed from an email
    address alone — the OTP row is keyed by username, but the user was never
    asked to supply one.
    """
    user = get_user_by_email(email)
    if user is None:
        return []
    conn = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """SELECT id, username, otp_hash, expires_at, attempts, used
           FROM password_resets
           WHERE LOWER(username) = LOWER(?) AND used = 0 AND expires_at > ?
           ORDER BY id DESC""",
        ((user["username"] or "").strip(), now_str),
    ).fetchall()
    return [
        {
            "id": r[0],
            "username": r[1],
            "otp_hash": r[2],
            "expires_at": r[3],
            "attempts": r[4],
            "used": r[5],
        }
        for r in rows
    ]


def verify_password_reset_by_email(email: str, otp: str) -> tuple[bool, str, str]:
    """Verifies an OTP against every pending reset for `email`.

    Returns ``(ok, message, canonical_username)``. On success the matching
    reset row is marked used and the canonical username is returned so the
    caller can update the password without ever having asked for a username.
    """
    pending = get_pending_resets_by_email(email)
    if not pending:
        return False, "No reset request found for this email address. Please request a new code.", ""

    # Try each pending row — normally there is exactly one, but a user who
    # requested a code twice in a row may have two unexpired rows.
    for row in pending:
        if row["used"] or datetime.now() > datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S"):
            continue
        if row["attempts"] >= 5:
            continue
        if not verify_password(otp, row["otp_hash"]):
            conn = get_db()
            conn.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
            conn.commit()
            continue
        conn = get_db()
        conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        return True, "Code verified.", row["username"]

    return False, "Incorrect or expired verification code. Please check your email and try again.", ""


def purge_expired_password_resets() -> int:
    """Removes expired or used password reset records."""
    conn = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("DELETE FROM password_resets WHERE used = 1 OR expires_at < ?", (now_str,))
    deleted = cur.rowcount
    conn.commit()
    return deleted


# ══════════════════════════════════════════════════════════════
#  USER MANAGEMENT & GUARDED DELETION ENGINE (F-01..F-08)
# ══════════════════════════════════════════════════════════════

def count_admins() -> int:
    """Returns the total number of administrator accounts."""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()
    return row[0] if row else 0


def list_users(search: str = "", role: str = "all", sort: str = "created_desc") -> pd.DataFrame:
    """Returns account directory with aggregated feedback counts and submission metrics."""
    conn = get_db()
    query = """
        SELECT 
            u.id,
            u.username,
            u.full_name,
            u.email,
            u.role,
            u.level,
            u.created_at,
            COUNT(f.id) AS feedback_count,
            COUNT(DISTINCT f.session) AS sessions_touched,
            MAX(f.timestamp) AS last_submission,
            SUM(CASE WHEN f.admin_corrected_sentiment IS NOT NULL THEN 1 ELSE 0 END) AS admin_corrections
        FROM users u
        LEFT JOIN feedback f ON LOWER(f.username) = LOWER(u.username)
    """
    conditions = []
    params = []

    if role in ("student", "admin"):
        conditions.append("u.role = ?")
        params.append(role)

    if search and search.strip():
        s = f"%{search.strip().lower()}%"
        conditions.append("(LOWER(u.username) LIKE ? OR LOWER(u.full_name) LIKE ? OR LOWER(u.email) LIKE ?)")
        params.extend([s, s, s])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # Every selected non-aggregate column is named explicitly.
    #
    # `GROUP BY u.id` alone is accepted by SQLite, which infers the rest from the
    # primary key. PostgreSQL has no such inference and raises
    # `column "u.username" must appear in the GROUP BY clause`, which took out
    # User Management entirely. Listing the columns is valid on both engines, so
    # the query no longer depends on which one is underneath.
    query += (" GROUP BY u.id, u.username, u.full_name, u.email, "
              "u.role, u.level, u.created_at ")

    # Every text sort folds case, because every username comparison in this
    # app is case-insensitive — a directory that ordered `DeAnalyst` before
    # `admin001` would not match how the rest of the system looks a user up.
    # The `u.id` tiebreaker keeps rows with equal keys in a stable order
    # instead of letting SQLite return them in whatever order the query
    # planner happens to produce, which reshuffles the table on reload.
    sort_map = {
        "created_desc": "u.id DESC",
        "created_asc": "u.id ASC",
        "name_asc": "LOWER(u.full_name) ASC, LOWER(u.username) ASC, u.id ASC",
        "username_asc": "LOWER(u.username) ASC, u.id ASC",
        "feedback_desc": "feedback_count DESC, u.id ASC",
    }
    query += " ORDER BY " + sort_map.get(sort, "u.id DESC")

    df = pd.read_sql_query(query, conn, params=tuple(params) if params else None)
    df["admin_corrections"] = df["admin_corrections"].fillna(0).astype(int)
    df["feedback_count"] = df["feedback_count"].fillna(0).astype(int)
    df["sessions_touched"] = df["sessions_touched"].fillna(0).astype(int)
    return df


def get_user_deletion_preview(username: str, acting_user: str = "") -> dict | None:
    """Read-only preview of everything owned by a user before deletion.

    `acting_user` is the signed-in administrator; it only affects the
    `is_self` flag, which the confirmation UI uses to explain the refusal.
    This function never mutates anything.
    """
    conn = get_db()
    u_clean = (username or "").strip()
    u_row = conn.execute(
        "SELECT id, username, email, full_name, role, level, created_at FROM users WHERE LOWER(username) = LOWER(?)",
        (u_clean,),
    ).fetchone()
    if not u_row:
        return None

    canonical_username = u_row[1]

    # Feedback breakdown
    fb_rows = conn.execute(
        """SELECT category, session, rating, timestamp, admin_corrected_sentiment
           FROM feedback WHERE LOWER(username) = LOWER(?) ORDER BY id ASC""",
        (canonical_username,),
    ).fetchall()

    categories = {}
    sessions = set()
    admin_corrections = 0
    first_sub = None
    last_sub = None

    if fb_rows:
        first_sub = fb_rows[0][3]
        last_sub = fb_rows[-1][3]
        for cat, sess, rating, ts, corrected in fb_rows:
            categories[cat] = categories.get(cat, 0) + 1
            if sess:
                sessions.add(sess)
            if corrected:
                admin_corrections += 1

    # Pending reset tokens
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resets_row = conn.execute(
        "SELECT COUNT(*) FROM password_resets WHERE LOWER(username) = LOWER(?) AND used = 0 AND expires_at > ?",
        (canonical_username, now_str),
    ).fetchone()
    pending_resets = resets_row[0] if resets_row else 0

    seeded_usernames = [a["username"].lower() for a in ADMIN_SEED_ACCOUNTS]
    is_seeded_admin = canonical_username.lower() in seeded_usernames
    is_last_admin = (u_row[4] == "admin" and count_admins() <= 1)

    return {
        "id": u_row[0],
        "username": canonical_username,
        "email": u_row[2],
        "full_name": u_row[3],
        "role": u_row[4],
        "level": u_row[5],
        "created_at": u_row[6],
        "feedback_count": len(fb_rows),
        "sessions": sorted(list(sessions)),
        "categories": categories,
        "first_submission": first_sub,
        "last_submission": last_sub,
        "admin_corrections": admin_corrections,
        "pending_resets": pending_resets,
        "is_last_admin": is_last_admin,
        "is_seeded_admin": is_seeded_admin,
        "is_self": bool(acting_user) and canonical_username.lower() == acting_user.strip().lower(),
    }


def delete_user_account(username: str, deleted_by: str, reason: str = "") -> tuple[bool, str, dict]:
    """Permanently deletes a user account and explicitly cascades to all child records, saving snapshot."""
    conn = get_db()
    u_clean = (username or "").strip()
    operator = (deleted_by or "").strip()

    # 1. Resolve canonical user
    u_row = conn.execute(
        "SELECT id, username, email, full_name, role, level, created_at, password_hash FROM users WHERE LOWER(username) = LOWER(?)",
        (u_clean,),
    ).fetchone()
    if not u_row:
        return False, f"User account '{username}' was not found.", {}

    canonical_u = u_row[1]
    role = u_row[4]

    # 2. Guard: Cannot delete self
    if canonical_u.lower() == operator.lower():
        return False, "Security restriction: You cannot delete the administrator account you are currently logged in with.", {}

    # 3. Guard: Cannot delete admin accounts at all
    if role == "admin":
        return False, "Administrator accounts cannot be deleted. The admin password is hardcoded in config.py — edit it directly to change administrator access.", {}

    try:
        # 4. Create snapshot for audit log
        user_snapshot = {
            "id": u_row[0], "username": u_row[1], "email": u_row[2],
            "full_name": u_row[3], "role": u_row[4], "level": u_row[5],
            "created_at": u_row[6], "password_hash": u_row[7],
        }

        # Feedback snapshot
        fb_cursor = conn.execute(
            "SELECT * FROM feedback WHERE LOWER(username) = LOWER(?)", (canonical_u,)
        )
        fb_cols = [c[0] for c in fb_cursor.description]
        fb_snapshot = [dict(zip(fb_cols, row)) for row in fb_cursor.fetchall()]

        # Resets snapshot
        res_cursor = conn.execute(
            "SELECT * FROM password_resets WHERE LOWER(username) = LOWER(?)", (canonical_u,)
        )
        res_cols = [c[0] for c in res_cursor.description]
        res_snapshot = [dict(zip(res_cols, row)) for row in res_cursor.fetchall()]

        snapshot_blob = json.dumps({
            "user": user_snapshot,
            "feedback": fb_snapshot,
            "password_resets": res_snapshot,
        })

        admin_corrections_count = sum(1 for fb in fb_snapshot if fb.get("admin_corrected_sentiment"))

        # 5. Delete child password_resets
        del_res = conn.execute("DELETE FROM password_resets WHERE LOWER(username) = LOWER(?)", (canonical_u,)).rowcount

        # 6. Delete child feedback (CASCADE)
        del_fb = conn.execute("DELETE FROM feedback WHERE LOWER(username) = LOWER(?)", (canonical_u,)).rowcount

        # 7. Delete parent user
        del_u = conn.execute("DELETE FROM users WHERE id = ?", (u_row[0],)).rowcount

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 8. Record audit log entry
        conn.execute(
            """INSERT INTO admin_audit_log (
                action, target_username, target_full_name, target_email,
                target_role, target_level, performed_by, performed_at,
                feedback_rows_deleted, reset_rows_deleted, admin_corrections_deleted,
                reason, snapshot
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "DELETE_USER", canonical_u, u_row[3], u_row[2],
                role, u_row[5], operator, now_str,
                del_fb, del_res, admin_corrections_count,
                reason.strip(), snapshot_blob,
            ),
        )
        conn.commit()

        # Stop `seed_admins` recreating this account on the next start. Written
        # AFTER the commit and outside the try, because it is a separate table
        # with its own lifetime — if it failed it must not roll back a deletion
        # that has already succeeded.
        _set_deletion_tombstone(canonical_u, present=True)

        stats = {
            "users_deleted": del_u,
            "feedback_deleted": del_fb,
            "resets_deleted": del_res,
            "corrections_removed": admin_corrections_count,
        }
        return True, f"Account '{canonical_u}' and all {del_fb} associated feedback records have been permanently removed.", stats

    except Exception:
        conn.rollback()
        return False, "Deletion failed and was rolled back — nothing was removed from the database.", {}


# ══════════════════════════════════════════════════════════════
#  5-DAY RETENTION — THE TRAIL IS A 5-DAY WINDOW, NOT AN ARCHIVE (F-08)
# ══════════════════════════════════════════════════════════════
#
# A deletion writes a full JSON snapshot — the account, its password hash, and
# every feedback row it owned — into `admin_audit_log.snapshot`. That snapshot
# is what makes Restore possible, and it is also the largest concentration of
# personal data this system holds: a comment is a student's own words, and the
# password hash is a credential.
#
# So the whole entry is a 5-DAY window. Once the window closes the row is
# DELETED — not blanked, deleted — so the trail stays short and the page has
# room for what an administrator is actually doing now. An audit trail that
# grows without bound stops being a record of current accountability and
# becomes an archive nobody reads.
#
# The trade this makes, stated plainly so it is not a surprise later: after 5
# days there is no record that a given account was ever removed, and no way to
# restore it. If that provenance matters to you, copy the page or the database
# before the window closes — this app is not the archive of record.
#
# Both actions expire, not just deletions: a RESTORE_USER row is just as much
# a stale artefact once it is weeks old, and leaving it behind while deleting
# its counterpart would be arbitrary.
#
# The one thing that does NOT expire is the tombstone in
# `admin_deletion_tombstones`, which is what stops `seed_admins` from
# recreating a deliberately deleted account. That has its own table precisely
# so that purging audit rows cannot resurrect a deleted admin — see
# `_admin_deletion_tombstones()`.

AUDIT_RETENTION_DAYS = 5

# Retained for anything that imported the old name. The concept is unchanged —
# 5 days — only the scope widened from "the snapshot" to "the entry".
AUDIT_SNAPSHOT_RETENTION_DAYS = AUDIT_RETENTION_DAYS


def _purge_expired_audit_rows(conn, retention_days: int = AUDIT_RETENTION_DAYS) -> int:
    """Deletes audit rows older than the retention window, on an existing connection.

    Takes the connection rather than calling get_db(), so get_db() can call
    this on the connection it is still building. Returns the rows removed.
    """
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("DELETE FROM admin_audit_log WHERE performed_at < ?", (cutoff,))
    return cur.rowcount


def purge_expired_audit_rows(retention_days: int = AUDIT_RETENTION_DAYS) -> int:
    """Removes audit entries past the retention window. Returns how many went.

    Safe to call at any time, and idempotent.
    """
    conn = get_db()
    try:
        removed = _purge_expired_audit_rows(conn, retention_days)
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        return 0


def list_audit_log(limit: int = 50) -> pd.DataFrame:
    """Returns recent administrative audit trail entries, newest first.

    Only entries inside the retention window exist, so anything older than
    `AUDIT_RETENTION_DAYS` has already been removed.
    """
    conn = get_db()
    query = """
        SELECT id, action, target_username, target_full_name, target_role,
               performed_by, performed_at, feedback_rows_deleted, reason, snapshot
        FROM admin_audit_log
        ORDER BY id DESC LIMIT ?
    """
    return pd.read_sql_query(query, conn, params=(limit,))


def restore_user(audit_id: int, restored_by: str = "admin") -> tuple[bool, str]:
    """Restores a deleted user, their feedback, and their reset tokens from an
    audit-log snapshot.

    Rows whose unique key has since been re-taken by someone else are skipped
    rather than aborting the whole restore, and the returned message states
    exactly how many rows were restored and how many were skipped.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id, action, target_username, snapshot, performed_at FROM admin_audit_log WHERE id = ?",
        (audit_id,),
    ).fetchone()
    if not row:
        # F-08: rows are REMOVED once the retention window closes, so a missing
        # row now means exactly one thing — this deletion has aged out and can
        # no longer be undone. Naming the window is more use to an administrator
        # than a bare "not found", which reads like a broken button.
        return False, (
            f"This deletion is no longer in the audit trail. Entries are kept for "
            f"{AUDIT_RETENTION_DAYS} days, after which they are permanently "
            "removed along with their restore data, so this account can no "
            "longer be restored."
        )

    # Action FIRST. A RESTORE_USER row carries snapshot = NULL by design, so
    # testing the snapshot first reported "snapshot not found" for a row that
    # was never a deletion to begin with — the wrong explanation, and it hid
    # the real question ("why is there nothing to restore here?") behind a
    # message about a missing payload.
    if row[1] != "DELETE_USER":
        return False, "This audit entry is not a deletion, so there is nothing to restore."

    if not row[3]:
        # Only reachable for rows written by an EARLIER build, which blanked
        # the snapshot instead of removing the row. Current builds delete the
        # row outright, so a snapshot-less deletion is legacy data rather than
        # a normal outcome — hence a message about a cleared payload and not
        # the retention-window one above.
        return False, (
            f"The restore data for this deletion (on {row[4] or 'an earlier date'}) "
            "has been cleared, so this account can no longer be restored."
        )

    try:
        data = json.loads(row[3])
        u_data = data.get("user", {})
        fb_list = data.get("feedback", [])

        if not u_data or not u_data.get("username"):
            return False, "Invalid snapshot payload: user data is missing."

        u_name = u_data["username"]

        if username_exists(u_name):
            return False, f"Cannot restore: the username '{u_name}' is currently in use."
        if u_data.get("email") and email_exists(u_data["email"]):
            return False, f"Cannot restore: the email address '{u_data['email']}' is currently in use."

        # Password-reset tokens are deliberately NOT restored: they were
        # either consumed or expired at deletion time, and re-arming a
        # one-time code is a security hazard with no upside.

        conn.execute(
            """INSERT INTO users (username, email, full_name, password_hash, role, level, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                u_name, u_data["email"], u_data["full_name"],
                u_data["password_hash"], u_data["role"], u_data.get("level"),
                u_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        fb_restored = 0
        fb_skipped = 0
        for fb in fb_list:
            try:
                if active_backend() == "postgresql":
                    # `INSERT OR IGNORE` becomes `ON CONFLICT DO NOTHING`. The
                    # conflict target is left off deliberately, mirroring SQLite's
                    # behaviour of ignoring a violation of ANY unique constraint
                    # rather than only one named index.
                    sql = """INSERT INTO feedback (
                        username, category, student_level, rating, comment, timestamp,
                        additional_info, sentiment, sentiment_score, sentiment_engine,
                        sentiment_confidence, sentiment_cues, admin_corrected_sentiment,
                        corrected_by, corrected_at, context_data, session
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT DO NOTHING"""
                else:
                    sql = """INSERT OR IGNORE INTO feedback (
                        username, category, student_level, rating, comment, timestamp,
                        additional_info, sentiment, sentiment_score, sentiment_engine,
                        sentiment_confidence, sentiment_cues, admin_corrected_sentiment,
                        corrected_by, corrected_at, context_data, session
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
                cur = conn.execute(
                    sql,
                    (
                        u_name, fb.get("category"), fb.get("student_level"), fb.get("rating"),
                        fb.get("comment"), fb.get("timestamp"), fb.get("additional_info", ""),
                        fb.get("sentiment") or "Neutral", fb.get("sentiment_score", 0.0),
                        fb.get("sentiment_engine") or "vader_academic_pro",
                        fb.get("sentiment_confidence", 0.85),
                        fb.get("sentiment_cues", "{}"), fb.get("admin_corrected_sentiment"),
                        fb.get("corrected_by"), fb.get("corrected_at"),
                        fb.get("context_data", "{}"), fb.get("session") or CURRENT_SESSION,
                    ),
                )
                if cur.rowcount:
                    fb_restored += 1
                else:
                    fb_skipped += 1
            except Exception:
                fb_skipped += 1

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT INTO admin_audit_log (
                action, target_username, target_full_name, target_email,
                target_role, target_level, performed_by, performed_at,
                feedback_rows_deleted, reset_rows_deleted, admin_corrections_deleted,
                reason, snapshot
            ) VALUES (?,?,?,?,?,?,?,?,0,0,0,?,NULL)""",
            (
                "RESTORE_USER", u_name, u_data.get("full_name"), u_data.get("email"),
                u_data.get("role"), u_data.get("level"), restored_by, now_str,
                f"Restored from deletion audit entry #{audit_id}",
            ),
        )
        conn.commit()

        # The account is back, so the "do not recreate this" tombstone must go
        # too — otherwise seed_admins would skip an account that now exists and
        # is perfectly healthy.
        _set_deletion_tombstone(u_name, present=False)

        msg = f"The account '{u_name}' and {fb_restored} feedback record(s) were restored."
        if fb_skipped:
            msg += (
                f" {fb_skipped} record(s) were skipped because a matching "
                "(category, session) submission already exists."
            )
        msg += " Any password-reset codes issued to this account were not restored — the user must request a new one."
        return True, msg

    except Exception:
        conn.rollback()
        return False, "Restore failed and was rolled back — no records were re-inserted."


def reconcile_orphaned_feedback() -> list[str]:
    """Returns list of usernames in feedback table that do not exist in the users table."""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT username FROM feedback WHERE LOWER(username) NOT IN (SELECT LOWER(username) FROM users)"
    ).fetchall()
    return [r[0] for r in rows if r[0]]


def cleanup_orphaned_feedback() -> int:
    """Removes all orphaned feedback rows whose author account no longer exists."""
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM feedback WHERE LOWER(username) NOT IN (SELECT LOWER(username) FROM users)"
    )
    deleted = cur.rowcount
    conn.commit()
    return deleted


# ══════════════════════════════════════════════════════════════
#  FEEDBACK & SENTIMENT DATA
# ══════════════════════════════════════════════════════════════

def save_data(category: str, d: dict) -> tuple[bool, str]:
    """Insert one feedback row. Returns (ok: bool, message: str)."""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO feedback
               (username, category, student_level, rating, comment, timestamp,
                additional_info, sentiment, sentiment_score, sentiment_engine,
                sentiment_confidence, sentiment_cues, context_data, session)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d["username"], category, d["student_level"], d["rating"],
                d["comment"], d["timestamp"], d.get("additional_info", ""),
                d.get("sentiment", "Neutral"), d.get("sentiment_score", 0.0),
                d.get("sentiment_engine", "vader"),
                d.get("sentiment_confidence", 0.85),
                json.dumps(d.get("sentiment_cues", {})) if isinstance(d.get("sentiment_cues"), (dict, list)) else str(d.get("sentiment_cues", "{}")),
                json.dumps(d.get("context_data", {})),
                d.get("session", CURRENT_SESSION),
            ),
        )
        conn.commit()
        return True, "Feedback submitted successfully!"
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "You have already submitted feedback for this category and academic session."
    except Exception as e:
        conn.rollback()
        return False, f"Error saving feedback: {e}"


def correct_sentiment(row_id: int, corrected_label: str, corrected_by: str):
    conn = get_db()
    conn.execute(
        """UPDATE feedback SET admin_corrected_sentiment = ?, corrected_by = ?, corrected_at = ?
           WHERE id = ?""",
        (corrected_label, corrected_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row_id),
    )
    conn.commit()


def save_admin_note(category: str, note: str, updated_by: str, updated_at: str):
    conn = get_db()
    conn.execute(
        """INSERT INTO admin_notes (category, note, updated_by, updated_at)
           VALUES (?,?,?,?)
           ON CONFLICT(category) DO UPDATE SET
             note=excluded.note, updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
        (category, note, updated_by, updated_at),
    )
    conn.commit()


def load_admin_notes() -> dict:
    """Returns {category: {'note':..., 'updated_by':..., 'updated_at':...}}."""
    conn = get_db()
    rows = conn.execute("SELECT category, note, updated_by, updated_at FROM admin_notes").fetchall()
    return {r[0]: {"note": r[1], "updated_by": r[2], "updated_at": r[3]} for r in rows}


# ══════════════════════════════════════════════════════════════
#  ACADEMIC SESSIONS MANAGEMENT
# ══════════════════════════════════════════════════════════════

def get_academic_sessions() -> list[str]:
    """Returns list of active academic session names, default/current session first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT session_name FROM academic_sessions WHERE is_active = 1 ORDER BY is_default DESC, id DESC"
    ).fetchall()
    if not rows:
        return [CURRENT_SESSION]
    return [r[0] for r in rows]


def get_active_session() -> str:
    """Returns the current default academic session name."""
    conn = get_db()
    row = conn.execute(
        "SELECT session_name FROM academic_sessions WHERE is_default = 1 AND is_active = 1 LIMIT 1"
    ).fetchone()
    if row:
        return row[0]
    sessions = get_academic_sessions()
    return sessions[0] if sessions else CURRENT_SESSION


def create_academic_session(session_name: str, created_by: str, set_default: bool = False) -> tuple[bool, str]:
    """Registers a new academic session (e.g. '2026/2027')."""
    name = (session_name or "").strip()
    if not name:
        return False, "Session name cannot be empty."
    if len(name) < 4 or len(name) > 20:
        return False, "Session name must be between 4 and 20 characters (e.g. '2026/2027')."

    conn = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if set_default:
            conn.execute("UPDATE academic_sessions SET is_default = 0")
        conn.execute(
            """INSERT INTO academic_sessions (session_name, is_active, is_default, created_at, created_by)
               VALUES (?, 1, ?, ?, ?)""",
            (name, 1 if set_default else 0, now_str, created_by),
        )
        conn.commit()
        return True, f"Academic session '{name}' created successfully!"
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, f"Session '{name}' already exists."
    except Exception as e:
        conn.rollback()
        return False, f"Error creating session: {e}"


def set_default_session(session_name: str) -> bool:
    """Designates an existing session as the active default session (B-30)."""
    conn = get_db()
    try:
        conn.execute("UPDATE academic_sessions SET is_default = 0")
        conn.execute("UPDATE academic_sessions SET is_default = 1 WHERE session_name = ?", (session_name.strip(),))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def get_session_stats() -> dict[str, dict]:
    """Returns aggregated response count, average rating, and student count per session.

    Rows with a NULL/blank session are grouped under the current default
    session rather than dropped, so the totals always add back up to the
    number of rows in the table.
    """
    conn = get_db()
    # The grouping key is computed in a subquery and then grouped by its alias.
    #
    # The obvious spelling — repeating the whole COALESCE(...) in both the SELECT
    # and the GROUP BY — is accepted by SQLite and rejected by PostgreSQL. The two
    # `?` placeholders become two *different* parameters ($1 and $2), so
    # PostgreSQL sees two different expressions, concludes that the bare `session`
    # column inside is neither grouped nor aggregated, and raises
    # `column "session" must appear in the GROUP BY clause`. Grouping by an alias
    # over a subquery is spelled the same way on both engines and uses one
    # parameter, so there is nothing left to disagree about.
    rows = conn.execute(
        """SELECT session_key, COUNT(*), AVG(rating),
                  COUNT(DISTINCT LOWER(username))
           FROM (
               SELECT COALESCE(NULLIF(TRIM(session), ''), ?) AS session_key,
                      rating, username
               FROM feedback
           ) AS grouped
           GROUP BY session_key""",
        (CURRENT_SESSION,),
    ).fetchall()
    stats = {}
    for r in rows:
        sess = r[0] or "Unknown"
        stats[sess] = {
            "total_feedback": r[1],
            "avg_rating": round(r[2], 1) if r[2] is not None else 0.0,
            "unique_students": r[3],
        }
    return stats


def load_data(category: str | None = None, session: str | None = None) -> pd.DataFrame:
    """Loads feedback DataFrame, optionally filtered by category and/or academic session."""
    conn = get_db()
    query = "SELECT * FROM feedback"
    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if session and session not in _AGGREGATE_ALIASES:
        conditions.append("session = ?")
        params.append(session)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    df = pd.read_sql_query(query, conn, params=tuple(params) if params else None)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if not df.empty and "admin_corrected_sentiment" in df.columns:
        df["effective_sentiment"] = df["admin_corrected_sentiment"].fillna(df["sentiment"])
    return df


def load_labeled_training_data(session: str | None = None, readonly: bool = False) -> pd.DataFrame:
    """Comments with an admin-corrected label — the ground-truth training set for
    train_model.py.

    `session=None` means "every session" (which is what the trainer uses, so it
    learns from all accumulated corrections). Passing a session name narrows it
    to that one session, which is what the admin's "N corrected so far" counter
    can use when a session filter is active in the sidebar — keeping the number
    on screen and the number the trainer sees in agreement.

    `readonly=True` opens the database with SQLite's read-only URI flag and
    skips `get_db()`, so an offline training run cannot switch the live file to
    WAL, add missing tables/columns, or delete expired password-reset rows as a
    side effect of "just reading" the labels.
    """
    query = """SELECT comment, admin_corrected_sentiment AS label FROM feedback
               WHERE admin_corrected_sentiment IS NOT NULL AND TRIM(comment) != ''"""
    params: tuple = ()
    if session and session not in _AGGREGATE_ALIASES:
        query += " AND session = ?"
        params = (session,)

    if readonly:
        if not Path(DB_PATH).exists():
            return pd.DataFrame(columns=["comment", "label"])
        uri = f"file:{Path(DB_PATH).as_posix()}?mode=ro"
        ro = sqlite3.connect(uri, uri=True, timeout=30.0)
        try:
            return pd.read_sql_query(query, ro, params=params)
        finally:
            ro.close()

    return pd.read_sql_query(query, get_db(), params=params)


def parse_context(raw) -> dict:
    """Safely parse the JSON context_data blob stored per submission."""
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}


def context_text_list(value, limit: int | None = None) -> list[str]:
    """Coerce one `context_data` field into a clean list of display strings.

    `context_data` is a free-form JSON blob. The forms only ever write a list
    of strings picked from the option lists in `config.py`, but the column is
    not constrained — a row inserted by hand, by an older build, or by a
    crafted POST can hold anything JSON can express, including
    `{"emphasis_areas": [["nested"]]}`.

    Both admin pages that summarise these fields pass the result straight to
    `Counter(...).most_common()`, and a `list` or `dict` element is
    *unhashable*: `Counter` raises `TypeError` and the entire page dies with a
    stack trace instead of rendering. `str()`-ing a nested list would "fix"
    that but print `[['nested']]` at an admin, which is worse than omitting it.

    So: keep only scalars, stringify those, drop blanks, and cap the length so
    one pathological row cannot dominate a frequency chart. Rendering
    responsibility (escaping) stays with the caller.
    """
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        # A bare string where a list was expected: one item, not N characters.
        items = [value]
    elif isinstance(value, dict):
        items = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    elif isinstance(value, (int, float, bool)):
        items = [value]
    else:
        return []

    out: list[str] = []
    for it in items:
        if isinstance(it, (list, dict, tuple, set, bytes)):
            continue  # unhashable, or structured — not a display string
        s = str(it).strip()
        if s:
            out.append(s[:200])
        if limit and len(out) >= limit:
            break
    return out
