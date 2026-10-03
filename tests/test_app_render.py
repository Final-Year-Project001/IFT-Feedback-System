"""Headless smoke test: drive every page in both roles through Streamlit's own
AppTest harness and fail on any uncaught exception.

This is the check that the F-04..F-07 User Management page and every other
edited page actually *render*, which `py_compile` cannot tell you.

Run: .venv\\\\Scripts\\\\python.exe test_app_render.py
"""
import io
import os
import shutil
import sys
from pathlib import Path
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_app_")
APP = os.path.join(ROOT, "app.py")
LIVE_DB = os.path.join(ROOT, "futo_feedback.db")
# `snapshot_live_db`, not `shutil.copy2`: the live file is in WAL mode, so a
# plain file copy silently discards everything committed since the last
# checkpoint and hands the suite a valid-but-stale database. See
# tests/db_snapshot.py.
COPY = snapshot_live_db(TMP)

# Point the app at the copy BEFORE app.py (and therefore db.py) is imported by
# the AppTest script runner, so nothing it renders can touch live data.
import db  # noqa: E402

db.DB_PATH = COPY
db.get_db.clear()

from streamlit.testing.v1 import AppTest  # noqa: E402

ADMIN_PAGES = ["Overview", "Full Dashboard", "Decision Insights", "User Management"]
STUDENT_PAGES = None  # filled in from config

import config  # noqa: E402
from pandas import isna as pd_isna  # noqa: E402

STUDENT_PAGES = ["Home"] + list(config.CATEGORIES) + ["My Statistics"]

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def exceptions_of(at):
    out = []
    for e in at.exception:
        out.append(f"{type(e.value).__name__}: {e.value}")
    return out


def _by_label(elements, label):
    """The login widgets carry no `key`, so they are addressed by label."""
    for el in elements:
        if (getattr(el, "label", None) or "") == label:
            return el
    return None


def sign_in_admin(at, username, password):
    """Logs in as an administrator through the real form, not by poking state.

    The portal must be switched to the Administrator view first, because both
    forms are not on screen at once.
    """
    seg = _by_label(at.segmented_control if hasattr(at, "segmented_control") else [], "Select Portal")
    if seg is not None:
        seg.set_value("Administrator").run()
    u = _by_label(at.text_input, "Username")
    p = _by_label(at.text_input, "Password")
    if u is None or p is None:
        raise AssertionError(
            f"admin sign-in fields not found; text_input labels = "
            f"{[t.label for t in at.text_input]}"
        )
    u.set_value(username)
    p.set_value(password)
    b = _by_label(at.button, "Sign In")
    if b is None:
        raise AssertionError(f"Sign In button not found; buttons = {[x.label for x in at.button]}")
    b.click().run()
    return at


def sign_in_student(at, email, password):
    seg = _by_label(at.segmented_control if hasattr(at, "segmented_control") else [], "Select Portal")
    if seg is not None:
        seg.set_value("Student Portal").run()
    e = _by_label(at.text_input, "Email Address")
    p = _by_label(at.text_input, "Password")
    if e is None or p is None:
        raise AssertionError(
            f"student sign-in fields not found; text_input labels = "
            f"{[t.label for t in at.text_input]}"
        )
    e.set_value(email)
    p.set_value(password)
    b = _by_label(at.button, "Sign In →")
    if b is None:
        raise AssertionError(f"Sign In button not found; buttons = {[x.label for x in at.button]}")
    b.click().run()
    return at


def nav_radio(at):
    for r in at.radio:
        if (getattr(r, "label", None) or "") == "Navigation":
            return r
    return None


def go_to(at, page):
    nav = nav_radio(at)
    assert nav is not None, "no Navigation radio"
    nav.set_value(page).run()
    return at


def fresh():
    # An ABSOLUTE path, because `AppTest.from_file` resolves a relative one
    # against the file that calls it — i.e. against `tests/`, not the working
    # directory. `"app.py"` worked when this script sat in the project root
    # and raises FileNotFoundError now that it lives one level down.
    return AppTest.from_file(str(APP), default_timeout=90).run()


def state_keys(at):
    """Session-state keys, tolerating an empty session."""
    try:
        return dict(at.session_state.filtered_state)
    except Exception:
        try:
            return {k: at.session_state[k] for k in at.session_state}
        except Exception:
            return {}


def state_get(at, key, default=None):
    try:
        return at.session_state[key]
    except Exception:
        return default


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


ADMIN_PW = config.ADMIN_SEED_ACCOUNTS[0]["password"]
ADMIN_USER = config.ADMIN_SEED_ACCOUNTS[0]["username"]

# A student with feedback, created here rather than borrowed from the database.
# Section 5 drives the two-tier delete dialog, which needs a *plain student* to
# select. It used to hard-code `DeAnalyst` — an account that only existed in
# the stale pre-WAL snapshot, so the selectbox raised
# `ValueError: 'DeAnalyst' is not in list` against the real database, where the
# only account is the seeded admin. A suite that depends on a previous
# developer's leftovers is a suite that fails for the next person to clone it.
TARGET = "AppProbeStudent"
db.create_user(TARGET, "appprobe@student.test", "App Probe", "appprobe123",
               "student", "400")
db.save_data("Internet", {
    "username": TARGET, "category": "Internet",
    "session": db.get_academic_sessions()[0], "student_level": "400",
    "rating": 2, "comment": "Fixture feedback for the render sweep",
    "timestamp": "2026-01-01 09:00:00", "sentiment": "Negative",
    "sentiment_score": -0.3, "sentiment_confidence": 0.8, "context_data": {},
})
# And a clean audit trail, so the Restore buttons on the page are only ever the
# ones this suite's own delete flow creates.
_conn = db.get_db()
_conn.execute("DELETE FROM admin_audit_log")
_conn.execute("DELETE FROM admin_deletion_tombstones")
_conn.commit()
db.get_db.clear()

# ── 1. Login page renders ──
section("1. Unauthenticated: the login portal")
at = fresh()
check("login page renders without error", not at.exception, exceptions_of(at))
check("the login portal renders its branding panel", len(at.markdown) > 5,
      f"{len(at.markdown)} markdown nodes")
check("the portal switch is present", hasattr(at, "segmented_control") and len(at.segmented_control) >= 1,
      [s.label for s in getattr(at, "segmented_control", [])])
check("no admin page is reachable before sign-in",
      not any("User Management" == b.label for b in at.button))
check("no Navigation radio before sign-in", nav_radio(at) is None,
      [r.label for r in at.radio])

# ── 2. Admin sign-in ──
section(f"2. Administrator sign-in as {ADMIN_USER}")
at = sign_in_admin(at, ADMIN_USER, ADMIN_PW)
check("sign-in produced no error", not at.exception, exceptions_of(at))
check("session says signed in", at.session_state.get("password_correct") is True,
      at.session_state.get("password_correct"))
check("session carries the role", (at.session_state.get("user") or {}).get("role") == "admin",
      at.session_state.get("user"))
check("the admin nav is now present", nav_radio(at) is not None)

# ── 3. Every admin page ──
section("3. Every administrator page renders")
for page in ADMIN_PAGES:
    at2 = sign_in_admin(fresh(), ADMIN_USER, ADMIN_PW)
    nav = nav_radio(at2)
    check(f"'{page}' appears in the admin nav", bool(nav) and page in nav.options,
          nav.options if nav else "no nav radio")
    if not nav:
        continue
    nav.set_value(page).run()
    ex = exceptions_of(at2)
    check(f"'{page}' renders without error", not ex, ex)
    check(f"'{page}' rendered body content", len(at2.markdown) > 3,
          f"{len(at2.markdown)} markdown nodes")
    check(f"'{page}' is not a 'no longer available' fallback",
          not any("no longer available" in (m.value or "") for m in at2.markdown))

# ── 4. User Management specifics ──
section("4. User Management page (F-04 / F-05 / F-06 / F-07)")
at3 = go_to(sign_in_admin(fresh(), ADMIN_USER, ADMIN_PW), "User Management")

ex = exceptions_of(at3)
check("renders without error", not ex, ex)
labels = [b.label for b in at3.button]
print(f"     buttons: {labels}")
check("a password-reset action exists",
      any("password" in (lbl or "").lower() for lbl in labels), labels)
check("a delete action exists",
      any("delete" in (lbl or "").lower() for lbl in labels), labels)
check("the directory is searchable",
      any("search" in (t.label or "").lower() for t in at3.text_input),
      [t.label for t in at3.text_input])
body = " ".join((m.value or "") for m in at3.markdown)
check("the danger zone is rendered", "danger-zone" in body)
check("the danger banner is rendered", "danger-banner" in body)
check("the audit trail section is rendered", "audit-log" in body or "Audit" in body)
check("the account directory table is rendered", len(at3.dataframe) >= 1,
      len(at3.dataframe))
if at3.dataframe:
    tbl = at3.dataframe[0].value
    check("the table lists the real accounts", ADMIN_USER in set(tbl["Username"]),
          list(tbl["Username"]))
    # Counts must be integers with no NaN leaking through the LEFT JOIN.
    for col in ("Feedback", "Corrections"):
        check(f"'{col}' has no NaN", not tbl[col].isna().any(), list(tbl[col]))
    # `last_submission` is legitimately empty for an account with no feedback.
    no_fb = tbl[tbl["Feedback"] == 0]
    check("'Last Submission' is empty only for accounts with no feedback",
          pd_isna(no_fb["Last Submission"]).all(), list(no_fb["Username"]))
    check("'Last Submission' is populated for accounts with feedback",
          not pd_isna(tbl[tbl["Feedback"] > 0]["Last Submission"]).any())
check("no confirm dialog is open on first load",
      "um_pending_delete" not in state_keys(at3),
      [k for k in state_keys(at3) if k.startswith("um_")])

# ── 5. The confirmation dialog gating ──
section("5. Two-tier confirmation gates the delete button")
target = TARGET
sel = at3.selectbox(key="um_target") if "um_target" in [w.key for w in at3.selectbox] else at3.selectbox[0]
sel.set_value(target).run()
ex = exceptions_of(at3)
check("selecting a target renders without error", not ex, ex)
rev_buttons = [b for b in at3.button if "delete" in (b.label or "").lower()]
check("a delete button is present after selecting a target", bool(rev_buttons),
      [b.label for b in at3.button])
check("the delete button is NOT disabled for a plain student",
      rev_buttons and not rev_buttons[0].disabled,
      rev_buttons[0].label if rev_buttons else None)

if rev_buttons:
    rev_buttons[0].click().run()
    ex = exceptions_of(at3)
    check("clicking 'Review and delete' opens the dialog without error", not ex, ex)
    check("a pending-delete state was recorded",
          at3.session_state.get("um_pending_delete") == target,
          at3.session_state.get("um_pending_delete"))
    dlg_texts = [t.label or t.placeholder for t in at3.text_input]
    print(f"     dialog text inputs: {dlg_texts}")
    check("the dialog asks for the exact username",
          any(target in (v or "") for v in dlg_texts), dlg_texts)
    check("a student does NOT get the DELETE ADMIN phrase",
          not any("DELETE ADMIN" in (v or "") for v in dlg_texts), dlg_texts)
    check("the dialog has an acknowledgement checkbox", len(at3.checkbox) >= 1,
          [c.label for c in at3.checkbox])
    confirm = [b for b in at3.button if "delete permanently" in (b.label or "").lower()]
    check("the confirm button is present", bool(confirm),
          [b.label for b in at3.button])
    check("the confirm button STARTS DISABLED", confirm and confirm[0].disabled)
    check("a 'still required' explanation is shown",
          any("Still required" in (c.value or "") for c in at3.caption),
          [c.value for c in at3.caption])

    # Type the username but do not tick the box -> still disabled.
    typed = [t for t in at3.text_input if target in (t.label or "")]
    check("the username field is identifiable", bool(typed), dlg_texts)
    if typed:
        typed[0].set_value(target).run()
        confirm = [b for b in at3.button if "delete permanently" in (b.label or "").lower()]
        check("still disabled after typing the username (box unticked)",
              confirm and confirm[0].disabled)
        check("the caption now only cites the unticked box",
              any("acknowledgement" in (c.value or "") for c in at3.caption),
              [c.value for c in at3.caption])
        at3.checkbox[0].check().run()
        confirm = [b for b in at3.button if "delete permanently" in (b.label or "").lower()]
        check("ENABLED once both gates are satisfied", confirm and not confirm[0].disabled,
              confirm[0].label if confirm else None)

    # Cancel must abandon the flow.
    cancel = [b for b in at3.button if (b.label or "").lower() == "cancel"]
    if cancel:
        cancel[0].click().run()
        check("cancel clears the pending deletion",
              not at3.session_state.get("um_pending_delete"),
              at3.session_state.get("um_pending_delete"))
        check("cancel produced no error", not exceptions_of(at3), exceptions_of(at3))

# ── 6. Self-deletion is refused in the UI too ──
section("6. Self-deletion is refused in the UI (not just the server)")
at4 = go_to(sign_in_admin(fresh(), ADMIN_USER, ADMIN_PW), "User Management")
sel4 = [s for s in at4.selectbox if s.key == "um_target"] or at4.selectbox
sel4[0].set_value(ADMIN_USER).run()
ex = exceptions_of(at4)
check("rendering the self row does not error", not ex, ex)
body = " ".join((m.value or "") for m in at4.markdown)
check("an explanation is shown for why self-deletion is blocked",
      "signed in with" in body or "Self-deletion is blocked" in body)
self_delete = [b for b in at4.button
               if "delete account" in (b.label or "").lower()]
check("the delete button is present but DISABLED for yourself",
      self_delete and self_delete[0].disabled,
      self_delete[0].label if self_delete else "no button")

# ── 7. Student pages ──
section("7. Every student page renders")
db.create_user("ProbeStudent", "probe@student.test", "Pat Probe",
               "probestudent1", "student", "500")
db.get_db.clear()
for page in STUDENT_PAGES:
    at6 = sign_in_student(fresh(), "probe@student.test", "probestudent1")
    if at6.session_state.get("password_correct") is not True:
        check(f"student sign-in for the '{page}' sweep", False,
              [f"{type(e.value).__name__}: {e.value}" for e in at6.exception])
        continue
    nav = nav_radio(at6)
    check(f"'{page}' appears in the student nav", bool(nav) and page in nav.options,
          nav.options if nav else "no nav radio")
    if not nav:
        continue
    nav.set_value(page).run()
    ex = exceptions_of(at6)
    check(f"student '{page}' renders without error", not ex, ex)
    check(f"student '{page}' is not a 'no longer available' fallback",
          not any("no longer available" in (m.value or "") for m in at6.markdown))

# ── 8. Role separation ──
section("8. Role separation")
at5 = sign_in_student(fresh(), "probe@student.test", "probestudent1")
check("student sign-in produced no error", not exceptions_of(at5), exceptions_of(at5))
check("session role is student", (at5.session_state.get("user") or {}).get("role") == "student")
admin_nav = nav_radio(at5)
check("the student nav offers no administrative page",
      bool(admin_nav) and not ({"Overview", "Full Dashboard", "Decision Insights",
                                "User Management"} & set(admin_nav.options)),
      admin_nav.options if admin_nav else None)

# A student must not be able to reach the admin page by other means either.
at5b = go_to(at5, "Home")
check("a student session never gains admin capabilities",
      (at5b.session_state.get("user") or {}).get("role") == "student")

# ── 9. Sign out ──
section("9. Sign out")
at6 = sign_in_admin(fresh(), ADMIN_USER, ADMIN_PW)
at6.button(key="logout_btn").click().run()
check("sign-out produced no error", not exceptions_of(at6), exceptions_of(at6))
check("the session is cleared", not at6.session_state.get("password_correct"))
check("the login portal is shown again", nav_radio(at6) is None,
      [r.label for r in at6.radio])
check("the portal switch is back", len(getattr(at6, "segmented_control", [])) >= 1)

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
