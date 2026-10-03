"""Does the `feedback.session` column actually have a usable DEFAULT?

`db.py:106` reads

    session TEXT NOT NULL DEFAULT '{CURRENT_SESSION}',

Whether that produces the literal string `{CURRENT_SESSION}` or the value of
the constant depends entirely on whether the enclosing DDL string is an
f-string. The source alone is ambiguous to read, and SQLite freezes a column
DEFAULT at CREATE TABLE time — so a table created before `CURRENT_SESSION`
changed keeps the OLD default forever, with no error anywhere.

This asks SQLite itself, and also inserts a row that omits `session` to see
what really lands in the column.

Run: .venv\\Scripts\\python.exe test_schema.py
"""
import io
import os
import shutil
import sqlite3
import sys
from pathlib import Path
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_snapshot import snapshot_live_db  # noqa: E402

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


import config  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_ddl_")
# Not `shutil.copy2` — the live file is in WAL mode, so a plain file copy drops
# every commit since the last checkpoint. This suite reads the DDL *as stored*,
# so a stale copy means it was checking a schema the database no longer has.
COPY = snapshot_live_db(TMP)

con = sqlite3.connect(COPY)
ddl = con.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='feedback'").fetchone()[0]
print("feedback DDL as stored in the live database:")
for line in ddl.splitlines():
    if "session" in line:
        print(f"    {line.strip()}")
print()

def unquote(v):
    """PRAGMA table_info reports a column default as the raw SQL literal, so a
    TEXT default arrives as "'2025/2026'" — with its SQL quotes still on."""
    if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


col = [c for c in con.execute("PRAGMA table_info(feedback)") if c[1] == "session"][0]
stored_default = unquote(col[4])
print(f"PRAGMA table_info(feedback).session -> dflt_value = {stored_default!r}")
print(f"config.CURRENT_SESSION             -> {config.CURRENT_SESSION!r}")
print()

check("the stored DEFAULT is a real session name, not an unformatted template",
      stored_default == config.CURRENT_SESSION,
      f"stored {stored_default!r}, config {config.CURRENT_SESSION!r}")

# Does the schema get created by an f-string? Check a FRESH table built by db.py.
con2 = sqlite3.connect(os.path.join(TMP, "fresh.db"))
import db  # noqa: E402

_orig = db.DB_PATH
db.DB_PATH = os.path.join(TMP, "fresh.db")
db.get_db.clear()
fresh_ddl = con2.execute(
    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
con2.close()

# db.py builds its schema in get_db(); easiest faithful check is to call it.
db.DB_PATH = os.path.join(TMP, "fresh2.db")
db.get_db.clear()
_conn = db.get_db()
_fresh_ddl = _conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='feedback'").fetchone()[0]
_fresh_col = [c for c in _conn.execute("PRAGMA table_info(feedback)")
              if c[1] == "session"][0]
print()
print("feedback.session dflt_value on a table db.py just created: "
      f"{unquote(_fresh_col[4])!r}")
check("a table db.py creates today has a correct DEFAULT",
      unquote(_fresh_col[4]) == config.CURRENT_SESSION,
      f"got {unquote(_fresh_col[4])!r}, want {config.CURRENT_SESSION!r}")

# And the decisive end-to-end test: insert omitting `session`.
try:
    _conn.execute(
        """INSERT INTO feedback (username, category, student_level, rating, comment, timestamp)
           VALUES ('DDLProbe','Course Content','300',3,'probe comment','2026-01-01 00:00:00')""")
    _conn.commit()
    _got = _conn.execute(
        "SELECT session FROM feedback WHERE username='DDLProbe'").fetchone()[0]
    check("a row inserted without `session` gets the real session",
          _got == config.CURRENT_SESSION, f"got {got!r}" if False else f"got {_got!r}")
except sqlite3.Error as exc:
    check("insert without `session` works", False, f"{type(exc).__name__}: {exc}")

_conn.close()
con.close()
db.DB_PATH = _orig
db.get_db.clear()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f_ in failures:
        print(f"    - {f_}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED")
