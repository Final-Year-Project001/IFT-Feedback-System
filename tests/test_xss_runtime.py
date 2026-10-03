"""Runtime XSS probe (plan item T-11), driven through Streamlit's AppTest.

`tests/test_xss_static.py` reads the source and proves that every placeholder
*looks* escaped. That is a strong check and it is not enough on its own: it
reasons about names, and a name can be escaped in one branch and not another,
or escaped and then interpolated somewhere the gate does not model. The only
way to know what the browser would actually receive is to put a payload into
the database through the real save path and then render every page.

This submits `<script>alert("xss")</script>` — and an `onerror=` image — as
the comment, the lecturer name, the course name and the location, then signs
in as both a student and an administrator and walks every page. Each rendered
`st.markdown` fragment must contain the escaped form and must never contain
the raw one.

Run: .venv\\Scripts\\python.exe tests\\test_xss_runtime.py
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

TMP = tempfile.mkdtemp(prefix="futo_xssrun_")
APP = os.path.join(ROOT, "app.py")
COPY = snapshot_live_db(TMP)

import db  # noqa: E402

db.DB_PATH = COPY
db.get_db.clear()

import config  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

failures = []

PAYLOAD = '<script>alert("xss")</script>'
ATTR_PAYLOAD = '<img src=x onerror=alert(1)>'
# What `components.esc()` (html.escape with quote=True) turns them into.
ESCAPED = "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
ESCAPED_ATTR = "&lt;img src=x onerror=alert(1)&gt;"
# Markers that only ever appear if the payload reached the page UNESCAPED.
# Deliberately the whole opening tag, not bare `onerror=` or `<img`: an escaped
# payload still contains those substrings as visible text, and matching them
# would flag every safe page.
RAW_MARKERS = ("<script>alert(", "<img src=x onerror")
# The escaped counterparts, used to prove the field really rendered rather
# than being silently dropped.
ESCAPED_MARKERS = ("&lt;script&gt;alert(", "&lt;img src=x onerror")


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}"
          f"{('  -- ' + str(detail)) if detail else ''}")
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


def rendered(at):
    """Every HTML fragment Streamlit will actually pass through to the browser.

    Only `unsafe_allow_html=True` fragments count. A plain `st.markdown`
    escapes its text itself, so user input there cannot inject markup no matter
    what it contains — and auditing it would flag the app's own benign
    `**Courses rated:** <script>…` line, which is exactly the false positive
    this filter removes.
    """
    return "\n".join(
        (m.value or "") for m in at.markdown
        if getattr(m.proto, "allow_html", False)
    )


def sign_in_admin(at, username, password):
    seg = by_label(at.segmented_control, "Select Portal")
    if seg is not None:
        seg.set_value("Administrator").run()
    by_label(at.text_input, "Username").set_value(username)
    by_label(at.text_input, "Password").set_value(password)
    by_label(at.button, "Sign In").click().run()
    return at


def sign_in_student(at, email, password):
    seg = by_label(at.segmented_control, "Select Portal")
    if seg is not None:
        seg.set_value("Student Portal").run()
    by_label(at.text_input, "Email Address").set_value(email)
    by_label(at.text_input, "Password").set_value(password)
    by_label(at.button, "Sign In →").click().run()
    return at


def fresh():
    return AppTest.from_file(str(APP), default_timeout=120).run()


def assert_clean(at, label, expect_payload=True):
    """No raw payload marker may survive; the escaped one must if expected."""
    body = rendered(at)
    leaks = [m for m in RAW_MARKERS if m in body]
    check(f"{label}: no raw HTML from user text", not leaks,
          leaks if leaks else "")
    if expect_payload:
        shown = [m for m in ESCAPED_MARKERS if m in body]
        check(f"{label}: the payload was rendered in escaped form", bool(shown),
              "" if shown else "no escaped marker — the field may not have rendered")
    ex = exceptions_of(at)
    check(f"{label}: no uncaught exception", not ex, ex if ex else "")


EMAIL = "xssprobe@student.test"
PW = "xssprobe123"
ok, msg = db.create_user("XssProbe", EMAIL, "X Probe", PW, "student", "300")
check("fixture student created", ok, msg)

# The app's own active session, not `config.CURRENT_SESSION`: the pages filter
# on the former, so seeding under anything else stores rows the sweep never
# renders — and the test would pass by rendering nothing.
SESSION = db.get_active_session()
CATS = list(config.CATEGORIES)
print(f"  categories: {CATS}")

# Submit through the real save path, one row per category, with the payload in
# every field the plan calls out: the comment, the lecturer name, the course
# name and the location — plus the list-valued fields the tag renderer handles.
FIXTURES = {
    "Course Content": {
        "semester": PAYLOAD,
        "course_rated": PAYLOAD,
        "emphasis_areas": [PAYLOAD, ATTR_PAYLOAD],
    },
    "Lecturer Teaching Style": {
        "lecturer_name": PAYLOAD,
        "course_code": PAYLOAD,
        "effective_methods": [PAYLOAD],
        "challenges": [ATTR_PAYLOAD],
    },
    "Facilities": {
        "facilities_flagged": [PAYLOAD],
        "urgency": PAYLOAD,
        "location": PAYLOAD + " " + ATTR_PAYLOAD,
    },
    "Curriculum": {
        "missing_topics": [PAYLOAD],
        "outdated_areas": [ATTR_PAYLOAD],
        "industry_alignment": PAYLOAD,
    },
}

section("1. Seed the payloads through db.save_data")

for cat in CATS:
    ok, m = db.save_data(cat, {
        "username": "XssProbe", "category": cat, "session": SESSION,
        "student_level": "300", "rating": 2,
        "comment": f"{PAYLOAD} {cat} comment",
        "timestamp": "2026-01-01 09:00:00",
        "sentiment": "Negative", "sentiment_score": -0.5,
        "sentiment_confidence": 0.8,
        "context_data": FIXTURES.get(cat, {}),
    })
    check(f"seeded {cat!r}", ok, m)

db.get_db.clear()
rows = db.filter_by_username(db.load_data(), "XssProbe")
check("all four rows are stored", len(rows) == 4, len(rows))
check("the raw payload is stored verbatim (so the render check is meaningful)",
      rows["comment"].str.contains("<script>", regex=False).all())

section("2. Every student page escapes it")

at = sign_in_student(fresh(), EMAIL, PW)
check("student signed in", at.session_state.get("password_correct") is True,
      exceptions_of(at))
assert_clean(at, "Home", expect_payload=False)

for cat in CATS:
    nav = nav_radio(at)
    nav.set_value(cat).run()
    assert_clean(at, f"student {cat}")

nav_radio(at).set_value("My Statistics").run()
assert_clean(at, "student My Statistics")

section("3. Every administrator page escapes it")

admin_user = config.ADMIN_SEED_ACCOUNTS[0]["username"]
admin_pw = config.ADMIN_SEED_ACCOUNTS[0]["password"]
adm = sign_in_admin(fresh(), admin_user, admin_pw)
check("admin signed in", adm.session_state.get("password_correct") is True,
      exceptions_of(adm))
assert_clean(adm, "admin landing", expect_payload=False)

# Only these two pages show comment text and context as HTML; Overview is
# counters, and User Management is accounts and the audit trail.
COMMENT_PAGES = {"Full Dashboard", "Decision Insights"}
for page in ("Overview", "Full Dashboard", "Decision Insights", "User Management"):
    nr = nav_radio(adm)
    if nr is None or page not in nr.options:
        check(f"admin {page}: page is reachable", False,
              nr.options if nr else "no nav")
        continue
    nr.set_value(page).run()
    assert_clean(adm, f"admin {page}", expect_payload=page in COMMENT_PAGES)

section("4. The read-only confirmation view escapes it too")

# Sign in again and open a category the fixture already answered — that is the
# path that renders the quote-card and the structured-context card.
at2 = sign_in_student(fresh(), EMAIL, PW)
for cat in CATS:
    nav_radio(at2).set_value(cat).run()
    body = rendered(at2)
    shown = [m for m in ESCAPED_MARKERS if m in body]
    leaks = [m for m in RAW_MARKERS if m in body]
    check(f"read-only {cat}: the comment renders escaped, not raw",
          bool(shown) and not leaks,
          f"escaped={bool(shown)} leaks={leaks}")

db.get_db.clear()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f_ in failures:
        print(f"    - {f_}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED — no raw markup reaches the browser")
