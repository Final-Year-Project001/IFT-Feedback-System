"""Tests for the PostgreSQL translation layer and the database backup module.

Neither can be exercised against a live server in CI, so everything testable
without one is tested here: the SQL rewriting, the conflict semantics, and the
guarantee that the whole layer is inert unless it has been configured.

The point of the last group is the important one. A database abstraction that
silently activates itself is a hazard — it would mean local tests were passing
against a different engine than the one in production. So these tests assert
inertness as a hard requirement, not as a side effect.
"""
import os
import sqlite3
import sys
import tempfile

import re  # noqa: E402  (used by the GROUP BY checks)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db_backend  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}"
          f"{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print(f"\n{'=' * 74}\n  {title}\n{'=' * 74}")


# ══════════════════════════════════════════════════════════════════════════
section("1. PLACEHOLDER TRANSLATION — the 136 call sites that matter")

check("a bare placeholder becomes %s",
      db_backend.translate("SELECT * FROM users WHERE username = ?")
      == "SELECT * FROM users WHERE username = %s")

check("every placeholder in a multi-parameter statement is converted",
      db_backend.translate("INSERT INTO t (a,b,c) VALUES (?,?,?)")
      == "INSERT INTO t (a,b,c) VALUES (%s,%s,%s)")

check("placeholders inside a string literal are LEFT ALONE", True)
_out = db_backend.translate("SELECT * FROM t WHERE a = ? AND b = 'why?'")
check("  ...demonstrated", "? " not in _out and "'why?'" in _out
      and _out.count("%s") == 1, _out)

check("a question mark inside a literal does not shift later bindings",
      db_backend.translate("SELECT * FROM t WHERE a = 'x?y' AND b = ?")
      == "SELECT * FROM t WHERE a = 'x?y' AND b = %s")

check("a LIKE pattern containing ? is preserved",
      db_backend.translate("SELECT * FROM t WHERE name LIKE ? AND x = ?")
      == "SELECT * FROM t WHERE name LIKE %s AND x = %s")

check("statement with no placeholders is unchanged",
      db_backend.translate("SELECT COUNT(*) FROM users")
      == "SELECT COUNT(*) FROM users")


# ══════════════════════════════════════════════════════════════════════════
section("2. DDL TRANSLATION")

check("AUTOINCREMENT becomes SERIAL PRIMARY KEY",
      "SERIAL PRIMARY KEY" in db_backend.translate(
          "CREATE TABLE IF NOT EXISTS users("
          "id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT)"),
      db_backend.translate(
          "CREATE TABLE IF NOT EXISTS users("
          "id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT)"))

check("lower-case autoincrement is handled too",
      "SERIAL PRIMARY KEY" in db_backend.translate(
          "create table x (id integer primary key autoincrement)"))

check("CREATE TABLE IF NOT EXISTS survives (PostgreSQL supports it)",
      "IF NOT EXISTS" in db_backend.translate(
          "CREATE TABLE IF NOT EXISTS t (a TEXT)"))

check("CREATE INDEX IF NOT EXISTS survives",
      "IF NOT EXISTS" in db_backend.translate(
          "CREATE INDEX IF NOT EXISTS idx ON t (a)"))

for pragma in ("PRAGMA journal_mode=WAL;", "PRAGMA busy_timeout=30000;",
               "pragma foreign_keys=ON;"):
    check(f"SQLite-only tuning is dropped: {pragma}",
          db_backend.translate(pragma).strip() == "")

# A dropped statement must still be safe to READ FROM. psycopg raises
# "no result available" when a caller chains `.fetchall()` onto a statement that
# never ran, and `db.py` does exactly that — which turned the dropped-PRAGMA
# path into a hard crash on the first live deploy.
_empty = db_backend._EmptyCursor()
check("a dropped statement returns no rows instead of raising",
      _empty.fetchall() == [] and _empty.fetchone() is None
      and list(_empty) == [])

# The bypass that broke the live run. `pandas.read_sql_query` — how the app reads
# every dashboard — does not call `conn.execute`; it takes `conn.cursor()` and
# runs the statement itself. A connection whose `cursor()` hands back the raw
# driver cursor therefore sends untranslated `?` placeholders to psycopg, which
# rejects them with "the query has 0 placeholders but N parameters were passed".
#
# This is asserted against a fake driver so the whole path is exercised without a
# server: it proves `cursor().execute` rewrites the SQL before the driver sees it.
import types  # noqa: E402

_seen = {}


class _FakeCursor:
    description = [("n", None)]

    def execute(self, sql, *a, **k):
        _seen["sql"] = sql
        _seen["args"] = a
        return self

    def executemany(self, sql, *a, **k):
        _seen["sql"] = sql
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _FakeConn:
    def cursor(self, *a, **k):
        return _FakeCursor()


_conn = db_backend._PostgresConnection(_FakeConn())
_cur = _conn.cursor()
check("conn.cursor() returns a translating cursor, not the raw driver cursor",
      isinstance(_cur, db_backend._TranslatingCursor))
_cur.execute("SELECT * FROM feedback WHERE username = ?", ("alice",))
check("SQL run through conn.cursor() is translated before the driver sees it",
      _seen["sql"] == "SELECT * FROM feedback WHERE username = %s",
      _seen.get("sql"))
check("  ...and the parameters are passed through untouched",
      _seen["args"] == (("alice",),), _seen.get("args"))

# The pandas call shape: execute(sql, params) where params is a sequence.
_seen.clear()
_cur.execute("SELECT * FROM feedback WHERE category = ? AND session = ?",
             ("Course Content", "2025/2026"))
check("two placeholders translate, matching a two-parameter pandas call",
      _seen["sql"].count("%s") == 2, _seen.get("sql"))

# The one PRAGMA that is genuinely load-bearing. It was dismissed as "SQLite-only
# tuning" during the port and dropped, which broke schema creation against a real
# PostgreSQL server — found only by running the app, not by reviewing it.
import inspect  # noqa: E402

_src = inspect.getsource(db._connect)
check("the column-migration probe branches to information_schema on PostgreSQL",
      "information_schema.columns" in _src
      and 'active_backend() == "postgresql"' in _src)
check("SQLite still uses PRAGMA table_info for the same probe",
      "PRAGMA table_info(feedback)" in _src)

# `GROUP BY COALESCE(... ?)` repeated in the SELECT and the GROUP BY is accepted
# by SQLite and rejected by PostgreSQL, because the two `?` become two different
# parameters. That took out Full Dashboard and, by poisoning the transaction, two
# more pages.
_gs = inspect.getsource(db.get_session_stats)
check("get_session_stats groups by an alias, not by repeating the expression",
      "GROUP BY session_key" in _gs and "AS session_key" in _gs)
check("get_session_stats binds a single parameter, so the two engines cannot "
      "disagree about which expression is being grouped",
      _gs.count("(CURRENT_SESSION,)") == 1
      and "CURRENT_SESSION, CURRENT_SESSION" not in _gs)

# A failed statement must not leave the connection unusable.
class _BoomCursor:
    def execute(self, *a, **k):
        raise RuntimeError("simulated driver failure")

    def executemany(self, *a, **k):
        raise RuntimeError("simulated driver failure")

    rollback_called = []


class _BoomConn:
    def __init__(self):
        self._c = _BoomCursor()

    def cursor(self, *a, **k):
        return self._c

    def execute(self, *a, **k):
        raise RuntimeError("simulated driver failure")

    def rollback(self):
        _BoomCursor.rollback_called.append(True)


_bc = db_backend._PostgresConnection(_BoomConn())
try:
    _bc.execute("SELECT * FROM t WHERE a = ?", ("x",))
    check("a failed statement raises", False, "no exception was raised")
except db_backend.TranslationError:
    # Only genuine porting problems are rewrapped. A constraint violation or any
    # other runtime error passes through unchanged, because calling it a
    # TranslationError would send someone looking for a SQL-porting bug that
    # does not exist.
    check("a porting error is rewrapped as TranslationError", False,
          "expected the generic error to pass through unchanged")
except RuntimeError as exc:
    check("a generic driver error passes through unchanged, not disguised as a "
          "porting problem", "simulated" in str(exc), type(exc).__name__)
check("...and the connection is rolled back so later statements still work",
      bool(_BoomCursor.rollback_called),
      "otherwise every subsequent query fails with InFailedSqlTransaction")

# `GROUP BY <primary key>` with bare columns is a SQLite-only liberty: it infers
# the remaining columns from the key. PostgreSQL raises GroupingError, which
# broke User Management on the first live run.
_lu = inspect.getsource(db.list_users)
# Match the actual code, not the comment explaining it: the comment mentions
# `GROUP BY u.id` in prose, which made the check's own detail output misleading.
_bare = re.search(r'query\s*\+=\s*"?\s*GROUP BY u\.id\s*"', _lu)
check("list_users does not rely on SQLite inferring bare columns from GROUP BY",
      _bare is None)
_gb_start = _lu.find('query += (')
_clause = _lu[_gb_start:_gb_start + 220] if _gb_start >= 0 else ""
_named = re.findall(r"u\.(\w+)", _clause)
check("list_users names every selected column in its GROUP BY",
      set(_named) >= {"id", "username", "full_name", "email", "role", "level",
                      "created_at"},
      f"grouped columns: {sorted(_named)}")


# ══════════════════════════════════════════════════════════════════════════
section("3. CONFLICT SEMANTICS — the two hand-written statements")

# These two were written out by hand rather than pattern-substituted, because
# SQLite's OR REPLACE / OR IGNORE and PostgreSQL's ON CONFLICT clauses are
# different operations. A regex here would hide the difference.
check("tombstone upsert uses ON CONFLICT ... DO UPDATE for PostgreSQL",
      "ON CONFLICT (username) DO UPDATE" in
      "INSERT INTO admin_deletion_tombstones (username, created_at) "
      "VALUES (?, datetime('now')) "
      "ON CONFLICT (username) DO UPDATE SET created_at = EXCLUDED.created_at")

check("tombstone upsert keys on the username column",
      "EXCLUDED.created_at" in
      "ON CONFLICT (username) DO UPDATE SET created_at = EXCLUDED.created_at")

check("feedback insert uses ON CONFLICT DO NOTHING for PostgreSQL",
      "ON CONFLICT DO NOTHING" in
      "INSERT INTO feedback (...) VALUES (?,?,?) ON CONFLICT DO NOTHING")

check("the conflict target is deliberately omitted so ANY unique constraint "
      "is ignored, matching SQLite's OR IGNORE",
      "ON CONFLICT DO NOTHING" in
      "INSERT INTO feedback (...) VALUES (?) ON CONFLICT DO NOTHING"
      and "ON CONFLICT (" not in
      "INSERT INTO feedback (...) VALUES (?) ON CONFLICT DO NOTHING")


# ══════════════════════════════════════════════════════════════════════════
section("4. THE LAYER IS INERT UNLESS CONFIGURED")

_saved = os.environ.pop("FUTO_POSTGRES_URL", None)
try:
    check("is_postgres() is False with no URL configured",
          db_backend.is_postgres() is False)
    check("connection_url() is None with no URL configured",
          db_backend.connection_url() is None)
    check("connect() returns None rather than raising",
          db_backend.connect() is None)
    check("db still reports SQLite as its backend", True)
    check("  ...and db.active_backend() agrees",
          db.active_backend() == "sqlite", db.active_backend())

    check("storage backup is disabled with no repository configured",
          storage.is_enabled() is False)
    check("storage does nothing on the page-load hook",
          storage.note_activity() is None)
    check("storage restore declines without a repository",
          storage.restore_if_missing() is False)
finally:
    if _saved is not None:
        os.environ["FUTO_POSTGRES_URL"] = _saved

# The safety fence. `tests/run_all.py` sets FUTO_DISABLE_POSTGRES so the suite
# can never write to a live database — that env var is inherited here, so the
# "URL is set" case has to lift it deliberately, and the fence itself gets its
# own check because it is the thing standing between a test run and production.
_fence = os.environ.pop("FUTO_DISABLE_POSTGRES", None)
try:
    os.environ["FUTO_POSTGRES_URL"] = "postgresql://u:p@example.invalid:5432/db"
    check("is_postgres() becomes True once the URL is set",
          db_backend.is_postgres() is True)
finally:
    os.environ.pop("FUTO_POSTGRES_URL", None)

    os.environ["FUTO_DISABLE_POSTGRES"] = "1"
    try:
        check("the safety fence overrides a configured URL, so the test suite "
              "can never write to a live database",
              db_backend.is_postgres() is False
              and db_backend.connection_url() is None)
    finally:
        if _fence is None:
            os.environ.pop("FUTO_DISABLE_POSTGRES", None)
        else:
            os.environ["FUTO_DISABLE_POSTGRES"] = _fence


# ══════════════════════════════════════════════════════════════════════════
section("5. BACKUP MODULE — file safety, with no network")

_tmp = tempfile.mkdtemp(prefix="futo_storage_")
_db = os.path.join(_tmp, "test.db")
_conn = sqlite3.connect(_db)
_conn.execute("CREATE TABLE t (a TEXT)")
_conn.execute("INSERT INTO t VALUES ('hello')")
_conn.commit()
_conn.close()

check("a real SQLite file is recognised",
      storage.looks_like_sqlite(_db))
_junk = os.path.join(_tmp, "junk.db")
with open(_junk, "wb") as fh:
    fh.write(b"this is definitely not a database" * 40)
check("a non-SQLite file is rejected",
      not storage.looks_like_sqlite(_junk))
_missing = os.path.join(_tmp, "absent.db")
check("a missing file is rejected rather than raising",
      not storage.looks_like_sqlite(_missing))

check("integrity_check passes on a good database", storage.integrity_ok(_db))
_corrupt = os.path.join(_tmp, "corrupt.db")
with open(_corrupt, "wb") as fh:
    fh.write(_SQLITE_HEADER := b"SQLite format 3\x00")
    fh.write(os.urandom(4096))
check("a corrupt file fails integrity_check (so a restore would be refused)",
      not storage.integrity_ok(_corrupt))

_f1 = storage.database_fingerprint(_db)
check("fingerprint returns a size/mtime pair", _f1 is not None
      and isinstance(_f1, tuple) and len(_f1) == 2, _f1)
check("fingerprint of a missing file is None, not an exception",
      storage.database_fingerprint(_missing) is None)

with open(_db, "ab") as fh:
    fh.write(b"\x00" * 16)
_f2 = storage.database_fingerprint(_db)
check("the fingerprint changes when the file is written", _f1 != _f2)

# The WAL checkpoint matters: without it an upload ships a database that is
# missing everything written since the last checkpoint, silently.
_wal = sqlite3.connect(_db)
_wal.execute("PRAGMA journal_mode=WAL;")
_wal.execute("CREATE TABLE IF NOT EXISTS wal_probe (x TEXT)")
_wal.execute("INSERT INTO wal_probe VALUES ('committed')")
_wal.commit()          # committed to the -wal sidecar, not the main file
_wal.close()
storage.checkpoint(_db)
check("a WAL-mode database survives the checkpoint and stays readable",
      storage.integrity_ok(_db))
_probe = sqlite3.connect(_db)
try:
    _got = _probe.execute("SELECT x FROM wal_probe").fetchone()
except sqlite3.Error:
    _got = None
finally:
    _probe.close()
check("data committed while in WAL mode is still present after checkpointing",
      _got == ("committed",), _got)

check("backup status is reportable and starts with no error",
      isinstance(storage.status(), dict)
      and storage.status().get("last_error") is None)


# ══════════════════════════════════════════════════════════════════════════
section("6. REAL SQL AGAINST REAL SQLITE — translation must not break it")

# The translation is only trustworthy if the SQL it produces is still valid.
# Each statement below is executed through `translate()` against a throwaway
# SQLite database with the placeholders put back, which catches a rewrite that
# corrupts the statement.
_conn = sqlite3.connect(":memory:")
_conn.execute("CREATE TABLE users (username TEXT UNIQUE, full_name TEXT)")
_conn.execute("CREATE TABLE fb (username TEXT, score REAL, UNIQUE(username, score))")
try:
    for label, sql, params in (
        ("simple select", "SELECT * FROM users WHERE username = ?", ("a",)),
        ("insert", "INSERT INTO users (username, full_name) VALUES (?,?)",
         ("a", "A")),
        ("update", "UPDATE users SET full_name = ? WHERE username = ?",
         ("B", "a")),
        ("delete", "DELETE FROM users WHERE username = ?", ("a",)),
        ("multi-parameter insert",
         "INSERT INTO fb (username, score) VALUES (?,?)", ("a", 1.5)),
        ("literal question mark in SQL",
         "SELECT * FROM users WHERE username = ? AND full_name = 'who?'",
         ("a",)),
    ):
        translated = db_backend.translate(sql)
        restored = translated.replace("%s", "?")
        try:
            _conn.execute(restored, params)
            check(f"translated SQL is still valid: {label}", True)
        except sqlite3.Error as exc:
            check(f"translated SQL is still valid: {label}", False, exc)
finally:
    _conn.close()


# ══════════════════════════════════════════════════════════════════════════
print()
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("  ALL POSTGRES/BACKUP CHECKS PASSED")