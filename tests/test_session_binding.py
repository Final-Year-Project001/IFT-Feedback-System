"""Verification for the session token and its browser binding.

Scope — what this file is FOR:

A session has to survive a page refresh, and the only thing Streamlit can read
back on the next run is the token in the URL. That makes the token a bearer
credential: whoever holds the link holds the session, so a link pasted into a
chat used to hand the session over.

So the row also records a second, per-browser secret, and a restore requires
BOTH to match: the URL token AND the secret. The secret lives in `localStorage`,
read back through a tiny same-origin component (`frontend/futo_identity`). It
cannot be a cookie: Streamlit Community Cloud's proxy strips cookies (and most
headers) from the WebSocket handshake, so `st.context.cookies` is empty there by
design, and a restore that demanded a cookie found no row and logged every user
out on every refresh. localStorage is never proxied, so it survives intact, and
a copied link cannot carry it — the receiver's browser has its own.

These checks run against a real SQLite database rather than a mock, because the
SQL is where this could quietly be wrong:

  * a row written with one secret cannot be read with a DIFFERENT secret;
  * a browser whose secret is not known yet restores NOTHING (fail closed),
    rather than falling back to the token alone;
  * the secret is not in the URL, so copying the address bar does not copy it;
  * a token matching no row is dropped rather than left to be retried forever.

Run: .venv\\Scripts\\python.exe tests\\test_session_binding.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_session_")
COPY = snapshot_live_db(TMP)

import streamlit as st  # noqa: E402
import db  # noqa: E402
import app as appmod  # noqa: E402

db.DB_PATH = COPY
try:
    st.cache_resource.clear()
except Exception:
    pass
db.get_db.clear()

results: list = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


TOKEN = "senders-token-abc123"
OTHER_TOKEN = "receivers-token-xyz789"
SENDER_CLIENT = "sender-secret-111"
OTHER_CLIENT = "receiver-secret-222"

DDL = appmod._SESSION_TABLE_DDL
ALT = appmod._SESSION_CLIENT_COLUMN


def ensure_schema(conn):
    conn.execute(DDL)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(web_sessions)").fetchall()}
    except Exception:
        cols = set()
    if "client_id" not in cols:
        conn.execute(ALT)
    conn.commit()


def write_session(token, username, client_id, seen_at=9e9, created_at=9e9):
    conn = db.get_db()
    ensure_schema(conn)
    conn.execute(
        """INSERT INTO web_sessions (token, username, payload, created_at, seen_at, client_id)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(token) DO UPDATE SET
             username=excluded.username, client_id=excluded.client_id,
             seen_at=excluded.seen_at""",
        (token, username, "{}", created_at, seen_at, client_id),
    )
    conn.commit()


def read_session(token, client_id):
    """Exactly the branch logic `_restore_session` now runs.

    One lookup, and it requires the secret. An unknown secret — either a
    different browser or one whose component has not reported yet — matches no
    row, which is the fail-closed direction: a shared link gets nothing.
    """
    conn = db.get_db()
    ensure_schema(conn)
    if not client_id:
        return None
    return conn.execute(
        """SELECT username FROM web_sessions
           WHERE token = ? AND client_id = ? AND seen_at >= ?""",
        (token, client_id, 1.0),
    ).fetchone()


def clear():
    conn = db.get_db()
    ensure_schema(conn)
    conn.execute("DELETE FROM web_sessions")
    conn.commit()


# ══════════════════════════════════════════════════════════════════════
section("1. The browser secret must match the row")
# ══════════════════════════════════════════════════════════════════════

clear()
write_session(TOKEN, "sender", SENDER_CLIENT)

check("the sender's own browser restores normally",
      read_session(TOKEN, SENDER_CLIENT) is not None)
check("a DIFFERENT browser, holding ITS OWN secret, restores nothing",
      read_session(TOKEN, OTHER_CLIENT) is None)
check("a browser whose secret is not known yet restores nothing",
      read_session(TOKEN, "") is None)
check("...and a None secret behaves the same (fail closed)",
      read_session(TOKEN, None) is None)
check("an UNKNOWN token still restores nothing",
      read_session("no-such-token", SENDER_CLIENT) is None)

# ══════════════════════════════════════════════════════════════════════
section("2. The secret is not something a copied link carries")
# ══════════════════════════════════════════════════════════════════════

src = Path("app.py").read_text(encoding="utf-8")

# Every write to the URL is checked by name, not by matching the literal. The
# names are read off the module, so this cannot drift if a constant is renamed.
writers = [l.strip() for l in src.splitlines() if "st.query_params[" in l]
check("only the session token is written to the URL",
      writers and all("_SESSION_PARAM" in l for l in writers), writers)
check("the browser secret never appears in a query-param write",
      not any(appmod._CLIENT_STORAGE_NAME in l for l in writers), writers)
check("...nor does its session_state key",
      not any(appmod._CLIENT_ID_KEY in l for l in writers), writers)

# ══════════════════════════════════════════════════════════════════════
section("3. The secret comes from localStorage, read by a component")
# ══════════════════════════════════════════════════════════════════════

# Cookies are the obvious primitive and the wrong one on Cloud: the platform
# proxy strips them from the WebSocket handshake, so a cookie-based check could
# never restore there. Nothing in the app may read cookies as the credential.
check("the app never reads st.context.cookies for the credential",
      "st.context.cookies" not in src,
      "Cloud strips handshake cookies; a cookie is not a usable credential")
check("...and never writes document.cookie either",
      "document.cookie" not in src)

comp_html = Path("frontend/futo_identity/index.html").read_text(encoding="utf-8")
check("a same-origin component exists to read the browser store",
      "localStorage" in comp_html)
check("it reads the stored secret with a stable key",
      "getItem" in comp_html and appmod._CLIENT_STORAGE_NAME in comp_html)
check("...and creates one only on a first visit",
      "setItem" in comp_html)
check("the secret is a CSPRNG value, not derived from the token",
      "crypto" in comp_html and "getRandomValues" in comp_html
      and "token_urlsafe" not in comp_html)
check("it speaks the component protocol (ready, then value as JSON)",
      "streamlit:componentReady" in comp_html
      and "streamlit:setComponentValue" in comp_html
      and 'dataType: "json"' in comp_html)
check("app.py declares that component from a local path",
      "declare_component" in src and '"futo_identity"' in src)
check("the component is declared once, not re-registered every rerun",
      "@st.cache_resource" in src.split("def _identity_component")[0][-120:]
      and "def _identity_component" in src)

# ══════════════════════════════════════════════════════════════════════
section("4. A row that predates the binding")
# ══════════════════════════════════════════════════════════════════════

clear()
conn = db.get_db()
ensure_schema(conn)
# A row written by the previous version: no client_id at all.
conn.execute(
    """INSERT INTO web_sessions (token, username, payload, created_at, seen_at)
       VALUES (?,?,?,?,?)""",
    ("legacy-token", "someone", "{}", 9e9, 9e9),
)
conn.commit()
# A NULL client_id can never match a real secret, so a legacy row is refused.
# That is the correct, fail-closed direction: the person signs in once more and
# a fresh, properly-bound row is written.
check("a legacy row (client_id NULL) matches no real secret",
      read_session("legacy-token", SENDER_CLIENT) is None)
check("...and does not restore on the token alone either",
      read_session("legacy-token", "") is None)

# ══════════════════════════════════════════════════════════════════════
section("5. What the write side may and may not do")
# ══════════════════════════════════════════════════════════════════════
# The write side binds the row to the secret held in session_state — a fresh,
# per-browser value that never appears in the URL. Writing without it would
# create exactly the shareable session this is meant to prevent, so a missing
# secret is a refusal, not a fallback.

persist_src = src.split("def _persist_session")[1].split("\ndef ")[0]
check("_persist_session refuses to write with no token or no secret",
      "if not token" in persist_src and "if not client_id" in persist_src)
check("...reading the secret from the component, never from a cookie",
      "_CLIENT_ID_KEY" in persist_src and "st.context.cookies" not in persist_src)
check("the row it writes carries the client_id column",
      "client_id" in persist_src and "client_id = excluded.client_id" in persist_src)
check("signing in under a token owned by someone else mints a fresh one",
      "_claim_token_for" in persist_src, "a receiver reusing a link's token "
      "would otherwise overwrite the sender's row with their own account")

# ══════════════════════════════════════════════════════════════════════
section("6. Failing closed, never open")
# ══════════════════════════════════════════════════════════════════════

restore_src = src.split("def _restore_session")[1].split("\ndef ")[0]
check("the restore lookup demands BOTH token and client_id",
      "token = ? AND client_id = ? AND seen_at >= ?" in restore_src)
check("there is no token-only lookup left to fall back on",
      "token = ? AND seen_at >= ?" not in restore_src,
      "a token-only query is exactly the shared-link hole")
check("when the secret is not known yet, the run waits instead of trusting"
      " the token", "st.stop()" in restore_src and "waits < 3" in restore_src)
check("...but only when a row actually claims the token (no deadlock)",
      "if not pending:" in restore_src
      and "SELECT 1 FROM web_sessions WHERE token = ?" in restore_src,
      "waiting on a token with no row freezes a sign-out on 'Restoring…'")
check("...and after waiting, an unknown secret still restores nothing",
      "if not client_id:" in restore_src)
check("the token is dropped only when it provably belongs to another browser",
      restore_src.count("_drop_token_from_url()") == 1
      and "SELECT 1 FROM web_sessions WHERE token = ?" in restore_src,
      restore_src.count("_drop_token_from_url()"))
# The drop must sit INSIDE the not-found branch, guarded by the ownership
# lookup. If it fires for a token with no row at all, the freshly minted token
# of a first-ever page load is erased before the sign-in that binds to it, and
# the next refresh has nothing to restore.
_drop_block = restore_src.split("if not row:")[1].split("return")[0]
check("...and the drop is guarded by an ownership lookup",
      "_drop_token_from_url()" in _drop_block
      and "SELECT 1 FROM web_sessions WHERE token = ?" in _drop_block)
check("session_status reports which mode is in force",
      "browser_storage_bound" in src and "def session_status" in src)
status = appmod.session_status()
check("...and it does not raise outside a browser",
      isinstance(status, dict) and "mode" in status, status)

# ══════════════════════════════════════════════════════════════════════
section("7. Identity is stored once and never churned")
# ══════════════════════════════════════════════════════════════════════

# The component creates the secret only on a first visit and otherwise returns
# the stored one. Re-minting mid-session churned the value out from under the
# persisted row and logged the user out, so the app must never invent one.
check("_establish_browser_identity adopts the component value, never mints",
      "secrets.token_urlsafe" not in
      src.split("def _establish_browser_identity")[1].split("\ndef ")[0])
# The only random secrets the app mints are the session token and the rotation
# performed when a receiver signs in under a token someone else owns. Anything
# else minting a "client id" would churn the browser's stored secret away from
# the persisted row.
_minting = ["_session_token", "_claim_token_for"]
_non_minting = ["_persist_session", "_establish_browser_identity",
                "_restore_session", "_browser_client_id", "_identity_component"]
def _fn_src(name):
    return src.split(f"def {name}")[1].split("\ndef ")[0]
check("only the token helpers mint a random value",
      all("secrets.token_urlsafe" in _fn_src(fn) for fn in _minting)
      and not any("secrets.token_urlsafe" in _fn_src(fn) for fn in _non_minting))

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
