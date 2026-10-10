"""Verification for session persistence actually surviving a refresh.

Scope — what this file is FOR:

Two holes, both found by reading rather than by a failing test, because the
whole persistence layer switches itself off under AppTest (`_is_test_run`) —
so no existing suite could see either one:

  1. Registration never persisted. The register path set `password_correct`,
     `username` and `user` directly and never wrote a `web_sessions` row, so
     a freshly registered student was signed in only in memory. First refresh
     after registering dropped them on the login page. Sign-in (both portals)
     did persist; registration did not.

  2. The sign-in persist was one-shot. `_persist_session` runs at sign-in and
     must skip when the browser's cookie is not readable yet — the iframe that
     writes it may not have executed on that exact run. Nothing ever retried,
     so that miss was permanent: every later refresh dropped the user until
     they signed in again.

The fixes: registration persists like sign-in does, and `main()` retries the
persist on later runs while signed in (flagged by `_session_persist_ok`, so at
most one write per browser session). The binding is unchanged — a row is still
only written when BOTH the URL token and the cookie are readable here — so
`test_session_binding.py`'s fail-closed properties still hold.

The functional half below drives the REAL `_persist_session` /
`_restore_session` through probe scripts under AppTest, with only the two
browser-only sources faked (the test-run gate and the cookie reader). The URL
token and session_state are the genuine articles.

Run: .venv\\Scripts\\python.exe tests\\test_session_persist.py
"""
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_persist_")
COPY = snapshot_live_db(TMP)

import db  # noqa: E402

db.DB_PATH = COPY
db.get_db.clear()

import app as appmod  # noqa: E402
import st_compat  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


# ══════════════════════════════════════════════════════════════
section("1. Registration persists like sign-in does")
# ══════════════════════════════════════════════════════════════

login_src = Path("app_pages/login.py").read_text(encoding="utf-8")
reg_src = login_src.split("def _show_register")[1].split("\ndef ")[0]
check("the register path persists the new sign-in",
      "_persist_session" in reg_src, "registration sets session keys but writes no row")
check("...and it does so for the account just created",
      "username_clean" in reg_src.split("_persist_session")[1][:120],
      reg_src.split("_persist_session")[1][:120] if "_persist_session" in reg_src else "")
signin_src = login_src.split("def _establish_session")[1].split("\ndef ")[0]
check("sign-in still persists through the same helper",
      "_persist_session" in signin_src)

# ══════════════════════════════════════════════════════════════
section("2. A missed persist is healed on later runs")
# ══════════════════════════════════════════════════════════════

app_src = Path("app.py").read_text(encoding="utf-8")
main_src = app_src.split("def main()")[1]
check("main() retries the persist while signed in",
      "_session_persist_ok" in main_src and "_persist_session(" in main_src)
check("...only until one write lands (flagged, not every run)",
      main_src.count("_session_persist_ok") >= 2)
check("...and never under a test harness",
      "_is_test_run()" in main_src.split("_session_persist_ok")[0][-400:])
persist_src = app_src.split("def _persist_session")[1].split("\ndef ")[0]
check("_persist_session reports whether the row exists afterwards",
      "-> bool" in app_src.split("def _persist_session")[1][:60]
      and "return True" in persist_src and "return False" in persist_src)
check("...still refusing to write with no readable cookie",
      persist_src.index("_read_client_cookie()") < persist_src.index("INSERT"))

# ══════════════════════════════════════════════════════════════
section("3. The dialog modality is visible where it can be fixed")
# ══════════════════════════════════════════════════════════════

check("st_compat reports which dialog semantics are in force",
      callable(getattr(st_compat, "dialog_mode", None))
      and st_compat.dialog_mode() in ("exact-choice", "dismissible", "inline"),
      getattr(st_compat, "dialog_mode", lambda: "?")())

# ══════════════════════════════════════════════════════════════
section("3b. Every modal opens at the same moderate size")
# ══════════════════════════════════════════════════════════════

# The submit-confirmation modal ("small") is the reference users approved.
# The two user-management modals used to open "large" and dominate the
# screen; all four call sites are now small, so sizing is consistent and
# every modal fits a phone without forcing horizontal scroll.
import re  # noqa: E402

_dialog_calls = []
for _mod in ("components.py", "app_pages/user_management.py"):
    _src = Path(_mod).read_text(encoding="utf-8")
    _dialog_calls += re.findall(r"@st_compat\.dialog\(([^)]*)\)", _src)
check("every dialog in the app opens small",
      _dialog_calls and all('width="small"' in c for c in _dialog_calls),
      _dialog_calls)
check("no dialog still opens large", not any('width="large"' in c for c in _dialog_calls),
      [c for c in _dialog_calls if "large" in c])

# ══════════════════════════════════════════════════════════════
section("3c. A failed restore says why instead of failing silently")
# ══════════════════════════════════════════════════════════════

# A refresh that arrives with a token but cannot honour it records the reason
# (cookie vs row — never the token, never an account) so the login page can
# explain it; signing out drops the token so a deliberate sign-out never
# earns an "expired session" hint it did not ask for.
check("_restore_session records why it could not restore",
      app_src.count('_restore_note') >= 2, app_src.count("_restore_note"))
check("...distinguishing a missing cookie from a missing row",
      '"no_cookie"' in app_src and '"no_row"' in app_src)
check("signing out drops the URL token as well as the row",
      "_drop_token_from_url()" in app_src.split("Sign Out")[1][:1200]
      if "Sign Out" in app_src else False)
_login_src = Path("app_pages/login.py").read_text(encoding="utf-8")
check("the login page shows the reason once, then drops it",
      '_restore_note", None' in _login_src
      and "no_cookie" in _login_src and "no_row" in _login_src)

# ══════════════════════════════════════════════════════════════
section("4. Persist -> refresh -> restore round-trips for real")
# ══════════════════════════════════════════════════════════════

EMAIL = "persistprobe@student.test"
PW = "persistprobe1"
ok, msg = db.create_user("PersistProbe", EMAIL, "Pam Persist", PW, "student", "300")
check("fixture student created", ok, msg)
db.get_db.clear()

PROBE_PERSIST = os.path.join(TMP, "probe_persist.py")
with open(PROBE_PERSIST, "w", encoding="utf-8") as fh:
    fh.write(
        "import sys\n"
        f"sys.path.insert(0, {ROOT!r})\n"
        "import streamlit as st\n"
        "import db\n"
        f"db.DB_PATH = {COPY!r}\n"
        "db.get_db.clear()\n"
        "import app as appmod\n"
        "appmod._is_test_run = lambda: False\n"
        "appmod._read_client_cookie = lambda: 'probe-client-1'\n"
        "st.session_state[appmod._SESSION_TOKEN_KEY] = 'probe-token-1'\n"
        "st.session_state[appmod._CLIENT_COOKIE] = 'probe-client-1'\n"
        "ok = appmod._persist_session('PersistProbe', {'t': 1.0})\n"
        "conn = db.get_db()\n"
        "row = conn.execute(\n"
        "    'SELECT username, client_id FROM web_sessions WHERE token = ?',\n"
        "    ('probe-token-1',)).fetchone()\n"
        "st.session_state['probe_out'] = {\n"
        "    'persisted': bool(ok),\n"
        "    'row': list(row) if row else None,\n"
        "}\n"
    )

at = AppTest.from_file(PROBE_PERSIST, default_timeout=120).run()
out = dict(at.session_state.get("probe_out") or {})
check("persist reports the row exists afterwards", out.get("persisted") is True, out)
check("...bound to the token AND the cookie",
      out.get("row") == ["PersistProbe", "probe-client-1"], out.get("row"))
check("no exception in the persist path",
      not list(at.exception), [str(e.value)[:120] for e in at.exception])

PROBE_RESTORE = os.path.join(TMP, "probe_restore.py")
with open(PROBE_RESTORE, "w", encoding="utf-8") as fh:
    fh.write(
        "import sys\n"
        f"sys.path.insert(0, {ROOT!r})\n"
        "import streamlit as st\n"
        "import db\n"
        f"db.DB_PATH = {COPY!r}\n"
        "db.get_db.clear()\n"
        "import app as appmod\n"
        "appmod._is_test_run = lambda: False\n"
        "appmod._read_client_cookie = lambda: 'probe-client-1'\n"
        "st.query_params[appmod._SESSION_PARAM] = 'probe-token-1'\n"
        "appmod._restore_session()\n"
        "first = {\n"
        "    'signed_in': st.session_state.get('password_correct') is True,\n"
        "    'username': st.session_state.get('username'),\n"
        "}\n"
        "appmod._read_client_cookie = lambda: 'someone-elses-cookie'\n"
        "for _k in ('password_correct', 'username', 'user'):\n"
        "    st.session_state.pop(_k, None)\n"
        "appmod._restore_session()\n"
        "st.session_state['probe_out'] = {\n"
        "    'first': first,\n"
        "    'receiver_signed_in': st.session_state.get('password_correct') is True,\n"
        "}\n"
    )

at2 = AppTest.from_file(PROBE_RESTORE, default_timeout=120).run()
out2 = dict(at2.session_state.get("probe_out") or {})
first = out2.get("first") or {}
check("a refresh with token + cookie restores the user",
      first.get("signed_in") is True and first.get("username") == "PersistProbe",
      out2)
check("...and a copied link on another cookie still restores nothing",
      out2.get("receiver_signed_in") is not True, out2)
check("no exception in the restore path",
      not list(at2.exception), [str(e.value)[:120] for e in at2.exception])

db.get_db.clear()
shutil.rmtree(TMP, ignore_errors=True)

print()
failed = [r for r in results if not r[1]]
for name, ok, detail in results:
    line = f"  [{'PASS' if ok else 'FAIL'}] {name}"
    if detail and not ok:
        line += f"  -- {detail}"
    print(line)

print()
print("=" * 74)
if failed:
    print(f"  {len(failed)} CHECK(S) FAILED:")
    for name, _, detail in failed:
        print(f"    - {name}" + (f"  ({detail})" if detail else ""))
    print("=" * 74)
    sys.exit(1)
print(f"  ALL {len(results)} CHECKS PASSED")
print("=" * 74)
