"""End-to-end check of the student submission path (U-08) plus the remaining
data-read helpers, driven through AppTest against a copy of the live database.

U-08 in particular: after a successful submit the page must come back as the
read-only "Submission Confirmed" view, must not still be an editable form, and
must not be re-submittable.

Run: .venv\\Scripts\\python.exe test_submission_flow.py
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

TMP = tempfile.mkdtemp(prefix="futo_submit_")
APP = os.path.join(ROOT, "app.py")
# Not `shutil.copy2` — the live file is in WAL mode, so a plain file copy drops
# every commit since the last checkpoint and silently tests a stale database.
COPY = snapshot_live_db(TMP)

import db  # noqa: E402

db.DB_PATH = COPY
db.get_db.clear()

import sentiment  # noqa: E402
import config  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def exceptions_of(at):
    return [f"{type(e.value).__name__}: {str(e.value)[:160]}" for e in at.exception]


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


def nav_radio(at):
    for r in at.radio:
        if (getattr(r, "label", None) or "") == "Navigation":
            return r
    return None


EMAIL = "submitprobe@student.test"
PW = "submitprobe1"
ok, msg = db.create_user("SubmitProbe", EMAIL, "Sam Submit", PW, "student", "300")
check("fixture student created", ok, msg)
db.get_db.clear()

# Pick a category the fixture student has not answered yet.
CATEGORIES = list(config.CATEGORIES)
CATEGORY = CATEGORIES[0]
SESSION = config.CURRENT_SESSION

section(f"1. Submit feedback for {CATEGORY!r} as a student")
at = AppTest.from_file(APP, default_timeout=120).run()
seg = by_label(at.segmented_control, "Select Portal")
seg.set_value("Student Portal").run()
by_label(at.text_input, "Email Address").set_value(EMAIL)
by_label(at.text_input, "Password").set_value(PW)
by_label(at.button, "Sign In →").click().run()
check("student signed in", at.session_state.get("password_correct") is True,
      exceptions_of(at))

nav = nav_radio(at)
check(f"'{CATEGORY}' is in the student nav", nav and CATEGORY in nav.options, nav.options)
nav.set_value(CATEGORY).run()
check("the form page renders", not exceptions_of(at), exceptions_of(at))
check("the submission form is shown first",
      bool(by_label(at.button, "Submit Feedback →")), [b.label for b in at.button])
check("no confirmation card yet",
      not any("Submission Confirmed" in (m.value or "") for m in at.markdown))

# There is no comment box any more — the free-text field was removed along with
# VADER, because a prose opinion and a 1-5 rating are two answers to one question
# and the rating is the comparable one. So there is no longer a comment to leave
# empty, and submitting on the default slider is a *valid* submission. What is
# still refused is a Lecturer Teaching Style form with no lecturer chosen, which
# is covered at the end of this file.
#
# The rest of this block is unchanged in intent: a submission on the default
# rating must not crash, and the row it writes must be real.
by_label(at.button, "Submit Feedback →").click().run()
ex = exceptions_of(at)
check("a submission does not crash", not ex, ex)
body = " ".join((m.value or "") for m in at.markdown)
check("the confirmation card is shown", "Submission Confirmed" in body, body[:200])
check("no comment box is offered any more",
      not at.text_area, [t.label for t in at.text_area])
_pre_submit = db.load_data(category=CATEGORY, session=SESSION)
check("the row was written", "SubmitProbe" in set(_pre_submit["username"]),
      list(_pre_submit["username"]))
check("...with the comment column left empty",
      all(not str(c or "").strip() for c in _pre_submit["comment"]),
      list(_pre_submit["comment"]))
check("...and its sentiment is the rating's own band, not a text reading",
      set(_pre_submit["sentiment"]) <= {"Positive", "Neutral", "Negative"},
      sorted(set(_pre_submit["sentiment"])))
# The rating slider defaults to 3, which must land on Neutral.
check("the default rating produces a Neutral band",
      set(_pre_submit["sentiment"]) == {"Neutral"},
      sorted(set(_pre_submit["sentiment"])))

# Only this student's row — other students' rows for the same category are
# expected and must be left alone.
rows = db.filter_by_username(
    db.load_data(category=CATEGORY, session=SESSION), "SubmitProbe")
check("exactly one row was written for the fixture student", len(rows) == 1, len(rows))
check("it belongs to the fixture student",
      len(rows) == 1 and rows.iloc[0]["username"] == "SubmitProbe",
      list(rows["username"]) if len(rows) else None)
# The comment column is kept so historical rows stay readable, and is written
# empty for new submissions. Asserted rather than skipped: a row silently
# acquiring text again would mean the form has been reverted.
check("the comment column is retained and empty",
      "comment" in rows.columns and len(rows) == 1
      and not str(rows.iloc[0]["comment"] or "").strip(),
      rows.iloc[0].get("comment") if len(rows) else None)
check("a sentiment label was computed",
      len(rows) == 1 and rows.iloc[0]["sentiment"] in ("Positive", "Neutral", "Negative"),
      rows.iloc[0]["sentiment"] if len(rows) else None)
check("the label is the rating's band",
      len(rows) == 1
      and rows.iloc[0]["sentiment"] == sentiment.label_from_rating(rows.iloc[0]["rating"]),
      (rows.iloc[0]["rating"], rows.iloc[0]["sentiment"]) if len(rows) else None)
check("the engine is recorded as the rating threshold engine",
      len(rows) == 1 and rows.iloc[0]["sentiment_engine"] == sentiment.ENGINE_NAME,
      rows.iloc[0].get("sentiment_engine") if len(rows) else None)
check("a confidence was computed",
      len(rows) == 1 and 0.0 <= float(rows.iloc[0]["sentiment_confidence"]) <= 1.0,
      rows.iloc[0]["sentiment_confidence"] if len(rows) else None)

body = " ".join((m.value or "") for m in at.markdown)
check("the page came back as the read-only Confirmation view",
      "Submission Confirmed" in body)
check("the editable form is GONE (U-08)",
      by_label(at.button, "Submit Feedback →") is None,
      [b.label for b in at.button])
check("there is no re-submit button of any kind",
      not any("submit" in (b.label or "").lower() for b in at.button),
      [b.label for b in at.button])
check("the rating slider is gone",
      not any("Rate from" in (s.label or "") for s in at.slider),
      [s.label for s in at.slider])
check("the comment box is gone", len(at.text_area) == 0, len(at.text_area))
check("the flash did not leak onto the portal",
      "Feedback submitted" not in body or "Submission Confirmed" in body)
check("the flash flag was consumed",
      not at.session_state.get("just_submitted"),
      at.session_state.get("just_submitted"))

# A reload must not re-celebrate.
at.run()
check("a later visit still shows the confirmation",
      any("Submission Confirmed" in (m.value or "") for m in at.markdown))
check("a later visit does not re-celebrate",
      at.session_state.get("just_submitted") is None)

section("2. Reloading does not re-render the form")
at.run()
check("still read-only after a second reload",
      by_label(at.button, "Submit Feedback →") is None,
      [b.label for b in at.button])

section("3. Every other category still accepts a submission")
for cat in CATEGORIES[1:]:
    at2 = AppTest.from_file(APP, default_timeout=120).run()
    by_label(at2.segmented_control, "Select Portal").set_value("Student Portal").run()
    by_label(at2.text_input, "Email Address").set_value(EMAIL)
    by_label(at2.text_input, "Password").set_value(PW)
    by_label(at2.button, "Sign In →").click().run()
    n2 = nav_radio(at2)
    n2.set_value(cat).run()
    if by_label(at2.button, "Submit Feedback →") is None:
        check(f"{cat}: form shown", False, [b.label for b in at2.button])
        continue
    # Lecturer Teaching Style requires a lecturer, and it is now a dropdown
    # (a text box was replaced because a hand-typed surname could not be grouped
    # reliably — "Dr. Obi" is not a department member).
    if cat == "Lecturer Teaching Style":
        sel = None
        for sb in at2.selectbox:
            if "Lecturer" in (sb.label or ""):
                sel = sb
                break
        if sel is None:
            check(f"{cat}: the lecturer picker exists", False,
                  [s.label for s in at2.selectbox])
            continue
        options = [o for o in sel.options if "Select a lecturer" not in o]
        check(f"{cat}: the picker lists the handbook's teaching staff",
              len(options) == len(config.TEACHING_STAFF),
              f"{len(options)} option(s)")
        sel.set_value(options[0]).run()
    by_label(at2.button, "Submit Feedback →").click().run()
    ex = exceptions_of(at2)
    saved = db.filter_by_username(db.load_data(category=cat, session=SESSION), "SubmitProbe")
    check(f"{cat}: submitted without error and stored", not ex and len(saved) == 1,
          ex or f"{len(saved)} row(s) for this student")
    check(f"{cat}: came back read-only",
          by_label(at2.button, "Submit Feedback →") is None)

section("4. The student's own stats reflect the new submissions")
at3 = AppTest.from_file(APP, default_timeout=120).run()
by_label(at3.segmented_control, "Select Portal").set_value("Student Portal").run()
by_label(at3.text_input, "Email Address").set_value(EMAIL)
by_label(at3.text_input, "Password").set_value(PW)
by_label(at3.button, "Sign In →").click().run()
nav_radio(at3).set_value("My Statistics").run()
check("My Statistics renders after submitting", not exceptions_of(at3), exceptions_of(at3))
body = " ".join((m.value or "") for m in at3.markdown)
check("My Statistics shows a non-zero submission count",
      any(ch.isdigit() and ch != "0" for ch in body))
check("the confidence tier language is used",
      any(t in body for t in ("High", "Moderate", "Low")),
      "no confidence tier wording found")

section("5. filter_by_username (C-07)")
df = db.load_data()
only = db.filter_by_username(df, "submitprobe")
check("filters to the one user", set(only["username"]) == {"SubmitProbe"}, set(only["username"]))
check("is case-insensitive", len(db.filter_by_username(df, "SUBMITPROBE")) == len(only))
check("an unknown user yields an empty frame", db.filter_by_username(df, "nobody").empty)
check("an empty string yields an empty frame", db.filter_by_username(df, "").empty)
# The match is exact-but-case-insensitive, like every other username lookup in
# the module: a partial string must match nothing rather than one user.
check("a partial string matches nothing rather than one user",
      db.filter_by_username(df, "submit").empty,
      list(db.filter_by_username(df, "submit")["username"]))
check("surrounding whitespace is ignored",
      len(db.filter_by_username(df, "  SubmitProbe  ")) == len(only))

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
