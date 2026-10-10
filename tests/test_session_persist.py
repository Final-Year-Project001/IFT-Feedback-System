"""Verification for session persistence actually surviving a refresh.

Scope — what this file is FOR:

Three holes, all found by reading rather than by a failing test, because the
whole persistence layer switches itself off under AppTest (`_is_test_run`) —
so no existing suite could see them:

  1. Registration never persisted. The register path set `password_correct`,
     `username` and `user` directly and never wrote a `web_sessions` row, so
     a freshly registered student was signed in only in memory. First refresh
     after registering dropped them on the login page. Sign-in (both portals)
     did persist; registration did not.

  2. The sign-in persist was one-shot. `_persist_session` runs at sign-in and
     must skip when the browser's secret is not known yet — the identity
     component reports it on its own rerun. Nothing ever retried, so that miss
     was permanent: every later refresh dropped the user until they signed in
     again.

  3. A refresh on Streamlit Community Cloud could never restore, because the
     platform proxy strips handshake cookies and the old binding demanded one.

The fixes: registration persists like sign-in does; `main()` retries the persist
on later runs while signed in (flagged by `_session_persist_ok`, so at most one
write per browser session); and the browser binding moved from a cookie to a
`localStorage` secret read by a tiny component, which is not proxied and so
survives on Cloud. A restore now demands BOTH the URL token AND that secret, so
a copied link is refused. See `test_session_binding.py` for the read-side SQL.

The functional half below drives the REAL `_persist_session` /
`_restore_session` through probe scripts under AppTest, with only the
browser-only sources faked (the test-run gate and the browser secret reader).
The URL token and session_state are the genuine articles.

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
check("...refusing only a genuinely unbound write (no token or no secret)",
      "if not token" in persist_src and "if not client_id" in persist_src)
check("...taking the secret from the component, never from a cookie",
      "_CLIENT_ID_KEY" in persist_src and "st.context.cookies" not in persist_src,
      "a cookie is stripped by Cloud's proxy and cannot be the credential")

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
section("3c. Sign-out leaves no stale token behind")
# ══════════════════════════════════════════════════════════════

# Signing out drops the row and the URL token together, so the next visit is
# a clean first visit rather than a session that looks expired. (An earlier
# revision showed the failure reason on the login page; that banner is gone
# by request — the page is back to exactly what it was.)
check("signing out drops the URL token as well as the row",
      "_drop_token_from_url()" in app_src.split("Sign Out")[1][:1200]
      if "Sign Out" in app_src else False)
_signout_src = app_src.split("Sign Out")[1][:1600] if "Sign Out" in app_src else ""
check("...and keeps the browser secret across the session_state clear",
      "st.session_state.clear()" in _signout_src and "_CLIENT_ID_KEY" in _signout_src,
      "clearing the secret strands the next run on a 'Restoring…' screen")
_login_src = Path("app_pages/login.py").read_text(encoding="utf-8")
check("the login page carries no restore banner",
      "_restore_note" not in _login_src, "banner removed by request")

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
        # The browser secret has been reported by the component into
        # session_state; the write must land bound to it.
        "st.session_state[appmod._SESSION_TOKEN_KEY] = 'probe-token-1'\n"
        "st.session_state[appmod._CLIENT_ID_KEY] = 'probe-client-1'\n"
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
check("persist lands, bound to the browser secret",
      out.get("persisted") is True, out)
check("...bound to the token AND the session_state secret",
      out.get("row") == ["PersistProbe", "probe-client-1"], out.get("row"))
check("no exception in the persist path",
      not list(at.exception), [str(e.value)[:120] for e in at.exception])

PROBE_CLAIM = os.path.join(TMP, "probe_claim.py")
with open(PROBE_CLAIM, "w", encoding="utf-8") as fh:
    fh.write(
        "import sys\n"
        f"sys.path.insert(0, {ROOT!r})\n"
        "import streamlit as st\n"
        "import db\n"
        f"db.DB_PATH = {COPY!r}\n"
        "db.get_db.clear()\n"
        "import app as appmod\n"
        "appmod._is_test_run = lambda: False\n"
        "conn = db.get_db()\n"
        "try:\n"
        "    conn.execute(appmod._SESSION_TABLE_DDL)\n"
        "    conn.commit()\n"
        "except Exception:\n"
        "    pass\n"
        "conn.execute(\n"
        "    'INSERT INTO web_sessions (token, username, payload, created_at, seen_at, client_id)'\n"
        "    ' VALUES (?,?,?,?,?,?)',\n"
        "    ('probe-token-2', 'SomeoneElse', '{}', 1.0, 9999999999.0, 'alice-client'))\n"
        "conn.commit()\n"
        # Bob opens a link carrying SomeoneElse's token and signs in.
        "st.session_state[appmod._SESSION_TOKEN_KEY] = 'probe-token-2'\n"
        "st.session_state[appmod._CLIENT_ID_KEY] = 'bob-client'\n"
        "ok = appmod._persist_session('PersistProbe', {'t': 2.0})\n"
        "new_token = st.session_state.get(appmod._SESSION_TOKEN_KEY)\n"
        "alice = conn.execute(\n"
        "    'SELECT username, client_id FROM web_sessions WHERE token = ?',\n"
        "    ('probe-token-2',)).fetchone()\n"
        "bob = conn.execute(\n"
        "    'SELECT username FROM web_sessions WHERE token = ? AND client_id = ?',\n"
        "    (new_token, 'bob-client')).fetchone() if new_token != 'probe-token-2' else None\n"
        "st.session_state['probe_out'] = {\n"
        "    'persisted': bool(ok),\n"
        "    'fresh_token': new_token != 'probe-token-2',\n"
        "    'alice_intact': list(alice) == ['SomeoneElse', 'alice-client'] if alice else False,\n"
        "    'bob_row': list(bob) == ['PersistProbe'] if bob else False,\n"
        "}\n"
    )

atc = AppTest.from_file(PROBE_CLAIM, default_timeout=120).run()
outc = dict(atc.session_state.get("probe_out") or {})
check("signing in under another user's token mints a fresh one",
      outc.get("persisted") is True and outc.get("fresh_token") is True, outc)
check("...leaving the sender's row untouched",
      outc.get("alice_intact") is True, outc)
check("...with the new account bound under the fresh token",
      outc.get("bob_row") is True, outc)
check("no exception in the claim path",
      not list(atc.exception), [str(e.value)[:120] for e in atc.exception])

PROBE_STABLE = os.path.join(TMP, "probe_stable.py")
with open(PROBE_STABLE, "w", encoding="utf-8") as fh:
    fh.write(
        "import sys\n"
        f"sys.path.insert(0, {ROOT!r})\n"
        "import streamlit as st\n"
        "import db\n"
        f"db.DB_PATH = {COPY!r}\n"
        "db.get_db.clear()\n"
        "import app as appmod\n"
        "appmod._is_test_run = lambda: False\n"
        # The component always returns the SAME stored value while it is known.
        # Three consecutive establishes must not move it a millimetre -- that
        # churn is what broke every refresh.
        "appmod._browser_client_id = lambda: 'stable-client-7'\n"
        "appmod._establish_browser_identity()\n"
        "after_first = st.session_state.get(appmod._CLIENT_ID_KEY)\n"
        "appmod._establish_browser_identity()\n"
        "appmod._establish_browser_identity()\n"
        "after_third = st.session_state.get(appmod._CLIENT_ID_KEY)\n"
        # A component that has not reported yet must store nothing, not invent.
        "st.session_state.pop(appmod._CLIENT_ID_KEY, None)\n"
        "appmod._browser_client_id = lambda: ''\n"
        "appmod._establish_browser_identity()\n"
        "not_reported = st.session_state.get(appmod._CLIENT_ID_KEY)\n"
        "st.session_state['probe_out'] = {\n"
        "    'stable': after_first == 'stable-client-7' == after_third,\n"
        "    'not_reported': not_reported in (None, ''),\n"
        "}\n"
    )

ats = AppTest.from_file(PROBE_STABLE, default_timeout=120).run()
outs = dict(ats.session_state.get("probe_out") or {})
check("reruns never churn an established browser secret",
      outs.get("stable") is True, outs)
check("...while a component that has not reported yet stores nothing",
      outs.get("not_reported") is True, outs)
check("no exception in the identity path",
      not list(ats.exception), [str(e.value)[:120] for e in ats.exception])

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
        "def _reset():\n"
        "    for _k in ('password_correct', 'username', 'user'):\n"
        "        st.session_state.pop(_k, None)\n"
        "def _seed():\n"
        "    st.query_params[appmod._SESSION_PARAM] = 'probe-token-1'\n"
        # Case A: the sender's own browser -- the stored secret matches the row.
        "_seed()\n"
        "st.session_state[appmod._CLIENT_ID_KEY] = 'probe-client-1'\n"
        "appmod._restore_session()\n"
        "own = {'signed_in': st.session_state.get('password_correct') is True,\n"
        "       'username': st.session_state.get('username')}\n"
        # Case B: a browser holding ITS OWN different secret must be refused,
        # and the borrowed token dropped from the address bar.
        "_reset()\n"
        "st.session_state[appmod._CLIENT_ID_KEY] = 'someone-elses-secret'\n"
        "appmod._restore_session()\n"
        "receiver_signed_in = st.session_state.get('password_correct') is True\n"
        "borrowed_token_dropped = st.query_params.get(appmod._SESSION_PARAM, '') == ''\n"
        # Case C: the secret is not known yet and waiting is exhausted -- fail
        # closed rather than trust the bare token.
        "_reset()\n"
        "_seed()\n"
        "st.session_state[appmod._CLIENT_ID_KEY] = ''\n"
        "st.session_state[appmod._IDENTITY_WAITS_KEY] = 3\n"
        "appmod._restore_session()\n"
        "unknown_signed_in = st.session_state.get('password_correct') is True\n"
        # Case D: the secret is unknown AND no row claims the token -- a token a
        # sign-out or a fresh login page just minted. Restore must return at
        # once, not stop and wait, or the page hangs on 'Restoring…'. If it did
        # stop, the line below never runs and probe_out is never set.
        "_reset()\n"
        "st.query_params[appmod._SESSION_PARAM] = 'never-any-row-token'\n"
        "st.session_state[appmod._CLIENT_ID_KEY] = ''\n"
        "st.session_state.pop(appmod._IDENTITY_WAITS_KEY, None)\n"
        "appmod._restore_session()\n"
        "reached_after_no_row = True\n"
        "no_row_signed_in = st.session_state.get('password_correct') is True\n"
        "st.session_state['probe_out'] = {\n"
        "    'own': own,\n"
        "    'receiver_signed_in': receiver_signed_in,\n"
        "    'borrowed_token_dropped': borrowed_token_dropped,\n"
        "    'unknown_signed_in': unknown_signed_in,\n"
        "    'reached_after_no_row': reached_after_no_row,\n"
        "    'no_row_signed_in': no_row_signed_in,\n"
        "}\n"
    )

at2 = AppTest.from_file(PROBE_RESTORE, default_timeout=120).run()
out2 = dict(at2.session_state.get("probe_out") or {})
own = out2.get("own") or {}
check("a refresh with token + matching secret restores the user",
      own.get("signed_in") is True and own.get("username") == "PersistProbe",
      out2)
check("...a browser with its OWN different secret still restores nothing",
      out2.get("receiver_signed_in") is not True, out2)
check("...and the borrowed token is dropped from the address bar",
      out2.get("borrowed_token_dropped") is True, out2)
check("...a not-yet-known secret fails closed instead of trusting the token",
      out2.get("unknown_signed_in") is not True, out2)
check("...and a token with no row returns at once instead of waiting",
      out2.get("reached_after_no_row") is True
      and out2.get("no_row_signed_in") is not True, out2)
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
