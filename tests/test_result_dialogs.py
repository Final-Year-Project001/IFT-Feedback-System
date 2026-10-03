"""Verification for the result-dialog mechanism (components.park_result_dialog).

Scope — what this file is FOR, and what it deliberately is not:

A modal is only the right answer for a *flow-completing* moment. Using one
for a form-validation error is a regression: the user is mid-form, the field
that needs fixing is on screen, and a dismiss click goes between them. So this
suite covers the success dialogs, and ALSO pins that the inline validation
alerts are still inline — i.e. that adding dialogs did not quietly turn every
`st.error` into a modal.

The park/render split is the part most likely to rot. It exists because
Streamlit's `st.rerun()` discards everything queued on the run that called it,
which is precisely why the original "Account created successfully" message had
to be parked in session_state. If a future change renders the dialog on the
same run as the rerun, it will flash once and vanish — and no amount of
reading the code will show that. So there is a check for it here.

Run: .venv\\Scripts\\python.exe tests\\test_result_dialogs.py
"""
import io
import os
import shutil
import sys
from pathlib import Path
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_dlg_")
# Not `shutil.copy2` — the live file is in WAL mode, so a plain file copy drops
# every commit since the last checkpoint and silently tests a stale database.
COPY = snapshot_live_db(TMP)

import streamlit as st  # noqa: E402
import db  # noqa: E402

db.DB_PATH = COPY
st.cache_resource.clear()
db.get_db.clear()

import components  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(ROOT, "app.py")

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}"
          f"{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


def by_label(elements, label):
    for el in elements:
        if (getattr(el, "label", None) or "") == label:
            return el
    return None


def fresh():
    # Absolute path: AppTest resolves a relative one against the CALLING file.
    return AppTest.from_file(APP, default_timeout=120).run()


# ── 1. The park/render contract ──
section("1. park_result_dialog stores exactly what the renderer reads")

FIELDS = ("message", "kind", "title", "details", "button_label")
st.session_state.clear()
components.park_result_dialog("Body text", kind="success", title="A Title",
                              details="Some detail", button_label="Go On")
payload = st.session_state[components._RESULT_DIALOG_KEY]
check("the payload is stored under the component's own key",
      components._RESULT_DIALOG_KEY in st.session_state)
for f in FIELDS:
    check(f"it stores '{f}'", f in payload, sorted(payload))
check("the stored values round-trip",
      payload["message"] == "Body text" and payload["title"] == "A Title"
      and payload["details"] == "Some detail" and payload["button_label"] == "Go On",
      payload)
check("the payload is JSON-safe (no exotic types)",
      all(isinstance(payload[f], (str, type(None))) for f in FIELDS))

# An unknown severity must not reach the CSS class, which is built by string
# concatenation: `.result-dialog-{kind}`. An unsanitised value there would
# silently produce a rule that matches nothing AND leave the icon lookup
# returning None.
st.session_state.clear()
components.park_result_dialog("x", kind="totally-made-up")
bogus = st.session_state[components._RESULT_DIALOG_KEY]["kind"]
check("an unknown kind is coerced to a real one", bogus == "info", bogus)
check("every allowed kind has an icon",
      all(k in components._DIALOG_ICON for k in
          ("success", "error", "warning", "info")),
      sorted(components._DIALOG_ICON))

# ── 2. The dialog pops, so it cannot reappear on refresh ──
section("2. A parked dialog is shown once and then cleared")

# Drive the real page: park, then run the app, which renders it.
st.session_state.clear()
components.park_result_dialog("Registration finished", kind="success",
                              title="Registration Complete",
                              button_label="Start Using the System")
check("the payload is present before the page runs",
      components._RESULT_DIALOG_KEY in st.session_state)

# A fresh AppTest has its own session_state, so the parked payload has to be
# re-parked inside that session for the render hook to see it. That is what the
# registration test below does end-to-end; here we only assert the pop
# semantics on the store we control.
at = fresh()
check("a fresh page raises no exception", not at.exception,
      [type(e.value).__name__ for e in at.exception])
check("a fresh page does NOT show a leftover dialog",
      not any((b.label or "") == "Start Using the System" for b in at.button),
      [b.label for b in at.button])

# render_parked_dialog() returns False and changes nothing when nothing is
# parked — the common case, on every ordinary page load.
st.session_state.clear()
check("render_parked_dialog() reports nothing to show",
      components.render_parked_dialog() is False)
check("...and left no residue", components._RESULT_DIALOG_KEY not in st.session_state)

# ── 3. Registration success produces the dialog ──
section("3. Registration: the success dialog appears on the far side of the redirect")

at = fresh()
by_label(at.segmented_control, "Select Portal").set_value("Student Portal").run()
by_label(at.button, "Create an Account").click().run()

form = [t.label for t in at.text_input]
check("the registration form rendered", "Choose a Username" in form, form)

by_label(at.text_input, "Full Name").set_value("Dialog Probe")
by_label(at.text_input, "Choose a Username").set_value("DlgProbe1")
by_label(at.text_input, "Email Address").set_value("dlgprobe@test.local")
by_label(at.text_input, "Password").set_value("probepass123")
by_label(at.text_input, "Confirm Password").set_value("probepass123")
by_label(at.button, "Create Account →").click().run()

check("registration raised no exception", not at.exception,
      [type(e.value).__name__ for e in at.exception])
check("the account really was created", db.username_exists("DlgProbe1"),
      db.username_exists("DlgProbe1"))
check("the user is signed in", at.session_state.get("password_correct") is True)
check("the dialog's dismiss button is on screen",
      by_label(at.button, "Start Using the System") is not None,
      [b.label for b in at.button])
# Assert on the BODY, not the title. `st.dialog(title)` renders its title as
# modal chrome owned by the frontend; AppTest exposes no element for it (there
# is no `at.dialog` collection at all), so asserting on the title would be
# asserting against something the harness cannot see. The body is a real
# st.markdown node and is the part this module actually controls.
body = " ".join((m.value or "") for m in at.markdown)
check("the dialog body is rendered", "result-dialog-success" in body, body[:120])
check("the dialog carries the success message",
      "created and you are now" in body)
check("the dialog shows the account details", "DlgProbe1" in body, body[:200])

# The whole point of parking: the payload must be CONSUMED. If it were left in
# session_state, every subsequent rerun — and every refresh — would re-open
# the modal over a page the user is trying to use.
check("the parked payload was consumed, not left behind",
      components._RESULT_DIALOG_KEY not in at.session_state,
      [k for k in at.session_state if "dialog" in k.lower()])
at.run()
check("a reload does not re-open the dialog",
      by_label(at.button, "Start Using the System") is None,
      [b.label for b in at.button])

# ── 4. Validation errors stayed INLINE ──
section("4. Form-validation errors are still inline, not modals")

at = fresh()
by_label(at.segmented_control, "Select Portal").set_value("Student Portal").run()
by_label(at.text_input, "Email Address").set_value("nobody@test.local")
by_label(at.text_input, "Password").set_value("wrongpassword")
by_label(at.button, "Sign In →").click().run()

check("a failed sign-in raised no exception", not at.exception,
      [type(e.value).__name__ for e in at.exception])
check("the error is shown inline on the page, not behind a modal",
      len(at.error) > 0, len(at.error))
check("no dismiss button was forced on the user",
      not any((b.label or "") in ("Continue", "Start Using the System")
              for b in at.button),
      [b.label for b in at.button])
check("the sign-in form is still usable straight away",
      by_label(at.text_input, "Password") is not None,
      [t.label for t in at.text_input])

# ── 5. The student signed in by the dialog is a real account ──
section("5. The dialog is shown only after a genuine registration")

check("the account can sign in by email",
      db.verify_login_by_email("dlgprobe@test.local", "probepass123")[0])
check("the dialog did not fire for an ordinary page load",
      not any((b.label or "") == "Start Using the System"
              for b in fresh().button),
      [b.label for b in fresh().button])

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f in failures:
        print(f"    - {f}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED -- live database untouched")
