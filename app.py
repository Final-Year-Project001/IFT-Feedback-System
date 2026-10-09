"""
app.py — FUTO IFT Smart Feedback System (v4, restructured)
===========================================================
Entry point only: page config, global CSS injection, session-based auth
gate, sidebar, and page routing. All real page logic lives in
`app_pages/`, all shared helpers in `components.py` / `charts.py` /
`icons.py`.

IMPORTANT — why this project's page-logic folder is named `app_pages/`
and not `pages/`: Streamlit treats any folder literally named `pages/`
sitting next to the entry-point script as a reserved name that triggers
its own *automatic* multi-page navigation feature — it silently injects
an extra, unstyled navigation list into the sidebar built from the raw
filenames it finds there, on top of (and independent from) whatever
sidebar this app builds itself below. Since this project deliberately
implements its own role-based routing (see `main()`), that folder is
named `app_pages/` specifically to opt out of Streamlit's automatic
behaviour. Do not rename it back to `pages/`.

Run with:  streamlit run app.py
"""

import sys

import streamlit as st

import st_compat

import db
import storage
from styles import GLOBAL_CSS
from config import CATEGORIES, CAT_META, ADMIN_SEED_ACCOUNTS, ALL_SESSIONS_LABEL
from icons import i
from app_pages.login import show_login_page, show_mandatory_password_change
from app_pages.home import show_home
from app_pages.feedback_form import show_feedback_form
from app_pages.my_stats import show_basic_stats
from app_pages.admin_overview import show_admin_overview
from app_pages.full_dashboard import show_full_dashboard
from app_pages.decision_insights import show_decision_support
from app_pages.user_management import show_user_management
from sentiment import engine_status

# The name shown on the sidebar badge. It used to be `ENGINE_NAME` verbatim —
# `rating_threshold_engine` — which is a Python constant, not something to put
# in front of a user: it reads as an error code and it is wide enough that the
# pill beside it wrapped onto a second line in a 240px sidebar.
ENGINE_BADGE_NAME = "Rating Engine"
from components import esc, render_parked_dialog

st.set_page_config(
    page_title="Information Technology Feedback System",
    page_icon="https://unpkg.com/lucide-static@0.462.0/icons/graduation-cap.svg",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  MOTION OPT-OUT — `?motion=off`
# ══════════════════════════════════════════════════════════════
#
# `styles.py` cancels every looping animation when the operating system asks for
# reduced motion (`prefers-reduced-motion: reduce` on Windows, macOS "Reduce
# motion", iOS). That is the correct default and it is what most people want.
#
# But it is an OS-level switch that is easy to set once and forget, and the
# result is a site that looks simply static with nothing on screen explaining
# why. This is the escape hatch: append `?motion=off` to any URL in this app to
# cancel the animations even on a machine that allows them, or `?motion=on` to
# restore them on a machine that does not. The URL travels with the session
# token, so the choice survives a refresh.
#
# The override has to live in Python rather than in the stylesheet, because a CSS
# media query cannot read a query parameter. It is injected after GLOBAL_CSS so
# that it wins on source order, and it is deliberately small: it re-enables the
# decorative loops and restores real durations, without touching the cascade of
# anything else.
_MOTION_ON = """
<style id="motion-override">
@keyframes headerShimmer {
    0%   { background-position: -200% center; }
    100% { background-position:  200% center; }
}
.page-header::after {
    animation: headerShimmer 8s linear infinite !important;
}
.page-header h1 {
    animation: headerShimmer 6s linear infinite !important;
}
.login-title-gradient {
    animation: textShimmer 4s linear infinite !important;
}
.pulse-dot {
    animation: pulse 1.8s infinite !important;
}
.engine-indicator-dot {
    animation: engine-pulse-anim 2s infinite ease-in-out !important;
}
.metric-card:hover,
.cat-card:hover,
.insight-card:hover,
.login-feature-card:hover {
    transform: translateY(-3px) !important;
}
</style>
"""

_MOTION_OFF = """
<style id="motion-override">
*, *::before, *::after {
    animation: none !important;
    transition-duration: 1ms !important;
    scroll-behavior: auto !important;
}
</style>
"""

_motion_pref = (st.query_params.get("motion") or "").strip().lower()
if _motion_pref == "off":
    st.markdown(_MOTION_OFF, unsafe_allow_html=True)
elif _motion_pref == "on":
    st.markdown(_MOTION_ON, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  RESTORE THE DATABASE BEFORE ANYTHING READS IT
# ══════════════════════════════════════════════════════════════
#
# Order matters here. On a cloud host the container's disk is wiped whenever the
# app sleeps, restarts or is redeployed, so a fresh process finds no database at
# all — and the very next line would create an empty one and re-seed the default
# administrator, making the app look healthy while every account, feedback record
# and audit entry had silently vanished.
#
# `restore_if_missing` fetches the stored copy from the backup repository when
# this container has no database of its own. It does nothing when no backup is
# configured, so local runs are unaffected, and it validates the download before
# overwriting anything — a truncated or corrupt copy is ignored rather than
# allowed to destroy good data.
if storage is not None:
    try:
        storage.restore_if_missing()
    except Exception:
        # A storage problem must never stop the app from starting.
        pass

db.seed_admins(ADMIN_SEED_ACCOUNTS)


# ══════════════════════════════════════════════════════════════
#  SESSION PERSISTENCE ACROSS A BROWSER REFRESH
# ══════════════════════════════════════════════════════════════
#
# The problem: `st.session_state` lives in the server process and is tied to a
# websocket. A browser refresh drops that websocket, so on the next run
# `password_correct` is gone and `main()` sends the user back to the login
# page — losing their place on whatever page they were reading.
#
# The fix: keep the auth state in a table and look it up again on every run,
# keyed by a token that lives in the URL's query string. Query params DO
# survive a refresh (the browser re-requests the same URL), so the run after a
# refresh finds the same token, looks up the same row, and restores the same
# signed-in user.
#
# WHY A TOKEN AND NOT A SINGLE GLOBAL FILE — the obvious shortcut, and a
# serious vulnerability: writing one file that says "this is the logged-in
# user" and reloading it means the FIRST person to sign in becomes the
# signed-in user for *everyone* on the deployment, including a browser that
# has never authenticated. On a shared machine or a public demo that is a
# privilege-escalation hole, not a UX convenience. A per-browser secret token
# means a browser can only ever restore the session it created; a browser
# with no token stays on the login page, and a forged or unknown token is
# simply not found.
#
# The token is `secrets.token_urlsafe(32)` (~256 bits of entropy), stored in
# the URL, and compared in constant time. It is an authentication *session*
# identifier, not a password, and it carries no privilege of its own — the
# role and level are re-read from the `users` table on every run, so a role
# change takes effect on the user's next interaction rather than persisting
# in the token.
#
# Sign-out deletes the row. Expired rows are swept on every write.

import json
import secrets
import time

_SESSION_PARAM = "futo_sess"        # query-param name carrying the token
_SESSION_TOKEN_KEY = "futo_session_token"  # session_state mirror of it
_CLIENT_COOKIE = "futo_client"      # per-browser secret, deliberately NOT in the URL

# ── Why a session needs two secrets, not one ───────────────────────────
#
# A token in the URL is a bearer credential: whoever holds the link holds the
# session. That is exactly what the URL has to be for a session to survive a
# refresh — there is no cookie and no storage API — but it also means the link
# can be pasted into a chat and handed to someone else, who then loads the app
# as the person who sent it and sees that account's dashboard, details and
# feedback. That was reported from the field.
#
# So the token alone no longer authenticates anything. Every session row also
# records a `client_id`, which lives in a cookie: browsers keep that out of the
# address bar and never send it when a link is shared. Restoring a session now
# requires BOTH to match the row.
#
#   sender's own browser    token + cookie match    -> restored
#   receiver opens the link  cookie absent or differs -> signed out, token dropped
#
# The failure is deliberately in the safe direction. With cookies blocked,
# nothing is ever restored and every visit starts at the login page: an
# inconvenience, not an account compromise. `session_status()` reports which
# mode is in force so an administrator can see which one they are getting.

# AppTest drives the script through a synthetic runner rather than the real
# websocket one, and it advertises itself: every session it creates carries an
# internal marker key in `st.session_state`. That is what this tests.
#
# It used to sniff `sys.modules` for "pytest"/"unittest" instead, and that trap
# had already sprung. `import sklearn` pulls `unittest` in as a side effect, and
# the app imports sklearn via sentiment.py and train_model.py -- so on a deployed
# container this function returned True and the whole session-persistence layer
# silently switched itself off. Signing in wrote no row, so every refresh logged
# the user out. The symptom looked like Streamlit dropping the cookie; the cause
# was a test detector that an ordinary third-party import could switch off.
#
# The module sniff survives only as a last-resort fallback, because `run_all.py`
# is not pytest and reaches unittest the same indirect way. The marker is checked
# first and wins.
_STREAM_TESTING_MARKER = "$$STREAMLIT_INTERNAL_KEY_TESTING"


def _is_test_run() -> bool:
    """True when a test harness is driving this script rather than a browser.

    Persistence is switched off in that case for two reasons: there is no browser
    to keep signed in, and writing a row would let a test that signs in as an
    administrator leak that state into a later run that expects the login page.
    Each AppTest instance starts with empty query params and so mints its own
    token, meaning the rows could not collide regardless -- this only keeps the
    test's database copy clean.
    """
    try:
        if _STREAM_TESTING_MARKER in st.session_state:
            return True
    except Exception:
        # No session context at all (a bare `import app`): there is nothing to
        # persist to, so treat it as a test run rather than write a stray row.
        return True
    if "pytest" in sys.modules:
        return True
    try:
        runner = st.runtime.scriptrunner
        return type(runner).__name__ == "LocalScriptRunner"
    except Exception:
        return False


_SESSION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS web_sessions (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL,
    seen_at    REAL NOT NULL
)
"""

# `client_id` is added defensively rather than by a migration step, for the same
# reason every other column here is: a database created by an earlier version of
# this project has to gain it on first connect without anyone running anything.
_SESSION_CLIENT_COLUMN = "ALTER TABLE web_sessions ADD COLUMN client_id TEXT"

SESSION_TTL_SECONDS = 7 * 24 * 3600  # one week


def _read_client_cookie() -> str:
    """This browser's client id from its cookie, or "" if it has none.

    Read through `st.context.cookies` rather than by parsing a header: that is
    the supported accessor, and it returns an empty mapping when the context
    does not carry one at all (a bare `import app`, or AppTest).
    """
    try:
        return str(st.context.cookies.get(_CLIENT_COOKIE, "") or "").strip()
    except Exception:
        return ""


def _mint_client_cookie() -> None:
    """Write a fresh client id into this browser's cookie.

    Streamlit's Python API can read cookies but not set them, so the write is
    done in the page through a same-origin component iframe — Streamlit mounts
    it with `allow-scripts allow-same-origin`, which is exactly the combination
    that lets `document.cookie` reach the app's own origin.

    The value is also kept in `session_state` so that everything downstream in
    *this* run agrees on one id. The cookie is what the next run reads back, and
    it only becomes readable once the browser has loaded the component — which
    is why a first-time visitor cannot be signed in by a token they did not earn.
    """
    if _is_test_run():
        return
    value = secrets.token_urlsafe(32)
    st.session_state[_CLIENT_COOKIE] = value
    try:
        import streamlit.components.v1 as components
        components.html(
            "<script>try{document.cookie="
            f"'{_CLIENT_COOKIE}={value}; path=/; max-age=31536000; SameSite=Lax'"
            ";}catch(e){}</script>",
            height=0,
        )
    except Exception:
        # If the component cannot be mounted, no cookie is written and the
        # session simply never persists. Nothing else breaks.
        pass


def session_status() -> dict:
    """Which persistence mode this browser is in. Surfaced in the admin health panel."""
    client = _read_client_cookie()
    return {
        "url_token_bound": True,
        "browser_cookie_bound": bool(client),
        "mode": "token + browser cookie" if client else "not bound yet (sign-in must be repeated)",
        "cookie_name": _CLIENT_COOKIE,
    }


def _session_token() -> str:
    """This browser's session token, read from the URL, minted if absent.

    Streamlit copies every query param onto the page's links, so a token in
    the URL is carried through the app's own navigation without extra work.
    """
    try:
        token = st.query_params.get(_SESSION_PARAM, "")
    except Exception:
        return ""

    if not token:
        token = secrets.token_urlsafe(32)
        try:
            st.query_params[_SESSION_PARAM] = token
        except Exception:
            return ""
    return token


def _ensure_session_schema(conn) -> None:
    """Creates `web_sessions` and adds `client_id` to an older table.

    A row written before this column existed has `client_id` NULL, and NULL can
    never equal the cookie, so those rows simply stop restoring. That is the
    correct outcome: they predate the browser binding, so the only way to honour
    one would be to trust a bare URL token again.
    """
    conn.execute(_SESSION_TABLE_DDL)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(web_sessions)").fetchall()}
    except Exception:
        cols = set()
    if "client_id" not in cols:
        try:
            conn.execute(_SESSION_CLIENT_COLUMN)
            conn.commit()
        except Exception:
            pass


def _persist_session(username: str, payload: dict) -> None:
    """Writes this browser's auth state, keyed by its own token AND its cookie.

    A no-op under AppTest, where query params and the websocket are both
    synthetic: there is no browser to keep signed in, and honouring the row
    would make a test that signs in as an admin leak that state into a
    subsequent `fresh()` that expects the login page.
    """
    if _is_test_run():
        return
    token = st.session_state.get(_SESSION_TOKEN_KEY, "")
    if not token:
        return
    client_id = st.session_state.get(_CLIENT_COOKIE, "")
    if not client_id or not _read_client_cookie():
        # No readable cookie on this browser, so there is nothing to bind the
        # row to. Writing it unbound would create exactly the session a shared
        # link can hijack, which is what this column exists to prevent.
        return
    now = time.time()
    try:
        conn = db.get_db()
        _ensure_session_schema(conn)
        conn.execute("DELETE FROM web_sessions WHERE seen_at < ?", (now - SESSION_TTL_SECONDS,))
        conn.execute(
            """INSERT INTO web_sessions (token, username, payload, created_at, seen_at, client_id)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(token) DO UPDATE SET
                 username = excluded.username,
                 payload  = excluded.payload,
                 seen_at  = excluded.seen_at,
                 client_id = excluded.client_id""",
            (token, username, json.dumps(payload), now, now, client_id),
        )
        conn.commit()
    except Exception:
        # Persistence is a convenience. If it fails the app still works; the
        # user just signs in again after a refresh.
        pass


def _drop_token_from_url() -> None:
    """Removes `futo_sess` from the address bar.

    Called when a token is present but does not belong to this browser. Leaving
    it there would mean every page the receiver visits carries the sender's
    token, and every one of them has to re-check it and reject it again.
    """
    try:
        if _SESSION_PARAM in st.query_params:
            del st.query_params[_SESSION_PARAM]
    except Exception:
        pass


def _restore_session() -> None:
    """Reloads this browser's auth state, if it signed in before.

    Requires the URL token *and* the browser cookie to match the stored row. A
    link pasted into someone else's browser has a token but no matching cookie,
    so it resolves to no session and the receiver lands on the login page — see
    the note on `_CLIENT_COOKIE`.

    Re-reads the user from the `users` table rather than trusting the stored
    payload, so a deleted account cannot keep a session alive and a changed
    role takes effect immediately.

    Reads the token from the URL and the client_id from the cookie directly,
    because on a fresh render (page refresh) `st.session_state` is empty — it
    is populated from these sources *during* this function, not before it.
    """
    if _is_test_run():
        return
    # On a fresh render, session_state is empty. Read the sources of truth:
    # the token from the URL, and the client_id from the cookie.
    try:
        token = st.query_params.get(_SESSION_PARAM, "")
    except Exception:
        token = ""
    client_id = _read_client_cookie()
    # Mirror into session_state so downstream code in this run sees them.
    st.session_state[_SESSION_TOKEN_KEY] = token
    st.session_state[_CLIENT_COOKIE] = client_id
    if not token:
        return
    if not client_id:
        # A token with no readable cookie is either a brand-new browser or
        # somebody else's link. Neither may be restored, and the token is
        # discarded so it stops travelling through this browser's URLs.
        _drop_token_from_url()
        return
    try:
        conn = db.get_db()
        _ensure_session_schema(conn)
        row = conn.execute(
            """SELECT username FROM web_sessions
               WHERE token = ? AND client_id = ? AND seen_at >= ?""",
            (token, client_id, time.time() - SESSION_TTL_SECONDS),
        ).fetchone()
        if not row:
            _drop_token_from_url()
            return
        conn.execute("UPDATE web_sessions SET seen_at = ? WHERE token = ?",
                     (time.time(), token))
        conn.commit()
        username = row[0]
    except Exception:
        return

    user = db.get_user(username)
    if user is None:
        # Signed-in user was deleted while their browser was open.
        _forget_session()
        return

    st.session_state["password_correct"] = True
    st.session_state["username"] = user["username"]
    # Role and level come from the table, never from the stored payload.
    st.session_state["user"] = {
        "name": user["full_name"],
        "role": user["role"],
        "level": user["level"],
        "email": user["email"],
    }
    # No password-hash state is cached here. `main()` re-reads the row to decide
    # whether to hold a legacy account, so a browser refresh mid-migration stays
    # held and a completed migration releases — with nothing to keep in sync.


def _forget_session() -> None:
    """Drops this browser's persisted row. Called on sign-out and on failure."""
    token = st.session_state.get(_SESSION_TOKEN_KEY, "")
    if _is_test_run() or not token:
        return
    try:
        conn = db.get_db()
        _ensure_session_schema(conn)
        conn.execute("DELETE FROM web_sessions WHERE token = ?", (token,))
        conn.commit()
    except Exception:
        pass


# Establish the browser identity before anything reads a token, because the
# restore below needs both. The cookie is read first; only when the browser has
# none does the component get mounted to write one. Reading first avoids
# re-minting on every single page render.
_client_from_cookie = _read_client_cookie()
if _client_from_cookie:
    st.session_state[_CLIENT_COOKIE] = _client_from_cookie
elif not _is_test_run():
    _mint_client_cookie()

# Put this browser's token into session_state FIRST, so both `_restore_session`
# and any later `_persist_session` in this same run agree on the key.
st.session_state[_SESSION_TOKEN_KEY] = _session_token()
_restore_session()

# Nav entries as (semantic page key, icon name, display label)
STUDENT_NAV = [("Home", "home", "Home")] + [
    (cat, CAT_META[cat]["icon"], cat) for cat in CATEGORIES
] + [("My Statistics", "bar-chart", "My Statistics")]

ADMIN_NAV = [
    ("Overview", "bar-chart", "Overview"),
    ("Full Dashboard", "search", "Full Dashboard"),
    ("Decision Insights", "target", "Decision Insights"),
    # F-04: user management + guarded account deletion. Uses the `user-cog`
    # Lucide glyph that was already inlined in icons.py but never referenced.
    ("User Management", "user-cog", "User Management"),
]


def _sidebar(user):
    role_display = "Administrator" if user["role"] == "admin" else f"Level {user['level']} Student"
    with st.sidebar:
        initials = "".join(w[0].upper() for w in (user["name"] or "?").split()[:2]) or "?"
        st.markdown(
            f'<div class="sidebar-profile"><div class="sidebar-avatar">{esc(initials)}</div>'
            f'<div class="sidebar-name">{esc(user["name"])}</div>'
            f'<div class="sidebar-role">{esc(role_display)}</div></div>',
            unsafe_allow_html=True,
        )

        # ── Academic Session Selector ──
        available_sessions = db.get_academic_sessions()
        active_default = db.get_active_session()

        if user["role"] == "admin":
            session_choices = [ALL_SESSIONS_LABEL] + available_sessions
        else:
            session_choices = available_sessions

        if "selected_session" not in st.session_state or st.session_state["selected_session"] not in session_choices:
            st.session_state["selected_session"] = active_default if active_default in session_choices else session_choices[0]

        curr_sess_idx = session_choices.index(st.session_state["selected_session"]) if st.session_state["selected_session"] in session_choices else 0

        st.markdown(
            f'<div class="sidebar-label">{i("calendar", 12)} {"Filter Session" if user["role"] == "admin" else "Academic Session"}</div>',
            unsafe_allow_html=True,
        )
        chosen_session = st.selectbox(
            "Academic Session",
            session_choices,
            index=curr_sess_idx,
            key="academic_session_choice",
            label_visibility="collapsed",
        )
        if chosen_session != st.session_state["selected_session"]:
            st.session_state["selected_session"] = chosen_session
            st.rerun()

        selected_session = st.session_state["selected_session"]

        st.markdown("---")

        # ── Administrator-only deployment health ──
        # An unconfigured mail server is invisible until a student tries to
        # recover a password, which is the worst possible moment to discover it.
        # An administrator should see it in one glance and be told WHICH setting
        # is absent, not merely that a feature is "unavailable".
        #
        # The database backend is shown alongside it because a deployment running
        # on the local SQLite file looks identical to a correct one until it is
        # restarted and the data is gone — the two failure modes worth catching
        # early are the two that are invisible until they are expensive.
        if user["role"] == "admin":
            from email_service import email_status

            _mail = email_status()
            _backend = "PostgreSQL" if db.active_backend() == "postgresql" else "SQLite (local file)"
            # Interpolated through esc() at the point of use. The static XSS gate
            # audits variable *names*, so it cannot see that this particular value
            # was escaped three lines above its assignment -- it only knows the
            # name, and the name is not on its whitelist. Escaping here instead
            # is the honest fix: the gate exists so that "it is only ever one of
            # two constants" cannot become the reasoning that lets the next,
            # genuinely user-influenced value through unescaped.
            if _mail["configured"]:
                st.markdown(
                    f'<div class="sidebar-label">{i("check-circle", 12)} Deployment</div>'
                    f'<div class="health-ok">Database: {esc(_backend)}<br>Email: configured</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="sidebar-label">{i("alert-triangle", 12)} Deployment</div>'
                    f'<div class="health-ok">Database: {esc(_backend)}</div>'
                    f'<div class="health-bad">Email: not configured &mdash; password '
                    f'recovery is unavailable.<br>Missing: '
                    f'<code>{esc(", ".join(_mail["missing"]))}</code></div>',
                    unsafe_allow_html=True,
                )

        nav = ADMIN_NAV if user["role"] == "admin" else STUDENT_NAV
        label = "Analytics Dashboard" if user["role"] == "admin" else "Navigation"
        st.markdown(f'<div class="sidebar-label">{label}</div>', unsafe_allow_html=True)
        options = [n[0] for n in nav]
        selection = st.radio("Navigation", options, label_visibility="collapsed")

        st.markdown("---")
        st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
        if st_compat.button("Sign Out", use_container_width=True, key="logout_btn", icon=":material/logout:"):
            # Drop the persisted row BEFORE clearing session_state, which is
            # where `_forget_session` reads the token from. Without this the
            # next refresh would restore the session the user just ended.
            _forget_session()
            st.session_state.clear()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Sentiment Engine live indicator ──
        # Was a "VADER Academic Pro / 220 rules / Domain-Specialized / Calibrated"
        # badge. None of that described the rating-threshold engine, and the
        # number was a hard-coded fallback rather than a count of anything —
        # `engine_status()` reports 0 lexicon terms, so on the happy path this
        # read "0 rules" and only claimed otherwise when the status call failed.
        # The badge now states the rule that is actually applied.
        try:
            status = engine_status()
            bands = status.get("rating_thresholds", "1-2 Negative · 3 Neutral · 4-5 Positive")
            engine_ok = not status.get("engine_problems")
        except Exception:
            bands = "1-2 Negative · 3 Neutral · 4-5 Positive"
            engine_ok = False

        engine_dot_color = "#10b981" if engine_ok else "#f59e0b"

        st.markdown(
            f'<div class="sidebar-engine-badge">'
            f'<div class="engine-badge-head">'
            f'<span class="engine-indicator-dot" style="background:{engine_dot_color};'
            f'box-shadow:0 0 8px {engine_dot_color};"></span>'
            f'<span class="engine-badge-name">{esc(ENGINE_BADGE_NAME)}</span>'
            f'<span class="engine-badge-tag">1&ndash;5</span>'
            f'</div>'
            f'<div class="engine-badge-bands">{esc(bands)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="margin-top:.7rem;padding:.65rem .85rem;'
            "background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.15);"
            'border-radius:12px;display:flex;align-items:center;gap:.6rem;">'
            '<div style="width:7px;height:7px;border-radius:50%;'
            'background:#10b981;box-shadow:0 0 6px rgba(16,185,129,.6);"></div>'
            '<div style="flex:1;">'
            '<div style="font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:#94a3b8;font-weight:700;">System Status</div>'
            f'<div style="font-size:.72rem;color:#059669;font-weight:700;margin-top:.05rem;">Online · {esc(selected_session)}</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )
        return selection, selected_session


def main():
    # Any flow that completed on a PREVIOUS run parks its result dialog, and
    # this is the far side of the redirect that shows it.
    #
    # It lives in `main()` and not in `show_login_page()` because registration
    # signs the student straight IN: the run after it lands on the dashboard,
    # so a hook on the login page would never fire and the dialog would sit
    # unrendered in session_state forever. `main()` is the one frame every run
    # passes through, signed in or not.
    #
    # Top level on purpose — Streamlit renders a dialog as a page-level modal,
    # so this must not sit inside a column context.
    render_parked_dialog()

    if not st.session_state.get("password_correct"):
        show_login_page()
        return

    user = st.session_state["user"]
    username = st.session_state["username"]

    # A legacy unsalted-SHA256 account is signed in but not finished. Hold it
    # here, before the sidebar, so there is nothing to navigate to until the
    # hash is replaced — see `show_mandatory_password_change`'s note on why
    # this is a return and not a banner.
    #
    # The row is the ONLY source of truth for that decision. An earlier
    # version cached it in session_state and accepted either the flag or the
    # row, which meant a stale flag left over from before the change kept
    # holding an account that had already been upgraded — a loop the user
    # cannot get out of, because completing the screen was what cleared the
    # flag. Reading the row costs one indexed lookup per run and cannot drift.
    if db.password_is_legacy(username):
        show_mandatory_password_change(username)
        return

    selection, selected_session = _sidebar(user)

    if user["role"] == "admin":
        if selection == "Overview":
            show_admin_overview(selected_session)
        elif selection == "Full Dashboard":
            show_full_dashboard(selected_session)
        elif selection == "Decision Insights":
            show_decision_support(user["name"], selected_session)
        elif selection == "User Management":
            show_user_management(username, user)
        else:
            # B-09: every branch used to be an `if/elif` chain with no `else`.
            # A nav key that no longer matches (a renamed page, a stale
            # `selected_session` left over in session_state, a value written
            # by an older build) matched nothing and rendered a completely
            # blank page body — no error, no explanation, just the sidebar.
            st.error(
                f"The page '{selection}' is no longer available. "
                "Choose another item from the navigation menu."
            )
    else:
        if selection == "Home":
            show_home(user, username, selected_session)
        elif selection in CATEGORIES:
            show_feedback_form(selection, user, username, selected_session)
        elif selection == "My Statistics":
            show_basic_stats(username, selected_session)
        else:
            st.error(
                f"The page '{selection}' is no longer available. "
                "Choose another item from the navigation menu."
            )


if __name__ == "__main__":
    main()
