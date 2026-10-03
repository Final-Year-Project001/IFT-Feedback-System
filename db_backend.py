"""A PostgreSQL backend for the database layer, selectable at runtime.

WHY THIS EXISTS
---------------
SQLite stores the whole database in one file on the machine running the app.
Streamlit Community Cloud runs the app on a container whose disk is wiped when it
sleeps, restarts or is redeployed, so on a free host the data does not survive.
PostgreSQL keeps the data on a server that outlives the container, which is the
only way the data outlives a restart.

SQLite STAYS THE DEFAULT
------------------------
Nothing about this module is active until `FUTO_POSTGRES_URL` is set. With no
URL, `db.py` imports sqlite3 directly and behaves exactly as it always has. That
is deliberate: the local workflow and the entire existing test suite must keep
working without a database server anywhere in sight.

WHAT ACTUALLY NEEDS TRANSLATING
-------------------------------
Measured, not assumed. Of the SQLite-specific constructs in `db.py`:

  * **136 `?` placeholders.** SQLite and Python both use `?`; psycopg uses
    `%s`. Hand-editing 136 call sites would be unreviewable and easy to get
    subtly wrong, so the translation happens in one place instead: this module
    rewrites the SQL as it passes through. The rest of `db.py` keeps writing `?`.
  * **5 `INTEGER PRIMARY KEY AUTOINCREMENT`** in the DDL, which becomes
    `SERIAL PRIMARY KEY`. Applied to the statement text at connect time.
  * **`INSERT OR REPLACE` / `INSERT OR IGNORE`** — two statements. These are
    rewritten explicitly in `db.py` rather than by pattern here, because each one
    has different conflict semantics and a regex would hide that.
  * **`PRAGMA journal_mode` / `busy_timeout`** — SQLite-only tuning, skipped.

And, importantly, what does NOT need translating:

  * **All 16 timestamps are computed in Python** (`datetime.now().strftime(...)`)
    and passed as bind parameters. There are no SQL-side date functions, so
    date handling is already portable.
  * `.rowcount` — both drivers support it, and it is what the retention sweep
    returns.
  * There are no foreign keys, no `sqlite_master` queries, no `lastrowid`, no
    `executescript`, no `GROUP_CONCAT`, no `COLLATE NOCASE`.

HOW TO ENABLE IT
----------------
Set one secret in the Streamlit dashboard:

    FUTO_POSTGRES_URL = postgresql://user:password@host:5432/dbname

Supabase and Neon both offer free hosted Postgres and will give you that string.
Never put the URL in a file that gets committed.
"""
from __future__ import annotations

import os
import re
import sqlite3

__all__ = ["is_postgres", "connection_url", "connect", "translate",
           "TranslationError"]


class TranslationError(RuntimeError):
    """Raised when a statement cannot be translated safely.

    Deliberately fatal rather than best-effort. Silently passing untranslated SQL
    to either driver would corrupt data instead of failing loudly.
    """


def _url() -> str | None:
    # SAFETY FENCE. The test suite writes and deletes rows. It must never do
    # that to a live database, and a URL sitting in `.streamlit/secrets.toml`
    # is enough to make it happen — the setting that makes the deployed app
    # durable also silently redirects every local test run into production.
    #
    # `tests/run_all.py` sets this, and it is checked before anything else so no
    # amount of configuration can defeat it.
    if os.environ.get("FUTO_DISABLE_POSTGRES", "").strip() in ("1", "true", "yes"):
        return None

    for source in (os.environ.get("FUTO_POSTGRES_URL"),):
        if source and source.strip():
            return source.strip()
    # Streamlit secrets are the normal route when deployed.
    try:
        import streamlit as st
        secrets = getattr(st, "secrets", None)
        if secrets is not None and "FUTO_POSTGRES_URL" in secrets:
            value = secrets["FUTO_POSTGRES_URL"]
            if value and str(value).strip():
                return str(value).strip()
    except Exception:
        pass
    return None


def is_postgres() -> bool:
    """True when a PostgreSQL URL has been configured."""
    return bool(_url())


def connection_url() -> str | None:
    return _url()


# ── SQL translation ─────────────────────────────────────────────────────────

# `?` -> `%s`, but only outside string literals. A literal `?` inside quoted text
# (a LIKE pattern, say) must be left alone or the offsets shift and every
# subsequent parameter binds to the wrong column.
_PARAM = re.compile(r"(\?)(?=(?:[^']*'[^']*')*[^']*$)")


def _placeholders(sql: str) -> str:
    return _PARAM.sub("%s", sql)


# Applied to DDL only. `SERIAL` is the portable spelling for this shape; the
# explicit `GENERATED ... AS IDENTITY` form is preferred but requires 10+, and
# `SERIAL` behaves identically for an auto-incrementing primary key.
_AUTOINC = re.compile(
    r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", re.IGNORECASE)


def _autoincrement(sql: str) -> str:
    return _AUTOINC.sub("SERIAL PRIMARY KEY", sql)


def _wal_pragmas(sql: str) -> str:
    """Drop SQLite-only tuning statements."""
    stripped = sql.strip().lower()
    if stripped.startswith("pragma"):
        return ""
    return sql


def translate(sql: str) -> str:
    """Rewrite one SQLite statement into PostgreSQL.

    Public so the test suite can assert the translation without a live server.
    """
    text = _wal_pragmas(sql)
    if not text:
        return text
    text = _autoincrement(text)
    # `IF NOT EXISTS` is supported by PostgreSQL for CREATE TABLE and INDEX.
    return _placeholders(text)


# ── connection ──────────────────────────────────────────────────────────────

class _EmptyCursor:
    """Stands in for a statement that was dropped as SQLite-only.

    Returning a bare driver cursor here is a trap: psycopg raises
    `ProgrammingError: no result available` the moment a caller chains
    `.fetchall()`, which is exactly what `db.py` does. A skipped statement has
    no rows, so it reports none rather than raising.
    """

    rowcount = -1
    description = None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def fetchmany(self, size=1):
        return []

    def __iter__(self):
        return iter(())

    def close(self):
        pass


class _TranslatingCursor:
    """A cursor whose `execute` translates SQL first.

    Needed because callers do not always go through the connection's `execute`.
    `pandas.read_sql_query(query, conn, params=...)` — which is how the app reads
    every dashboard — takes `conn.cursor()` and runs the statement on that cursor
    directly. Without this wrapper the query reaches the driver untouched, so its
    `?` placeholders are not recognised and it fails with "the query has 0
    placeholders but N parameters were passed".

    That is not theoretical: it is exactly what happened on the first live run
    against PostgreSQL, on the most-used read in the application. Translating at
    the cursor removes the whole class of bypass, rather than patching the one
    call site that happened to be noticed.

    It holds its parent so that a statement failing on a dead connection can be
    retried on a fresh one — see `_retryable`.
    """

    def __init__(self, cursor, parent=None):
        self._cursor = cursor
        self._parent = parent

    def execute(self, sql, *args, **kwargs):
        text = translate(sql)
        if not text.strip():
            return self
        try:
            self._cursor.execute(text, *args, **kwargs)
        except Exception:
            if self._parent is None or not self._parent._retryable():
                raise
            # Dead connection, not bad SQL. Reopen and take a fresh cursor —
            # the old one belongs to the socket that just died.
            self._parent._reopen()
            self._cursor = self._parent._new_cursor()
            self._cursor.execute(text, *args, **kwargs)
        return self

    def executemany(self, sql, *args, **kwargs):
        text = translate(sql)
        if not text.strip():
            return self
        try:
            self._cursor.executemany(text, *args, **kwargs)
        except Exception:
            if self._parent is None or not self._parent._retryable():
                raise
            self._parent._reopen()
            self._cursor = self._parent._new_cursor()
            self._cursor.executemany(text, *args, **kwargs)
        return self

    def __getattr__(self, name):
        # fetchone/fetchall/rowcount/description and everything else pass
        # straight through to the real cursor.
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)


class _PostgresConnection:
    """A thin shim presenting the small slice of the DB-API that `db.py` uses.

    `db.py` only ever calls `execute`, `executemany`, `commit`, `rollback`,
    `close` and `cursor`. Rather than rewrite 47 functions against two drivers,
    this presents the same surface and translates SQL on the way through.

    The object returned by `execute` is the driver's own cursor, so every
    `fetchone` / `fetchall` / `rowcount` behaves exactly as it does today.

    It also owns recovery. A hosted database's connection dies when the container
    sleeps or the server suspends, and this shim is what `st.cache_resource`
    holds onto. So when a statement fails, this distinguishes "the socket died"
    from "the query was wrong" and replaces the socket in the first case, rather
    than leaving the cache holding an object that can never work again.
    """

    def __init__(self, conn, url):
        self._conn = conn
        self._url = url

    def _retryable(self, exc: Exception) -> bool:
        """True when a failure was the connection dying, not a bad statement.

        This distinction is the whole safety of the retry below, because the two
        cases look similar on screen and must not be handled the same way:
        retrying bad SQL just fails again and, worse, a retried write can
        double-apply. psycopg answers the question directly — `closed` once it
        knows the connection is gone, `broken` once an error has left it
        unusable — and neither is set by an ordinary constraint violation.
        """
        # Only retry on connection-class errors. The error types that matter
        # are OperationalError, InterfaceError, InternalError — anything that
        # means "the wire broke". A generic RuntimeError from a test, or a
        # TranslationError we wrapped, must not be retried.
        import psycopg
        if not isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError, psycopg.InternalError)):
            return False
        try:
            return bool(self._conn.closed or self._conn.broken)
        except Exception:
            return False

    def _reopen(self):
        """Replace the dead connection underneath this shim.

        The shim's *identity* is deliberately preserved. `st.cache_resource`
        hands back the exact object it cached, so returning a new shim would mean
        every caller holding the old one keeps using the dead socket, while the
        database silently accumulates a second connection per reconnect.
        Swapping what is inside is invisible to the cache and fixes everyone at
        once.
        """
        import psycopg
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = psycopg.connect(self._url, connect_timeout=10)

    def _new_cursor(self):
        return _TranslatingCursor(self._conn.cursor(), self)

    # ── the two methods that need translating ────────────────────────────────
    def execute(self, sql, params=()):
        text = translate(sql)
        if not text.strip():
            return _EmptyCursor()
        try:
            return self._conn.execute(text, params)
        except Exception as exc:
            if self._retryable(exc):
                self._reopen()
                try:
                    return self._conn.execute(text, params)
                except Exception as retry_exc:
                    exc = retry_exc
            # Roll back before propagating. PostgreSQL aborts the whole
            # transaction on the first failure and then refuses every subsequent
            # statement with `InFailedSqlTransaction`, so one bad query turns the
            # rest of the session into collateral damage — which is how a single
            # GROUP BY problem took out three separate pages.
            #
            # Safe to attempt unconditionally: if no transaction was open the
            # rollback is a no-op.
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise _explain(sql, text, exc) from exc

    def executemany(self, sql, seq):
        text = translate(sql)
        if not text.strip():
            return _EmptyCursor()
        try:
            return self._conn.executemany(text, seq)
        except Exception as exc:
            if self._retryable(exc):
                self._reopen()
                return self._conn.executemany(text, seq)
            raise

    # ── everything else is delegated untouched ──────────────────────────────
    def cursor(self, *a, **k):
        # Wrapped, not raw: see _TranslatingCursor. Anything that grabs a cursor
        # to run SQL on it — pandas included — gets the translation for free.
        return self._new_cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        # Anything not explicitly wrapped (row_factory, isolation_level, ...)
        # passes straight through to the real connection.
        return getattr(self._conn, name)


def _explain(original: str, translated: str, exc: Exception) -> Exception:
    """Turn a driver error into something a human can act on.

    PostgreSQL reports errors by position in the statement it received, which
    means the reported index points at the *translated* text and is off by the
    number of placeholders rewritten. Saying so is the difference between a
    five-minute fix and an hour of confusion.
    """
    message = str(exc)
    if "syntax error" in message.lower() or "does not exist" in message.lower():
        return TranslationError(
            f"PostgreSQL rejected a statement that SQLite accepted.\n"
            f"  sent    : {translated.strip()[:200]}\n"
            f"  original: {' '.join(original.split())[:200]}\n"
            f"  driver  : {message[:300]}"
        )
    return exc


def connect():
    """Open a PostgreSQL connection, or None when not configured.

    `check_same_thread` has no PostgreSQL equivalent and no counterpart here:
    psycopg connections are usable from multiple threads, though sharing one
    across Streamlit's thread pool still serialises statements.
    """
    url = _url()
    if not url:
        return None
    try:
        import psycopg
    except ImportError as exc:
        raise TranslationError(
            "FUTO_POSTGRES_URL is set but psycopg is not installed. Add "
            "'psycopg[binary]' to requirements.txt."
        ) from exc

    # `connect_timeout` matters on Cloud: a misconfigured or unreachable host
    # should fail in seconds, not hang until the platform kills the container.
    conn = psycopg.connect(url, connect_timeout=10)
    # The URL is kept so `_reopen` can rebuild the connection after the host
    # suspends it, without having to re-read and re-parse configuration.
    return _PostgresConnection(conn, url)


def probe(url: str | None = None, timeout: int = 10) -> dict:
    """Try to reach the database and report what happened.

    Used by `verify_postgres.py` so a configuration problem can be diagnosed
    before it is discovered during a presentation.
    """
    target = url or _url()
    if not target:
        return {"ok": False, "detail": "FUTO_POSTGRES_URL is not set"}
    try:
        import psycopg
    except ImportError as exc:
        return {"ok": False, "detail": f"psycopg is not installed ({exc})"}
    try:
        with psycopg.connect(target, connect_timeout=timeout) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                cur.execute("SELECT current_database();")
                name = cur.fetchone()[0]
        return {"ok": True, "detail": version.split(" on ")[0], "database": name}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}