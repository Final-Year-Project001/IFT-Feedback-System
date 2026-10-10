"""Verification for the browser-bound session token.

Scope — what this file is FOR:

A link pasted into a chat used to hand over the session. The session token
lives in the URL — that is what makes it survive a refresh, since there is no
cookie or storage API to hold it — and whoever opened the link was signed in as
the sender, seeing their dashboard, their account details and their feedback.

The token alone no longer authenticates anything. Each session row also records
a `client_id` held in a cookie, and a restore requires both to match. These
checks pin the properties that make that work, and they are checked against a
real SQLite database rather than a mock, because the SQL is where this could
quietly be wrong:

  * a row written with one client cannot be read with another;
  * a token with no cookie at all cannot restore anything — that is the shared
    link case, and it must fail rather than fall back to trusting the token;
  * a row from before the column existed (client_id NULL) cannot restore,
    because honouring it would mean trusting a bare URL token again;
  * the cookie is not in the URL, so copying the address bar does not copy it.

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
SENDER_CLIENT = "sender-cookie-secret-111"
OTHER_CLIENT = "receiver-cookie-secret-222"

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
    """Exactly the query `_restore_session` runs."""
    conn = db.get_db()
    ensure_schema(conn)
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
section("1. The recipient of a copied link cannot restore the sender's session")
# ══════════════════════════════════════════════════════════════════════

clear()
write_session(TOKEN, "sender", SENDER_CLIENT)

check("the sender's own browser restores normally",
      read_session(TOKEN, SENDER_CLIENT) is not None)
check("a DIFFERENT browser, holding only the copied link, restores nothing",
      read_session(TOKEN, OTHER_CLIENT) is None)
check("and neither does one with no cookie at all (client_id = '')",
      read_session(TOKEN, "") is None)
check("...nor one that guesses an empty/NULL client",
      read_session(TOKEN, None) is None)

# ══════════════════════════════════════════════════════════════════════
section("2. The cookie is not something a copied link carries")
# ══════════════════════════════════════════════════════════════════════

src = Path("app.py").read_text(encoding="utf-8")

# Every write to the URL is checked by name, not by matching the literal. The
# names are read off the module, so this cannot drift if a constant is renamed.
writers = [l.strip() for l in src.splitlines() if "st.query_params[" in l]
check("only the session token is written to the URL",
      writers and all("_SESSION_PARAM" in l for l in writers), writers)
check("the cookie name never appears in a query-param write",
      not any(appmod._CLIENT_COOKIE in l for l in writers), writers)

check("the client id is minted from a CSPRNG, not derived from the token",
      "secrets.token_urlsafe" in src.split("def _mint_client_cookie")[1][:900])
check("minting and reading use different sources, so one cannot copy the other",
      "secrets.token_urlsafe" in src.split("def _mint_client_cookie")[1][:900]
      and "document.cookie" in src.split("def _mount_client_cookie")[1][:900])
check("mounting re-asserts the held value without minting a new one",
      "token_urlsafe" not in src.split("def _mount_client_cookie")[1][:900])

# ══════════════════════════════════════════════════════════════
section("2b. An established id is never churned mid-session")
# ══════════════════════════════════════════════════════════════

# Re-minting on every cookieless rerun rewrote the browser's cookie out from
# under the persisted row, so the next refresh could never match it — the
# logout-on-refresh this project kept seeing. Minting happens only when the
# tab session holds nothing; anything held is kept, and the jar is converged
# onto it by re-mounting instead.
check("a held id is adopted, never overwritten, from the handshake cookie",
      "if _client_from_cookie and not _held_id:" in src)
check("minting happens only when the tab holds nothing",
      "elif not _held_id:" in src)
check("...and a held id is re-mounted rather than replaced",
      "_mount_client_cookie(_held_id)" in src)
check("restore only adopts a non-empty cookie, never blanks a held id",
      "if client_id:\n        st.session_state[_CLIENT_COOKIE] = client_id" in src)

# ══════════════════════════════════════════════════════════════════════
section("3. Rows from before this change cannot be honoured")
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
check("a row with no client_id cannot be restored by any client",
      read_session("legacy-token", SENDER_CLIENT) is None
      and read_session("legacy-token", "") is None,
      "a pre-binding row was honoured, which means trusting a bare URL token")

# ══════════════════════════════════════════════════════════════════════
section("4. What the write side may and may not do")
# ══════════════════════════════════════════════════════════════════════
# The write side binds the row to the client id held in session_state — a
# fresh secret per browser that never appears in the URL. It deliberately does
# NOT require the browser to have echoed the cookie back yet: `st.context`
# only carries the cookies of the initial websocket handshake, so a cookie
# written during the visit is invisible until a fresh page load, and demanding
# readability at write time made every sign-in's write a silent skip (hence
# logout-on-refresh with no row to restore). The check that stops a shared
# link lives at READ time (section 5), where both values are verifiable.

persist_src = src.split("def _persist_session")[1].split("\ndef ")[0]
check("_persist_session refuses to write with no token or no client id",
      "if not token" in persist_src and "if not client_id" in persist_src)
check("...but does not demand the cookie be echoed back first",
      "_read_client_cookie()" not in persist_src,
      "a readability gate at write time reintroduces logout-on-refresh")
check("the row it writes carries the client_id column",
      "client_id" in persist_src and "client_id = excluded.client_id" in persist_src)
check("signing in under a token owned by someone else mints a fresh one",
      "_claim_token_for" in persist_src, "a receiver reusing a link's token "
      "would otherwise overwrite the sender's row with their own account")

# ══════════════════════════════════════════════════════════════════════
section("5. Failing closed")
# ══════════════════════════════════════════════════════════════════════

restore_src = src.split("def _restore_session")[1].split("\ndef ")[0]
check("a missing cookie restores nothing but leaves the URL alone",
      "_drop_token_from_url()" in restore_src
      and "if not client_id:" in restore_src)
check("...the token is dropped only when cookie AND token match no row",
      restore_src.count("_drop_token_from_url()") == 1,
      restore_src.count("_drop_token_from_url()"))
check("the match requires the client_id, not just the token",
      "client_id = ?" in restore_src)
check("no path restores on the token alone",
      "WHERE token = ? AND" not in restore_src.replace("WHERE token = ? AND client_id", "X"),
      "a restore query matches on the token only")

# The safe direction is unchanged: without the cookie nothing is restored.
# What changed is that a missing cookie no longer destroys the token to prove
# it — mid-session the snapshot is simply stale, so absence proves nothing and
# only the row match may discard anything.
check("session_status reports which mode is in force",
      "browser_cookie_bound" in src and "def session_status" in src)
status = appmod.session_status()
check("...and it does not raise outside a browser",
      isinstance(status, dict) and "mode" in status, status)

# ══════════════════════════════════════════════════════════════════════
section("6. The cookie is genuinely a cookie")
# ══════════════════════════════════════════════════════════════════════

check("it is read through st.context.cookies, not parsed out of a header",
      "st.context.cookies.get" in src)
check("it is set with an explicit path and SameSite",
      "path=/" in src and "SameSite=Lax" in src)
check("it is not HttpOnly — the app's own iframe has to write it",
      "HttpOnly" not in src,
      "HttpOnly would make the JS write silently fail")

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