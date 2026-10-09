"""The per-session Rain/Harmattan active-semester feature.

An academic session (2025/2026, 2026/2027, ...) is an academic *year*. Each one
runs exactly one active semester, and a student may only give feedback for that
one. Choosing the other must SAY so, not silently accept a submission the
department is not collecting yet.

This covers three layers, in order of how cheaply they fail:

  1. the database layer — the `active_semester` column exists (including on a
     table created before it existed), defaults sensibly, validates on write,
     and never returns something outside `config.SEMESTERS`;
  2. the gate itself — choosing the inactive semester explains itself and hides
     the form; switching to the active one reveals it again;
  3. the link between the two — the semester the student sees must be the one
     the database says is active, or the gate is decoration.

Run: .venv\\Scripts\\python.exe tests\\test_semester_gate.py
"""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_snapshot import snapshot_live_db  # noqa: E402

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


import config  # noqa: E402
import db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_semester_")
COPY = snapshot_live_db(TMP)
_ORIG_DB = db.DB_PATH
db.DB_PATH = COPY
db.get_db.clear()

ADMIN = "admin001"

section("1. The schema has a validated active_semester column")
conn = db.get_db()
cols = {c[1]: c for c in conn.execute("PRAGMA table_info(academic_sessions)").fetchall()}
check("academic_sessions.active_semester exists", "active_semester" in cols,
      sorted(cols))
check("...is NOT NULL", cols.get("active_semester", (None,) * 4)[3] == 1,
      cols.get("active_semester"))
stored_default = cols.get("active_semester", (None, None, None, None, None))[4]
if isinstance(stored_default, str) and len(stored_default) >= 2 and stored_default[0] in "'\"":
    stored_default = stored_default[1:-1]
check("...defaults to config.DEFAULT_SEMESTER", stored_default == config.DEFAULT_SEMESTER,
      f"stored {stored_default!r}, want {config.DEFAULT_SEMESTER!r}")

seeded = conn.execute(
    "SELECT active_semester FROM academic_sessions WHERE session_name = ?",
    (config.CURRENT_SESSION,)).fetchone()
check("the seeded current session has a real semester",
      seeded is not None and seeded[0] in config.SEMESTERS,
      seeded[0] if seeded else None)

section("2. create_academic_session stores and validates the semester")
ok, msg = db.create_academic_session("2029/2030", ADMIN, active_semester="Rain")
check("a session can be created with an explicit semester", ok, msg)
check("...and get_active_semester returns it",
      db.get_active_semester("2029/2030") == "Rain",
      db.get_active_semester("2029/2030"))

ok, msg = db.create_academic_session("2030/2031", ADMIN, active_semester="Bogus")
check("an unknown semester does not fail the create", ok, msg)
check("...it silently falls back to the default, so nothing invalid is stored",
      db.get_active_semester("2030/2031") == config.DEFAULT_SEMESTER,
      db.get_active_semester("2030/2031"))

check("an unknown session falls back to the default",
      db.get_active_semester("never/existed") == config.DEFAULT_SEMESTER)
check("the aggregate alias falls back to the default",
      db.get_active_semester(config.ALL_SESSIONS_LABEL) == config.DEFAULT_SEMESTER)

section("3. set_active_semester validates before writing")
ok, msg = db.set_active_semester("2029/2030", "Harmattan")
check("a valid switch succeeds", ok, msg)
check("...and is read back", db.get_active_semester("2029/2030") == "Harmattan",
      db.get_active_semester("2029/2030"))

ok, msg = db.set_active_semester("2029/2030", "Monsoon")
check("an unrecognised semester is refused", not ok, msg)
check("...and the stored value is untouched",
      db.get_active_semester("2029/2030") == "Harmattan",
      db.get_active_semester("2029/2030"))

ok, msg = db.set_active_semester("does/not/exist", "Rain")
check("switching a session that does not exist is refused", not ok, msg)

semesters = db.get_all_session_semesters()
check("get_all_session_semesters reports every configured session",
      set(semesters) >= {"2029/2030", "2030/2031"}, sorted(semesters))
check("...with values that are all valid semesters",
      set(semesters.values()) <= set(config.SEMESTERS), sorted(set(semesters.values())))
check("...including the one just switched",
      semesters.get("2029/2030") == "Harmattan", semesters.get("2029/2030"))

section("4. A table created before the column existed is migrated")
legacy = os.path.join(TMP, "legacy.db")
con = sqlite3.connect(legacy)
con.execute(
    """CREATE TABLE academic_sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT NOT NULL UNIQUE,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        created_by TEXT)""")
con.execute(
    """INSERT INTO academic_sessions
       (session_name, is_active, is_default, created_at, created_by)
       VALUES ('2019/2020', 1, 1, '2019-09-01 00:00:00', 'legacy')""")
con.commit()
con.close()

db.DB_PATH = legacy
db.get_db.clear()
lconn = db.get_db()
lcols = {c[1] for c in lconn.execute("PRAGMA table_info(academic_sessions)").fetchall()}
check("the defensive migration adds active_semester", "active_semester" in lcols,
      sorted(lcols))
row = lconn.execute(
    "SELECT active_semester FROM academic_sessions WHERE session_name = '2019/2020'"
).fetchone()
check("...and backfills the existing row with the default",
      row is not None and row[0] == config.DEFAULT_SEMESTER,
      row[0] if row else None)
check("get_active_semester works on the migrated table",
      db.get_active_semester("2019/2020") == config.DEFAULT_SEMESTER)

section("5. The student gate follows the stored active semester")
db.DB_PATH = COPY
db.get_db.clear()
db.set_active_semester(config.CURRENT_SESSION, "Harmattan")
active = db.get_active_semester(config.CURRENT_SESSION)
inactive = next(s for s in config.SEMESTERS if s != active)
check("the fixture session is set to a known active semester",
      active == "Harmattan", active)

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(ROOT, "app.py")
EMAIL = "semestergate@student.test"
PW = "gatepass1"
db.create_user("SemesterGate", EMAIL, "Semester Gate", PW, "student", "300")
db.get_db.clear()

CATEGORY = config.CATEGORIES[0]


def by_label(els, label):
    for el in els:
        if (getattr(el, "label", None) or "") == label:
            return el
    return None


def exceptions_of(at):
    return [f"{type(e.value).__name__}: {e.value}" for e in at.exception]


def sign_in_and_nav(at, category):
    by_label(at.segmented_control, "Select Portal").set_value("Student Portal").run()
    by_label(at.text_input, "Email Address").set_value(EMAIL)
    by_label(at.text_input, "Password").set_value(PW)
    by_label(at.button, "Sign In →").click().run()
    for r in at.radio:
        if (getattr(r, "label", None) or "") == "Navigation":
            r.set_value(category).run()
            break


at = AppTest.from_file(APP, default_timeout=180).run()
sign_in_and_nav(at, CATEGORY)
check("the feedback page loads", not exceptions_of(at), exceptions_of(at))
check("the semester picker is shown",
      by_label(at.radio, "Semester") is not None,
      [r.label for r in at.radio])

# Choosing the inactive semester must explain itself and hide the form.
by_label(at.radio, "Semester").set_value(inactive).run()
check("choosing the inactive semester does not crash", not exceptions_of(at),
      exceptions_of(at))
body = " ".join((m.value or "") for m in at.markdown)
check(f"the inactive semester is named in the explanation",
      f"The {inactive} semester is not active" in body, body[:220])
check("...and the active one is named as the way forward",
      active in body, body[:220])
check("no form is offered for the inactive semester",
      by_label(at.button, "Submit Feedback →") is None,
      [b.label for b in at.button])
check("no course picker is built for the inactive semester",
      by_label(at.selectbox, "Which course are you rating?") is None,
      [s.label for s in at.selectbox])

# Switching to the active semester must reveal the form.
switch = by_label(at.button, f"Switch to {active} and continue")
check("a switch affordance is offered", switch is not None,
      [b.label for b in at.button])
if switch is not None:
    switch.click().run()
    check("switching does not crash", not exceptions_of(at), exceptions_of(at))
    check("switching reveals the form",
          by_label(at.button, "Submit Feedback →") is not None,
          [b.label for b in at.button])
    check("the picker now reads the active semester",
          at.session_state.get("feedback_semester") == active,
          at.session_state.get("feedback_semester"))
    body2 = " ".join((m.value or "") for m in at.markdown)
    check("the gate is gone once the active semester is chosen",
          "is not active" not in body2, body2[:220])

# And an already-active selection shows the form on arrival.
at2 = AppTest.from_file(APP, default_timeout=180).run()
sign_in_and_nav(at2, CATEGORY)
check("the active semester is the default selection",
      at2.session_state.get("feedback_semester") == active,
      at2.session_state.get("feedback_semester"))
check("the form is shown without touching the picker",
      by_label(at2.button, "Submit Feedback →") is not None,
      [b.label for b in at2.button])

section("6. An administrator can flip the active semester from the dashboard")
admin = db.get_user("admin001")
if admin is None:
    check("the seeded admin account exists for the dashboard check", False)
else:
    # Re-set the password on the COPY so the login is deterministic regardless
    # of whether the live admin's password was changed after seeding.
    db.admin_set_password("admin001", "admingate123")

    at3 = AppTest.from_file(APP, default_timeout=180).run()
    by_label(at3.segmented_control, "Select Portal").set_value("Administrator").run()
    # The admin portal signs in by username; only the student portal uses email.
    by_label(at3.text_input, "Username").set_value("admin001")
    by_label(at3.text_input, "Password").set_value("admingate123")
    by_label(at3.button, "Sign In").click().run()
    for r in at3.radio:
        if (getattr(r, "label", None) or "") == "Navigation":
            r.set_value("Full Dashboard").run()
            break
    check("the administrator reaches the Full Dashboard",
          not exceptions_of(at3), exceptions_of(at3))

    current = db.get_active_semester(config.CURRENT_SESSION)
    other = next(s for s in config.SEMESTERS if s != current)
    flip = by_label(at3.button, f"Set {other} active for '{config.CURRENT_SESSION}'")
    check("the session list offers a set-semester control", flip is not None,
          [b.label for b in at3.button])
    if flip is not None:
        flip.click().run()
        check("flipping the semester does not crash", not exceptions_of(at3),
              exceptions_of(at3))
        check("the stored active semester changed",
              db.get_active_semester(config.CURRENT_SESSION) == other,
              db.get_active_semester(config.CURRENT_SESSION))
        banner = " ".join((e.value or "") for e in at3.success)
        check("a success banner names the new semester and the session",
              other in banner and config.CURRENT_SESSION in banner, banner[:200])
        # A control derived from the stored value must now offer the reverse
        # switch; a hard-coded label would keep saying the same thing.
        back = by_label(at3.button, f"Set {current} active for '{config.CURRENT_SESSION}'")
        check("the control now offers the reverse switch", back is not None,
              [b.label for b in at3.button])

db.DB_PATH = _ORIG_DB
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
