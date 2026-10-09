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

from collections import Counter
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

import sentiment

from config import (
    CURRENT_SESSION,
    ALL_SESSIONS_LABEL,
    ADMIN_SEED_ACCOUNTS,
    SEED_ADMINS_ON_STARTUP,
    # Per-lecturer rollups group on these, and one handbook surname is held by
    # two members of staff — see `lecturer_group_key`.
    lecturer_group_key,
    lecturer_display_for,
    is_known_lecturer,
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
        # information_schema is a system view; parameterised queries against it
        # can fail with OperationalError on some Postgres configurations. Use a
        # literal table name instead.
        existing_cols = {row[0] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'feedback'"
        ).fetchall()}
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
            snapshot TEXT,
            restored_at TEXT
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON admin_audit_log(target_username)")

    # `restored_at` marks a DELETE_USER entry that has already been restored, so
    # the audit trail stops offering to restore the same deletion twice. Without
    # it the only available signal was "is this username in the users table",
    # which cannot tell a restored account apart from one somebody re-registered
    # — so it showed a successful restore as "Cannot restore: registered again",
    # which reads exactly like a restore that failed.
    #
    # Added defensively for databases created before this column existed. The
    # probe reads `information_schema` on PostgreSQL and `PRAGMA table_info` on
    # SQLite, for the same reason the `feedback` probe below does.
    if active_backend() == "postgresql":
        audit_cols = {r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'admin_audit_log'"
        ).fetchall()}
    else:
        audit_cols = {r[1] for r in
                      conn.execute("PRAGMA table_info(admin_audit_log)").fetchall()}
    if "restored_at" not in audit_cols:
        conn.execute("ALTER TABLE admin_audit_log ADD COLUMN restored_at TEXT")

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
    #
    # Best-effort, and the rollback is isolated in its own try/except. This runs
    # while the schema is still being built, so an exception here propagates out
    # of `_connect()` and takes down every page of the app — housekeeping
    # deleting an old audit row is not worth that. It also had no commit: on
    # PostgreSQL that left the DELETE sitting in an open transaction forever
    # ("idle in transaction"), which free-tier hosts routinely kill, and which
    # meant the sweep's deletions were never actually persisted.
    try:
        _purge_expired_audit_rows(conn)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    return conn


# How often the retention sweep is allowed to run. Hourly is far more often
# than the 5-day window needs and cheap enough to be invisible (one indexed
# DELETE that usually matches zero rows).
_SWEEP_INTERVAL_SECONDS = 3600
_last_sweep_at = 0.0

# How often the connection is checked for being alive. See `_connection_is_alive`
# for why a cached connection needs checking at all.
_PING_INTERVAL_SECONDS = 60
_last_ping_at = 0.0


def _connection_is_alive(conn) -> bool:
    """True when `conn` can still run a statement.

    A connection object outliving its socket is the failure mode this exists to
    catch. Streamlit containers sleep, and free-tier Postgres suspends the
    compute or drops idle sessions after a few quiet minutes — but
    `@st.cache_resource` keeps handing the *same* dead object back for the life
    of the process. The result is a database error that never clears itself: the
    app stays broken until somebody redeploys, and the traceback points at
    whichever innocent statement happened to run first (here, the audit
    retention DELETE) rather than at the dropped connection that caused it.

    The free checks come first because they cost nothing and catch the obvious
    cases — psycopg sets `closed` once it knows, and `broken` after an error.
    Neither is sufficient on its own: a socket that died silently is neither,
    which is why a real statement is still sent.
    """
    if getattr(conn, "closed", False) is True:
        return False
    if getattr(conn, "broken", False) is True:
        return False
    try:
        conn.execute("SELECT 1")
    except Exception:
        return False
    try:
        # A read still opens a transaction on PostgreSQL. Leaving one open holds
        # a pooled server connection for the rest of the idle interval, so close
        # it immediately rather than letting the ping leak.
        conn.commit()
    except Exception:
        pass
    return True


def _reconnect(conn):
    """Discard a dead cached connection and open a fresh one.

    `_connect()` is cached, so a new object is only ever produced by clearing
    the cache first. The old connection is closed beforehand: leaving a socket
    open against a suspended server is how a process ends up holding connections
    the host has already given away.
    """
    try:
        conn.close()
    except Exception:
        pass
    try:
        _connect.clear()
    except Exception:
        pass
    return _connect()


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

    It also owns the connection's health, for the same reason: checking liveness
    inside the cached function could never work, because a cached function does
    not run again.
    """
    global _last_sweep_at, _last_ping_at
    conn = _connect()

    # Liveness first, before anything is sent over it. Recovering here means the
    # dead connection is replaced quietly on the next page load instead of
    # throwing, which is the difference between a blip and a dead app.
    now = time.time()
    if now - _last_ping_at >= _PING_INTERVAL_SECONDS:
        _last_ping_at = now
        if not _connection_is_alive(conn):
            conn = _reconnect(conn)

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
            # Commit it. Uncommitted, the DELETE stayed open as an idle
            # transaction that some hosts terminate — taking the connection with
            # them, and the sweep's own work with it.
            conn.commit()
        except Exception:
            # Housekeeping must never take the app down with it. A failed sweep
            # means an expired entry lingers until the next one succeeds.
            #
            # The rollback is wrapped in its own try because a failed purge can
            # leave the connection in a state where rollback itself raises —
            # which would mask the original error and make the app unbootable.
            try:
                conn.rollback()
            except Exception:
                pass
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
            # The timestamp is computed in Python and bound, not asked for with
            # `datetime('now')`. That function is SQLite-only — PostgreSQL has
            # no `datetime()` at all — so the statement failed there, the
            # failure was swallowed by the except below, and the tombstone was
            # silently never written, which is precisely the case it exists to
            # cover: it is what stops `seed_admins` resurrecting a deleted
            # account on the next page load.
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # SQLite spells this `INSERT OR REPLACE`; PostgreSQL spells it as an
            # explicit conflict clause. Written out rather than rewritten by
            # pattern because the two conflict actions are genuinely different
            # operations, and `OR REPLACE` also silently resets columns that
            # `DO UPDATE` would leave alone.
            if active_backend() == "postgresql":
                conn.execute(
                    "INSERT INTO admin_deletion_tombstones (username, created_at) "
                    "VALUES (?, ?) "
                    "ON CONFLICT (username) DO UPDATE SET created_at = EXCLUDED.created_at",
                    (key, stamp),
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO admin_deletion_tombstones (username, created_at) "
                    "VALUES (?, ?)",
                    (key, stamp),
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
    """Deletes expired audit rows, plus redundant restore rows, on an existing connection.

    Takes the connection rather than calling get_db(), so get_db() can call
    this on the connection it is still building. Returns the rows removed.

    Two different deletions, and the distinction matters:

      * `DELETE_USER` rows age out after the retention window, carrying their
        snapshot with them.
      * `RESTORE_USER` rows are removed IMMEDIATELY, whatever their age.

    The second is new, and it exists because those rows became redundant. A
    restore now marks the deletion it undid via `admin_audit_log.restored_at`,
    which is the durable record. The separate RESTORE_USER row said the same
    thing twice — and because it was appended rather than replacing anything, one
    mistaken restore that could be clicked repeatedly produced a wall of identical
    "Restored X" entries all pointing at the same deletion. Those rows also carry
    snapshot = NULL, so nothing restorable is lost by deleting them.
    """
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("DELETE FROM admin_audit_log WHERE performed_at < ?", (cutoff,))
    removed = cur.rowcount
    try:
        restored = conn.execute(
            "DELETE FROM admin_audit_log WHERE action = 'RESTORE_USER'"
        ).rowcount
        removed += restored or 0
    except Exception:
        # Never let housekeeping of a redundant row stop the real purge above.
        pass
    return removed


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


def list_pending_deletions(limit: int = 50) -> pd.DataFrame:
    """The deletions that can STILL be restored — i.e. the working list.

    Three things are excluded, and each exclusion was a defect when it was shown:

      * `RESTORE_USER` rows. They are redundant now that a restore marks the
        deletion it undid, and they were what turned one mistaken restore into a
        column of identical entries.
      * Deletions already undone (`restored_at` set). Listing them made a
        finished job look outstanding.
      * Rows whose snapshot has gone. There is nothing left to restore from, so
        offering a Restore button would be a lie.

    `list_audit_log` still returns the full history; this is the view the page
    renders. Keeping both means the audit trail remains queryable in full while
    the administrator only ever sees work that is actually outstanding.
    """
    frame = list_audit_log(limit=max(limit * 4, limit + 50))
    if frame.empty:
        return frame
    pending = frame[
        (frame["action"] == "DELETE_USER")
        & (frame["snapshot"].notna())
        & (frame["restored_at"].isna())
    ]
    return pending.head(limit).reset_index(drop=True)


def audit_days_remaining(performed_at: str) -> int:
    """Whole days left before this entry is purged for good. Never negative.

    Counted against `AUDIT_RETENTION_DAYS` from the moment the action happened,
    not from when the page was opened, so two administrators reading the same
    row an hour apart are not told two different numbers.

    Clamped at 0 because an aged-out row is normally already gone by the sweep —
    but "0 days left" is the truthful thing to render in the window between a
    purge failing and the next attempt, where a negative count would read as a
    bug rather than as an expiry.
    """
    try:
        when = datetime.strptime(str(performed_at)[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        # An unparseable stamp is not worth hiding the entry over. Reporting the
        # full window is the optimistic end of the range, which is the safer
        # direction to be wrong in: it cannot talk someone out of restoring while
        # there is still time to do it.
        return AUDIT_RETENTION_DAYS
    elapsed = (datetime.now() - when).total_seconds()
    # The REMAINING time is rounded, not the elapsed time — and that distinction
    # is the whole function, because both obvious alternatives are wrong at one
    # end or the other:
    #
    #   floor(elapsed days): reads "5 days left" for the first full 24 hours, so
    #     an entry with one hour left claimed a whole day remained and the
    #     last-day warning never fired until after expiry.
    #   ceil(elapsed days): a row created two seconds ago immediately reads
    #     "4 days left", having consumed a day it never had.
    #
    # Rounding what is left is correct at both ends: a fresh row shows the full
    # window, an entry 17 hours old shows 4, and one inside its final 24 hours
    # shows 0 — which the UI words as "Last day" rather than as a bare zero.
    # Half-up, via int() rather than round(), which rounds halves to even and
    # would make 4.5 days read 4 on one visit and 5 on the next.
    remaining = AUDIT_RETENTION_DAYS - elapsed / 86400.0
    return max(0, int(remaining + 0.5))


def list_audit_log(limit: int = 50) -> pd.DataFrame:
    """Returns recent administrative audit trail entries, newest first.

    Only entries inside the retention window exist, so anything older than
    `AUDIT_RETENTION_DAYS` has already been removed.

    Two things are added here rather than selected from SQL:

      * `days_remaining` — the countdown before the row is purged permanently.
      * `snapshot` — normalised so that a NULL genuinely reads as absent. Left
        alone, pandas hands a NULL TEXT column back as float NaN, and
        `bool(nan)` is True, so a RESTORE_USER row (written with snapshot = NULL
        by design) looks like it carries restore data. That was harmless only
        because every caller happened to check the action first.
    """
    conn = get_db()
    query = """
        SELECT id, action, target_username, target_full_name, target_role,
               performed_by, performed_at, feedback_rows_deleted, reason, snapshot,
               restored_at
        FROM admin_audit_log
        ORDER BY id DESC LIMIT ?
    """
    frame = pd.read_sql_query(query, conn, params=(limit,))
    if frame.empty:
        return frame
    # Rebuilt as an explicit object-dtype Series rather than with `.where()`.
    # Two things go wrong otherwise, and both were hit in turn: `.where(cond,
    # None)` preserves the column's inferred dtype, and a column of JSON strings
    # mixed with a NULL gets inferred as pandas' `str` dtype — which coerces an
    # assigned `None` straight back to float NaN, the very value this exists to
    # eliminate. `dtype=object` is what makes None stick.
    frame["snapshot"] = pd.Series(
        [None if pd.isna(v) else v for v in frame["snapshot"]],
        index=frame.index, dtype=object,
    )
    frame["restored_at"] = pd.Series(
        [None if pd.isna(v) else v for v in frame["restored_at"]],
        index=frame.index, dtype=object,
    )
    frame["days_remaining"] = [audit_days_remaining(v) for v in frame["performed_at"]]
    return frame


def restore_user(audit_id: int, restored_by: str = "admin") -> tuple[bool, str]:
    """Restores a deleted user, their feedback, and their reset tokens from an
    audit-log snapshot.

    Rows whose unique key has since been re-taken by someone else are skipped
    rather than aborting the whole restore, and the returned message states
    exactly how many rows were restored and how many were skipped.

    The source deletion is marked `restored_at` in the same transaction as the
    restore. That is what lets the audit trail stop offering the same deletion
    again — previously it inferred "already restored" from the username being
    present in the users table, which is also true after an unrelated
    re-registration, so a successful restore was displayed as a refusal.
    """
    # Coerced up front. A numpy integer (straight out of a DataFrame) is not
    # accepted by sqlite3, which binds it as a BLOB; `WHERE id = <blob>` then
    # matches nothing and the function reports that the deletion "is no longer
    # in the audit trail" for a row that is sitting right there. Callers in the
    # UI already wrap the value in int(), so this only ever protects the others.
    try:
        audit_id = int(audit_id)
    except (TypeError, ValueError):
        return False, "That restore request did not identify a valid audit entry."
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
        #
        # ORDER MATTERS, and it is the opposite of what it looks like it should
        # be. The feedback rows go in FIRST and the account LAST.
        #
        # This used to insert the account, then loop over the feedback, and it
        # reported success while creating no account at all. The reason is
        # PostgreSQL: a failed statement aborts the whole transaction, and
        # `db_backend` rolls that transaction back before re-raising so the
        # connection stays usable. So a single bad feedback row — one whose
        # value the column will not accept — silently discarded the
        # uncommitted `users` INSERT along with it. The loop caught the error,
        # counted the row as "skipped", and the function went on to commit the
        # audit entry and report a restore that had not happened. Clicking
        # Restore again just repeated it, which is how one deletion ended up
        # with three identical "Restored" entries and no account.
        #
        # There are no foreign keys in this schema, so nothing requires the user
        # row to exist before its feedback — the order is free to be chosen for
        # safety. The account now goes in after every fallible statement, so
        # nothing that follows can undo it.

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

        # `fb_restored` counted driver-reported rowcounts, which is not the same
        # thing as what is in the table: a rollback triggered by a failed
        # statement can discard rows this loop had already "successfully"
        # inserted, and the tally never noticed. The count is therefore read
        # back from the database, so the number reported to the administrator is
        # the number of rows that actually survived.
        try:
            _now_present = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE LOWER(username) = LOWER(?)",
                (u_name,),
            ).fetchone()[0]
            fb_restored = int(_now_present)
            fb_skipped = max(0, len(fb_list) - fb_restored)
        except Exception:
            # Leave the driver's own tally in place rather than report a number
            # this function cannot stand behind.
            pass

        # The account goes in only now — after every fallible feedback statement
        # (see the note above). Nothing below this point can fail in a way that
        # discards it.
        conn.execute(
            """INSERT INTO users (username, email, full_name, password_hash, role, level, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                u_name, u_data["email"], u_data["full_name"],
                u_data["password_hash"], u_data["role"], u_data.get("level"),
                u_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # The deletion is marked as undone INSTEAD of appending a RESTORE_USER
        # row. Two entries for one event is what produced the pile of identical
        # "Restored X" lines — one per click, all referencing the same deletion —
        # and the mark on the original row is the better record anyway: it keeps
        # the deletion and its reversal together, and it removes the restored
        # account from the list of things awaiting restoration rather than
        # adding to it. The row is retained for the rest of the window so the
        # audit trail still records that the deletion happened and was undone.
        #
        # `reason` is deliberately left alone: it is the operator's stated reason
        # for deleting, and overwriting it with the fact of the restore would
        # destroy the only part of that entry nobody else wrote.
        conn.execute(
            "UPDATE admin_audit_log SET restored_at = ? WHERE id = ? AND action = 'DELETE_USER'",
            (now_str, audit_id),
        )
        conn.commit()

        # The account is back, so the "do not recreate this" tombstone must go
        # too — otherwise seed_admins would skip an account that now exists and
        # is perfectly healthy.
        #
        # Placed after the commit, and relied upon to never raise: the restore is
        # already durable by this point, and `_set_deletion_tombstone` swallows
        # its own failures. Moving it inside the guarded writes would risk
        # reporting "Restore failed and was rolled back" for a restore that had
        # actually succeeded.
        _set_deletion_tombstone(u_name, present=False)

        # PROOF, not optimism. The account is read back from the database before
        # success is reported. Every earlier version of this function returned
        # whatever the code path believed had happened, which is how it managed
        # to say "restored" while creating nothing at all — and an administrator
        # reading that message had no way to tell. A restore that cannot be seen
        # in the users table is reported as a failure, whatever the intent was.
        try:
            _survived = username_exists(u_name)
        except Exception:
            # Cannot verify. Say so rather than claim a success nobody checked.
            return True, (
                f"The account '{u_name}' was written and the restore was committed, "
                "but the database could not be re-read to confirm it, so please "
                "check the account directory before assuming it is back."
            )
        if not _survived:
            return False, (
                f"The restore did not take: '{u_name}' is still not in the account "
                "directory. Nothing was left half-restored, and this deletion can "
                "be restored again — please report this, as it means a value in "
                "the saved snapshot was rejected by the database."
            )

        msg = f"The account '{u_name}' and {fb_restored} feedback record(s) were restored."
        if fb_skipped:
            msg += (
                f" {fb_skipped} record(s) could not be restored, most likely "
                "because a matching (category, session) submission now exists."
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
    """Insert one feedback row. Returns (ok: bool, message: str).

    The sentiment columns are written from the rating, not from the caller.
    `save_data` used to take the label the page had computed and store it
    verbatim, which meant the row's sentiment and the row's rating could
    disagree — the exact contradiction the rating engine exists to remove.
    Deriving it here rather than in the form means there is no caller that can
    get it wrong, including a future one.

    `comment` is still a column so historical rows stay readable, but it is
    written empty: the free-text box has been removed from the forms.
    """
    conn = get_db()
    rating = sentiment.normalize_rating(d.get("rating"))
    label = sentiment.label_from_rating(rating) or "Neutral"
    try:
        conn.execute(
            """INSERT INTO feedback
               (username, category, student_level, rating, comment, timestamp,
                additional_info, sentiment, sentiment_score, sentiment_engine,
                sentiment_confidence, sentiment_cues, context_data, session)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d["username"], category, d["student_level"], rating,
                d.get("comment", ""), d["timestamp"], d.get("additional_info", ""),
                label,
                sentiment.rating_to_score(rating),
                sentiment.ENGINE_NAME,
                sentiment.rating_confidence(rating),
                "{}",
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


def count_session_submissions(session_name: str) -> int:
    """How many feedback rows belong to this session.

    Reported before a session is removed so the administrator knows what the
    deletion costs. The rows are NOT deleted — see `delete_academic_session`.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) FROM feedback WHERE session = ?", ((session_name or "").strip(),)
    ).fetchone()
    return int(row[0]) if row else 0


def delete_academic_session(session_name: str, deleted_by: str,
                            confirmed: bool = False) -> tuple[bool, str]:
    """Removes an academic session from the session list. Admin only; B-30.

    Two refusals, and neither is arbitrary:

      * The ACTIVE DEFAULT cannot be deleted. `get_active_session()` reads that
        flag, and `feedback.session` carries a DDL default of it, so removing it
        leaves new submissions defaulting to a session that no longer exists in
        the list. The fix is to promote another session first, which is a
        deliberate act rather than a side effect of a delete button.
      * The LAST remaining session cannot be deleted. The student portal and every
        filter are built around a session, so an app with none has nothing to show.

    `confirmed` must be passed by the caller, so this cannot be reached by a
    single stray click the way an unguarded button can.

    Feedback rows are deliberately LEFT ALONE. Deleting a session is a
    housekeeping act about which sessions are offered, not a request to destroy
    student submissions — and the rows stay reachable through the aggregate filter and
    through `load_data(session=...)`, so nothing is lost, they simply stop being
    individually selectable. The count is returned so the UI can say so.
    """
    name = (session_name or "").strip()
    if not name:
        return False, "No session was named."
    if not confirmed:
        return False, "Deleting a session must be confirmed before it happens."

    conn = get_db()
    row = conn.execute(
        "SELECT id, is_default FROM academic_sessions WHERE session_name = ?", (name,)
    ).fetchone()
    if not row:
        return False, f"Academic session '{name}' does not exist."

    total = conn.execute("SELECT COUNT(*) FROM academic_sessions").fetchone()[0]
    if total <= 1:
        return False, (
            f"'{name}' is the only academic session, so it cannot be deleted. "
            "Create the next session first."
        )
    if row[1]:
        return False, (
            f"'{name}' is the active default session and cannot be deleted. Make "
            "another session the active default first, then delete this one."
        )

    submissions = count_session_submissions(name)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute("DELETE FROM academic_sessions WHERE session_name = ?", (name,))
        # Recorded in the same trail as user deletions. It is not a DELETE_USER row,
        # so it never appears in the pending-restoration panel — it is history,
        # readable from `admin_audit_log` and aged out with everything else.
        conn.execute(
            """INSERT INTO admin_audit_log (
                action, target_username, target_full_name, target_role,
                performed_by, performed_at, feedback_rows_deleted,
                reset_rows_deleted, admin_corrections_deleted, reason, snapshot
            ) VALUES (?,?,?,?,?,?,?,0,0,?,NULL)""",
            (
                "DELETE_SESSION", name, None, "academic_session", deleted_by, now_str,
                submissions,
                f"Deleted by {deleted_by}; {submissions} submission(s) retained "
                f"and still visible under {ALL_SESSIONS_LABEL}",
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        return False, "The session could not be deleted. No changes were made."

    msg = f"Academic session '{name}' has been deleted."
    if submissions:
        msg += (
            f" Its {submissions} submission(s) were kept — they are still counted "
            f"under {ALL_SESSIONS_LABEL}, but this session is no longer offered as "
            "a filter."
        )
    return True, msg


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
    if not df.empty and "rating" in df.columns:
        # Re-apply the rating rule to rows that are already on disk.
        #
        # The stored `sentiment` column predates the rating engine: it was
        # written by VADER from the free-text comment, so historical rows can
        # carry a verdict that contradicts their own rating — the exact
        # "4 stars, Negative sentiment" display this replaced. Rather than a
        # migration that rewrites rows and loses the record of what the old
        # engine said, the authoritative label is derived here, at read time,
        # for every row old and new alike.
        df["rating"] = df["rating"].apply(sentiment.normalize_rating)
        df["text_sentiment"] = df["sentiment"]          # preserved, not used
        df["sentiment"] = df["rating"].map(sentiment.label_from_rating).fillna("Neutral")
        df["sentiment_score"] = df["rating"].map(sentiment.rating_to_score)
        df["sentiment_engine"] = sentiment.ENGINE_NAME
    if not df.empty and "admin_corrected_sentiment" in df.columns:
        # An administrator's manual correction outranks the automatic label —
        # it is the one case where a human has deliberately overridden the
        # scale, and silently discarding it would throw away that decision.
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


# ══════════════════════════════════════════════════════════════════════
#  PER-TARGET ROLLUPS
#
#  Three administrative questions the category-wide counters cannot answer:
#
#    * which lecturer should be spoken to, and about what   (all levels)
#    * which course in which level needs reworking           (by level)
#    * what infrastructure should be repaired first          (all levels)
#
#  They live here rather than on the pages so that what the dashboard shows and
#  what a CSV export contains come from one implementation — the two were
#  previously written separately and disagreed.
#
#  Every one of them reads `context_data`, which is a free-form JSON column, so
#  each goes through `context_text_list`. That is not defensive decoration: a
#  nested list in that blob is unhashable, and handing one to `Counter` raises
#  TypeError and takes the whole page down.
# ══════════════════════════════════════════════════════════════════════

_CTX_CHALLENGES_KEY = "challenges"
_CTX_METHODS_KEY = "effective_methods"
_CTX_EMPHASIS_KEY = "emphasis_areas"
_CTX_FACILITIES_KEY = "facilities_flagged"
_CTX_URGENCY_KEY = "urgency"


def lecturer_summary(session: str | None = None, top_n: int = 3) -> list[dict]:
    """Every lecturer rated, with the challenges flagged against them.

    Deliberately NOT split by level. One member of staff can be rated by a
    200-level and a 400-level student for different courses, and the question
    an administrator is answering — "who do I speak to, about what" — is about
    the person, not about each cohort separately. Splitting it would hide a
    pattern that only becomes visible once the cohorts are combined.

    `responses` counts students, not flags: a student who ticks three
    challenges for one lecturer is still one response, and that count is what
    says how much evidence a pattern rests on.

    Grouping is on `lecturer_group_key`, not the raw name, so "Dr. A. I.
    Otuonye" and a bare "Otuonye" are one person — and, because the handbook
    lists two EzEs, the initials are part of that key. Merging them would tell
    an administrator one person was praised for something the other was
    flagged for.
    """
    df = load_data("Lecturer Teaching Style", session=session)
    if df.empty:
        return []

    by_key: dict[str, dict] = {}
    for _, row in df.iterrows():
        ctx = parse_context(row.get("context_data"))
        raw_name = str(ctx.get("lecturer_name") or "").strip()
        key = lecturer_group_key(raw_name) or "unspecified"
        entry = by_key.setdefault(key, {
            "key": key,
            "name": raw_name or "Not identified",
            "display": ("Not identified" if key == "unspecified"
                        else lecturer_display_for(key)),
            "known": bool(raw_name) and is_known_lecturer(raw_name),
            "_ratings": [],
            "_levels": set(),
            "_challenges": Counter(),
            "_methods": Counter(),
            "_students": set(),
        })
        try:
            entry["_ratings"].append(float(row.get("rating")))
        except (TypeError, ValueError):
            pass
        level = str(row.get("student_level") or "").strip()
        if level:
            entry["_levels"].add(level)
        username = str(row.get("username") or "").strip()
        if username:
            entry["_students"].add(username.lower())
        entry["_challenges"].update(context_text_list(ctx.get(_CTX_CHALLENGES_KEY), limit=40))
        entry["_methods"].update(context_text_list(ctx.get(_CTX_METHODS_KEY), limit=40))

    out = []
    for entry in by_key.values():
        ratings = entry.pop("_ratings")
        entry["levels"] = sorted(entry.pop("_levels"))
        entry["responses"] = len(entry.pop("_students"))
        entry["avg_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        entry["top_challenges"] = entry.pop("_challenges").most_common(top_n)
        entry["top_methods"] = entry.pop("_methods").most_common(top_n)
        out.append(entry)

    # Worst average first: the point of the table is who needs attention.
    out.sort(key=lambda r: (r["avg_rating"], -r["responses"]))
    return out


def course_summary(session: str | None = None, top_n: int = 3) -> list[dict]:
    """The most-mentioned courses per level, with the emphasis areas asked for.

    Grouped by level as well as by course, because a 200-level course and a
    500-level one are different questions: the handbook schedules them
    differently, they draw on different staff, and "this course needs
    reworking" is not actionable if it averages a 300-level and a 500-level
    result together.
    """
    df = load_data("Course Content", session=session)
    if df.empty:
        return []

    grouped: dict[tuple, dict] = {}
    for _, row in df.iterrows():
        ctx = parse_context(row.get("context_data"))
        course = str(ctx.get("course_rated") or "").strip()
        if not course:
            continue
        level = str(row.get("student_level") or "").strip() or "Unspecified"
        entry = grouped.setdefault((level, course), {
            "level": level,
            "course": course,
            "_ratings": [],
            "_emphasis": Counter(),
            "_students": set(),
        })
        try:
            entry["_ratings"].append(float(row.get("rating")))
        except (TypeError, ValueError):
            pass
        entry["_emphasis"].update(context_text_list(ctx.get(_CTX_EMPHASIS_KEY), limit=40))
        username = str(row.get("username") or "").strip()
        if username:
            entry["_students"].add(username.lower())

    by_level: dict[str, list] = {}
    for (level, course), entry in grouped.items():
        ratings = entry.pop("_ratings")
        entry["responses"] = len(entry.pop("_students"))
        entry["avg_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        entry["emphasis_areas"] = entry.pop("_emphasis").most_common(top_n)
        by_level.setdefault(level, []).append(entry)

    out = []
    for level, rows in by_level.items():
        # Most-mentioned first: a course two students rated badly is a stronger
        # signal than one a single student rated badly.
        rows.sort(key=lambda r: (-r["responses"], r["avg_rating"]))
        out.extend(rows[:top_n])
    return out


def facility_summary(session: str | None = None, top_n: int = 5) -> list[dict]:
    """The most-reported infrastructure items, across every level.

    Not split by level: a dead projector or an unstable supply affects all
    cohorts at once, and the repair decision is a single departmental one.
    """
    df = load_data("Facilities", session=session)
    if df.empty:
        return []

    items: dict[str, dict] = {}
    for _, row in df.iterrows():
        ctx = parse_context(row.get("context_data"))
        for item in context_text_list(ctx.get(_CTX_FACILITIES_KEY), limit=40):
            entry = items.setdefault(item, {
                "facility": item,
                "reports": 0,
                "_levels": set(),
                "_urgency": Counter(),
                "_locations": Counter(),
            })
            entry["reports"] += 1
            level = str(row.get("student_level") or "").strip()
            if level:
                entry["_levels"].add(level)
            urgency = str(ctx.get(_CTX_URGENCY_KEY) or "").strip()
            if urgency:
                entry["_urgency"][urgency] += 1
            location = str(ctx.get("location") or "").strip()
            if location:
                entry["_locations"][location] += 1

    out = []
    for entry in items.values():
        entry["levels"] = sorted(entry.pop("_levels"))
        # A dict, not most_common()'s list of pairs. Every other breakdown on
        # these pages counts into a Counter and hands back a list, and a caller
        # that then does `counts.get(...)` gets AttributeError — which is how
        # this very check first failed against the list version. One shape for
        # "how many said X" is worth more here than matching the neighbours.
        entry["urgency_counts"] = dict(entry.pop("_urgency").most_common())
        entry["top_locations"] = entry.pop("_locations").most_common(3)
        out.append(entry)

    out.sort(key=lambda r: (-r["reports"], r["facility"]))
    return out[:top_n]
