"""
app_pages/login.py
--------------
Three views live behind the role toggle: **Sign In**, **Create Account**
(students only), and **Forgot Password** (both roles). All account data
is read from/written to the real `users` table (db.py) — there is no
more hardcoded demo dictionary; every student registers their own unique
username, email, and password, and can recover a forgotten password via
an emailed one-time code.

STUDENT gets the full marketing/onboarding experience (branding, feature
list, live stats). ADMIN gets a deliberately plain, centered card — see
the module-level rationale in the previous version of this file, unchanged.
"""

import time
from datetime import datetime

import streamlit as st

import db
import st_compat
from auth import authenticate, authenticate_by_email, validate_registration, check_lockout, register_failed_attempt, clear_attempts
from config import CATEGORIES, OTP_EXPIRY_MINUTES
from email_service import (
    is_email_configured,
    send_registration_email,
    send_otp_email,
    send_password_changed_email,
    show_otp_on_screen,
    email_status_report,
)
from icons import i
from components import esc, html_alert, park_result_dialog

FEATURES = [
    ("bar-chart", "rgba(59,130,246,.12)", "#2563eb", "Real-time Analytics", "Live dashboards, trend charts & sentiment analysis"),
    # Was "VADER Academic Pro · 220+ domain rules & calibrated confidence", which
    # described a lexicon analyser that no longer exists. The claim now made is
    # the one that can be checked: the rating decides the band, and everyone
    # sees the same band for the same rating.
    ("chart-bar", "rgba(139,92,246,.12)", "#7c3aed", "Rating-Based Analysis", "Sentiment is derived from the 1&ndash;5 rating &mdash; one rule, the same for every submission"),
    ("target", "rgba(6,182,212,.12)", "#0891b2", "Decision Support", "Surfaces priority areas requiring departmental action"),
    ("shield-check", "rgba(16,185,129,.12)", "#059669", "Secure & Confidential", "All submissions are encrypted and anonymised"),
]


def _hide_sidebar():
    """Removes the sidebar and BOTH of its toggle buttons on the portal.

    The second selector matters as much as the first: hiding only
    `section[data-testid="stSidebar"]` while leaving the fixed-position
    expand button in the header would leave a floating blue button in the
    top-left corner that opens a sidebar the user can then never close.

    The test-ids are Streamlit 1.64's (`stExpandSidebarButton` /
    `stSidebarCollapseButton`). `collapsedControl`, which this used to name,
    no longer exists — so the rule silently did nothing and the button was
    still there.
    """
    st.markdown(
        """<style>
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"] { display: none !important; }
        </style>""",
        unsafe_allow_html=True,
    )


def _role_switch() -> str:
    """Renders the Student / Administrator portal selector.

    This used to be wrapped in `<div class="role-switch-container"> … </div>`
    emitted as two separate markdown calls. Streamlit sanitises and re-parses
    each `st.markdown` block independently, so the closing tag landed in a
    different container and the wrapper never formed — every rule under
    `.role-switch-container` in styles.py was dead. Styling the radio's own
    test-id through `st_compat.segmented_control` cannot fail that way, and on
    Streamlit >= 1.40 it renders as a proper segmented pill toggle.
    """
    choice = st_compat.segmented_control(
        "Select Portal",
        ["Student Portal", "Administrator"],
        default="Student Portal",
        key="login_role_choice",
    )
    return "student" if "Student" in (choice or "Student Portal") else "admin"


def _go(view: str):
    st.session_state["login_view"] = view
    st.rerun()


def _establish_session(user: dict):
    """Marks the browser signed in and records it so a page refresh survives.

    Called by both sign-in paths. The user row is the single source of truth:
    `_restore_session` re-reads it on every run after a refresh, so a role
    change or a deleted account takes effect immediately rather than being
    pinned by whatever was cached in the browser's URL token.
    """
    st.session_state["password_correct"] = True
    st.session_state["username"] = user["username"]
    st.session_state["user"] = {
        "name": user["full_name"],
        "role": user["role"],
        "level": user["level"],
        "email": user["email"],
    }
    st.session_state["login_view"] = "signin"

    # No "must change your password" flag is set here on purpose. An earlier
    # version cached the decision in session_state and `main()` honoured either
    # the flag or the row — which meant a stale flag could trap an account that
    # had already been upgraded. The row is the only source of truth; see
    # `app.main()`. The user's row is already in hand here, so the one query it
    # costs is cheaper than a second source of truth to keep in sync.

    # Imported lazily: app.py imports this module, so a top-level import here
    # would be circular.
    import app as _app
    _app._persist_session(user["username"], {"t": time.time()})


def _do_login(username, password, role_hint):
    """Admin login via username (unchanged)."""
    remaining = check_lockout(st.session_state)
    if remaining > 0:
        st.error(f"Account temporarily locked. Please try again in {int(remaining)} seconds.")
        return

    username_clean = (username or "").strip()
    if not username_clean or not password:
        st.error("Please enter your username and password to continue.")
        return

    success, role = authenticate(username_clean, password)
    if not success:
        register_failed_attempt(st.session_state)
        st.error("The credentials provided are incorrect. Please verify and try again.")
        return

    expected_role = "student" if role_hint == "student" else "admin"
    if role != expected_role:
        st.error(
            f"This account is registered under the '{role}' role. "
            "Please select the correct role above and try again."
        )
        return

    clear_attempts(st.session_state)
    user = db.get_user(username_clean)
    _establish_session(user)
    st.rerun()


def _do_login_by_email(email, password):
    """Student login via registered email address."""
    remaining = check_lockout(st.session_state)
    if remaining > 0:
        st.error(f"Account temporarily locked. Please try again in {int(remaining)} seconds.")
        return

    email_clean = (email or "").strip().lower()
    if not email_clean or not password:
        st.error("Please enter your email address and password to continue.")
        return

    # Check whether the email is registered at all, so the error message can
    # tell the user whether to register or to re-check their password.
    existing = db.get_user_by_email(email_clean)
    if existing is None:
        st.error(
            "This email address is not registered. "
            "Please create an account to get started."
        )
        return

    success, role, user = authenticate_by_email(email_clean, password)
    if not success:
        register_failed_attempt(st.session_state)
        st.error("Your login credentials are incorrect. Please check your email and password, then try again.")
        return

    if role != "student":
        st.error(
            "This portal is designated for student access only. "
            "Please use the Administrator sign-in option."
        )
        return

    clear_attempts(st.session_state)
    _establish_session(user)
    st.rerun()


# ══════════════════════════════════════════════════════════════
#  SIGN IN
# ══════════════════════════════════════════════════════════════

def _top_rated_course() -> str:
    """Short course code with the highest average rating, or "—" if none.

    Read live from Course Content submissions (all sessions — the tile names
    no session, so the aggregate is the honest scope), combining levels by
    response-weighted average and breaking ties by response count. A preview
    tile showing a hardcoded course would be caught by the first examiner who
    compares it with the dashboard; this way the two can never disagree.
    Anything unreadable (empty table, bad rows, a down database) degrades to
    the em dash rather than taking the login page with it.
    """
    import re

    try:
        rows = db.course_summary()
    except Exception:
        return "—"
    combined: dict[str, list[float]] = {}
    for entry in rows or []:
        name = str((entry or {}).get("course") or "").strip()
        if not name:
            continue
        try:
            avg = float(entry.get("avg_rating"))
            n = int(entry.get("responses") or 0)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        slot = combined.setdefault(name, [0.0, 0])
        slot[0] += avg * n
        slot[1] += n
    best, best_avg, best_n = "", -1.0, -1
    for name, (weighted, n) in combined.items():
        avg = weighted / n
        if (avg, n) > (best_avg, best_n):
            best, best_avg, best_n = name, avg, n
    if not best:
        return "—"
    return re.split(r"\s+[–—-]\s+", best, maxsplit=1)[0].strip() or "—"


def _show_student_signin():
    left_col, right_col = st.columns([1.2, 0.8], gap="large")

    # A message parked by another view (e.g. "Account created successfully")
    # survives the st.rerun() that the redirect performs, which a direct
    # st.success() call could never do.
    flash = st.session_state.pop("flash_message", None)
    if flash:
        getattr(st, st.session_state.pop("flash_kind", "success"))(flash)

    with left_col:
        st.markdown('<div style="padding:1rem 0.5rem;">', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-hero">'
            f'<div class="login-logo">{i("graduation-cap", 36, "#ffffff")}</div>'
            '<h1 class="login-title">'
            '<span class="login-title-dark">Smart Feedback &amp;</span><br>'
            '<span class="login-title-gradient">Sentiment Intelligence</span>'
            '</h1>'
            '</div>',
            unsafe_allow_html=True,
        )
        # The scroll hint rides along with the subtitle because that is the last
        # thing on screen before the feature grid. It is `display: none` on
        # desktop — where the login form sits beside this column and there is
        # nothing to scroll to — and only revealed by the phone breakpoint.
        st.markdown(
            '<p class="login-subtitle">Empowering FUTO IFT students with intelligent, transparent feedback channels. '
            'Submissions are analyzed in real time by domain-specialized AI to drive actionable departmental improvements.</p>'
            '<div class="login-scroll-hint">'
            f'{i("chevron-down", 16, "#2563eb")}'
            '<span>Scroll down to access the login form</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        feature_cards = "".join(
            f'<div class="login-feature-card">'
            f'<div class="login-feature-icon" style="background:{bg};">{i(icon_name, 19, color)}</div>'
            f'<div class="login-feature-title">{title}</div>'
            f'<div class="login-feature-desc">{desc}</div></div>'
            for icon_name, bg, color, title, desc in FEATURES
        )
        st.markdown(f'<div class="login-feature-grid">{feature_cards}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-stats-bar">'
            f'<div class="login-stat-item"><div class="login-stat-value">{len(CATEGORIES)}</div><div class="login-stat-label">Categories</div></div>'
            '<div class="login-stat-item"><div class="login-stat-value" style="color:#0891b2;">1&ndash;5</div><div class="login-stat-label">Rating Scale</div></div>'
            '<div class="login-stat-item"><div class="login-stat-value" style="color:#059669;">100%</div><div class="login-stat-label">Secure</div></div>'
            '<div class="login-stat-item"><div class="login-stat-value" style="color:#7c3aed;">Live</div><div class="login-stat-label">Analytics</div></div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        # The preview mirrors live system data, not demo text: the top course
        # is read from actual submissions just above, and escaped at the point
        # of interpolation like every other database string in HTML.
        _top_course = _top_rated_course()
        st.markdown(
            '<div class="login-form-header"><div class="login-form-header-bar"></div>'
            '<div class="login-form-header-tag">STUDENT PORTAL</div>'
            '<h2>Welcome back</h2>'
            '<div class="login-preview-card">'
            '<!-- Tile 1: Rating Distribution Bar Chart -->'
            '<div class="login-preview-tile">'
            '<div class="preview-tile-title">Rating Distribution</div>'
            '<svg viewBox="0 0 200 100" class="preview-chart-svg" preserveAspectRatio="none">'
            '<defs>'
            '<linearGradient id="barGrad1" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#f87171"/>'
            '<stop offset="100%" stop-color="#ef4444"/>'
            '</linearGradient>'
            '<linearGradient id="barGrad2" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#fb923c"/>'
            '<stop offset="100%" stop-color="#f97316"/>'
            '</linearGradient>'
            '<linearGradient id="barGrad3" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#fbbf24"/>'
            '<stop offset="100%" stop-color="#f59e0b"/>'
            '</linearGradient>'
            '<linearGradient id="barGrad4" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#4ade80"/>'
            '<stop offset="100%" stop-color="#22c55e"/>'
            '</linearGradient>'
            '<linearGradient id="barGrad5" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#34d399"/>'
            '<stop offset="100%" stop-color="#10b981"/>'
            '</linearGradient>'
            '</defs>'
            '<text x="6" y="19" font-size="6.5" fill="#94a3b8" font-family="Sora, sans-serif">100</text>'
            '<line x1="22" y1="17" x2="195" y2="17" stroke="#f1f5f9" stroke-width="1"/>'
            '<text x="9" y="42" font-size="6.5" fill="#94a3b8" font-family="Sora, sans-serif">60</text>'
            '<line x1="22" y1="40" x2="195" y2="40" stroke="#f1f5f9" stroke-width="1"/>'
            '<text x="9" y="65" font-size="6.5" fill="#94a3b8" font-family="Sora, sans-serif">20</text>'
            '<line x1="22" y1="63" x2="195" y2="63" stroke="#f1f5f9" stroke-width="1"/>'
            '<text x="13" y="87" font-size="6.5" fill="#94a3b8" font-family="Sora, sans-serif">0</text>'
            '<line x1="22" y1="85" x2="195" y2="85" stroke="#e2e8f0" stroke-width="1"/>'
            '<rect x="32" y="72" width="22" height="13" rx="3" fill="url(#barGrad1)"/>'
            '<rect x="66" y="62" width="22" height="23" rx="3" fill="url(#barGrad2)"/>'
            '<rect x="100" y="48" width="22" height="37" rx="3" fill="url(#barGrad3)"/>'
            '<rect x="134" y="30" width="22" height="55" rx="3" fill="url(#barGrad4)"/>'
            '<rect x="168" y="17" width="22" height="68" rx="3" fill="url(#barGrad5)"/>'
            '<text x="43" y="95" text-anchor="middle" font-size="6.5" font-weight="700" fill="#64748b" font-family="Sora, sans-serif">1★</text>'
            '<text x="77" y="95" text-anchor="middle" font-size="6.5" font-weight="700" fill="#64748b" font-family="Sora, sans-serif">2★</text>'
            '<text x="111" y="95" text-anchor="middle" font-size="6.5" font-weight="700" fill="#64748b" font-family="Sora, sans-serif">3★</text>'
            '<text x="145" y="95" text-anchor="middle" font-size="6.5" font-weight="700" fill="#64748b" font-family="Sora, sans-serif">4★</text>'
            '<text x="179" y="95" text-anchor="middle" font-size="6.5" font-weight="700" fill="#64748b" font-family="Sora, sans-serif">5★</text>'
            '</svg>'
            '</div>'
            '<!-- Tile 2: Sentiment Analysis -->'
            '<div class="login-preview-tile" style="text-align:center;">'
            '<div class="preview-tile-title" style="text-align:left;">Sentiment Analysis</div>'
            '<div class="sentiment-donut-wrap">'
            '<div class="sentiment-donut-pie">'
            '<div class="sentiment-donut-hole"></div>'
            '</div>'
            '</div>'
            '<div class="sentiment-legend">'
            '<span class="legend-item"><span class="legend-dot dot-green"></span>Positive</span>'
            '<span class="legend-item"><span class="legend-dot dot-amber"></span>Neutral</span>'
            '<span class="legend-item"><span class="legend-dot dot-red"></span>Negative</span>'
            '</div>'
            '</div>'
            '<!-- Tile 3: Stacked Stat Cards -->'
            '<div class="preview-stat-col">'
            '<div class="preview-stat-card">'
            '<div class="preview-stat-icon icon-purple">'
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>'
            '</div>'
            '<div>'
            '<div class="preview-stat-value">88%</div>'
            '<div class="preview-stat-label">Positive Sentiment</div>'
            '</div>'
            '</div>'
            '<div class="preview-stat-card preview-stat-card-topcourse">'
            '<div class="preview-stat-header">Top Course</div>'
            '<div class="preview-stat-body">'
            '<div class="preview-stat-icon icon-green">'
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>'
            '</div>'
            '<div>'
            f'<div class="preview-stat-value">{esc(_top_course)}</div>'
            '<div class="preview-stat-label">Highest Rated</div>'
            '</div>'
            '</div>'
            '</div>'
            '</div>'
            '</div>'
            '<p>Enter your registered email address and password to access your feedback dashboard.</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("student_login_form", clear_on_submit=False):
            st.markdown(f"**{i('mail', 14)} Account Credentials**", unsafe_allow_html=True)
            email = st.text_input("Email Address", placeholder="Your registered email address")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st_compat.form_submit_button("Sign In →", use_container_width=True, type="primary")
            if submitted:
                _do_login_by_email(email, password)

        link_col1, link_col2 = st_compat.columns(2, vertical_alignment="top")
        with link_col1:
            if st_compat.button("Create an Account", use_container_width=True, icon=":material/person_add:", type="primary"):
                _go("register")
        with link_col2:
            if st_compat.button("Forgot Password?", use_container_width=True, icon=":material/lock_reset:", type="primary"):
                _go("forgot_request")

        st.markdown(
            f'<div class="login-footer">Federal University of Technology, Owerri &nbsp;&middot;&nbsp; '
            f'Department of Information Technology &nbsp;&middot;&nbsp; &copy; {datetime.now().year}</div>',
            unsafe_allow_html=True,
        )


def _show_admin_signin():
    """Deliberately minimal — no branding panel, no feature list.
    Admin authentication relies solely on username and password."""
    st.markdown("<div class='admin-login-shell'>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown(
            '<div class="admin-login-card">'
            f'<div class="admin-login-icon">{i("shield-check", 24, "#475569")}</div>'
            '<div class="admin-login-title">Administrator Sign-In</div>'
            '<div class="admin-login-subtitle">Restricted access &mdash; IFT Department authorised personnel only</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Administrator username")
            password = st.text_input("Password", type="password", placeholder="Administrator password")
            submitted = st_compat.form_submit_button("Sign In", use_container_width=True, type="primary")
            if submitted:
                _do_login(username, password, "admin")

        if st_compat.button("Forgot Password?", use_container_width=True, icon=":material/lock_reset:", type="primary"):
            _go("forgot_request")

        st.markdown(
            '<div class="login-footer" style="margin-top:1rem;">'
            f'{i("lock", 10)} Contact IFT Support to request or restore administrator access.</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  CREATE ACCOUNT (students only)
# ══════════════════════════════════════════════════════════════

def _show_register():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(
            '<div class="login-form-header"><div class="login-form-header-bar"></div>'
            '<div class="login-form-header-tag">Student Portal</div>'
            f"<h2>{i('user', 20)} Create Your Account</h2>"
            "<p>Each student is issued a unique, personal login. Shared credentials are not permitted.</p></div>",
            unsafe_allow_html=True,
        )
        with st.form("register_form"):
            full_name = st.text_input("Full Name", placeholder="Your full legal name")
            username = st.text_input("Choose a Username", placeholder="e.g. chidera.okafor",
                                     help="4–32 characters: letters, numbers, dots, dashes, or underscores.")
            email = st.text_input("Email Address", placeholder="you@example.com",
                                   help="Used for password recovery and submission confirmations.")
            level = st.selectbox("Academic Level", ["100 Level", "200 Level", "300 Level", "400 Level", "500 Level"])
            password = st.text_input("Password", type="password", placeholder="Minimum 8 characters")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password")
            submitted = st_compat.form_submit_button("Create Account →", use_container_width=True, type="primary")

            if submitted:
                problems = validate_registration(username, email, full_name, password, confirm_password)
                if problems:
                    for p in problems:
                        st.error(p)
                else:
                    username_clean = username.strip()
                    email_clean = email.strip().lower()
                    level_val = level.replace(" Level", "")

                    # create_user() can still fail on a uniqueness race — two
                    # people registering the same username, or a half-finished
                    # earlier attempt. It used to be called with its return
                    # value discarded, so a collision logged the user straight
                    # into a session that did not exist and showed a green
                    # "Account created successfully" on the next screen.
                    created, error = db.create_user(
                        username_clean, email_clean, full_name.strip(),
                        password, "student", level_val,
                    )
                    if not created:
                        st.error(error or "The account could not be created. Please try again.")
                        return

                    if is_email_configured():
                        send_registration_email(email_clean, full_name.strip(), username_clean)

                    st.session_state["password_correct"] = True
                    st.session_state["username"] = username_clean
                    st.session_state["user"] = {
                        "name": full_name.strip(), "role": "student",
                        "level": level_val, "email": email_clean,
                    }
                    # Persist this sign-in exactly like a password sign-in does.
                    # These keys alone keep the user signed in only until the
                    # next refresh; without a `web_sessions` row the run after
                    # a refresh finds no token to restore and drops the user on
                    # the login page. `_establish_session` writes that row (and
                    # sets the same keys), so a freshly registered student
                    # survives a refresh the same way a returning one does. It
                    # is a no-op where there is nothing to bind yet — same as
                    # the sign-in path — never a failure.
                    import app as _app_reg
                    _app_reg._persist_session(username_clean, {"t": time.time()})
                    # Parked, not rendered here: anything queued on this run is
                    # discarded by the rerun, so a dialog (or st.success) opened
                    # now would flash and vanish. `render_parked_dialog()` in
                    # show_login_page() shows it on the far side of the redirect.
                    park_result_dialog(
                        "Your student account has been created and you are now "
                        "signed in. Welcome to the FUTO IFT Feedback System.",
                        kind="success",
                        title="Registration Complete",
                        details=(
                            f"Username: {username_clean}  ·  "
                            f"Email: {email_clean}  ·  Level: {level_val}"
                        ),
                        button_label="Start Using the System",
                    )
                    _go("signin")

        if st_compat.button("← Return to Sign In", use_container_width=True):
            _go("signin")


# ══════════════════════════════════════════════════════════════
#  FORGOT PASSWORD (both roles)
# ══════════════════════════════════════════════════════════════

def _show_forgot_request():
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown(
            '<div class="login-form-header"><div class="login-form-header-bar"></div>'
            '<div class="login-form-header-tag">Account Recovery</div>'
            '<h2>Password Recovery</h2>'
            '<p>Enter the email address associated with your account. '
            'A one-time reset code will be dispatched to your inbox.</p></div>',
            unsafe_allow_html=True,
        )

        # Two-phase render — the result message is stored in session_state
        # and requires an explicit user action to advance, so it stays
        # visible long enough to be read (an auto-advance sleep pattern
        # does not guarantee this across rerun cycles).
        if st.session_state.get("otp_just_issued"):
            kind = st.session_state.get("otp_result_kind", "info")
            getattr(st, kind)(st.session_state.get("otp_result_message", ""))
            fallback_otp = st.session_state.get("otp_fallback_code")
            if fallback_otp:
                st.code(fallback_otp, language=None)
            if st_compat.button("Proceed — Enter Your Reset Code →", use_container_width=True, type="primary"):
                st.session_state["otp_just_issued"] = False
                _go("forgot_verify")
            if st_compat.button("← Try a Different Email", use_container_width=True):
                st.session_state["otp_just_issued"] = False
                st.rerun()
            return

        with st.form("forgot_request_form"):
            email = st.text_input("Registered Email Address")
            submitted = st_compat.form_submit_button("Send Reset Code →", use_container_width=True, type="primary")
            if submitted:
                email_clean = email.strip().lower()
                if not email_clean:
                    st.error("Please enter the email address associated with your account.")
                else:
                    result = db.create_password_reset_for_email(email_clean)
                    if result[0] is None:
                        st.error(
                            "The email address provided does not match any account on record. "
                            "Please verify your details and try again."
                        )
                    else:
                        canonical_username, otp = result
                        st.session_state["reset_username"] = canonical_username
                        st.session_state["reset_email"] = email_clean
                        st.session_state["otp_just_issued"] = True
                        st.session_state["otp_fallback_code"] = None

                        user = db.get_user(canonical_username)
                        user_email = user["email"] if user else email_clean
                        user_name = user["full_name"] if user else ""

                        if is_email_configured():
                            ok, msg = send_otp_email(user_email, user_name, otp, OTP_EXPIRY_MINUTES)
                            if ok:
                                st.session_state["otp_result_kind"] = "success"
                                st.session_state["otp_result_message"] = (
                                    f"A password reset code has been sent to {user_email}. "
                                    "Please check your inbox and proceed."
                                )
                            elif show_otp_on_screen():
                                st.session_state["otp_result_kind"] = "warning"
                                st.session_state["otp_result_message"] = (
                                    f"The reset email could not be delivered ({msg}). "
                                    "Your code is displayed below — please record it immediately, "
                                    "as it will not be shown again."
                                )
                                st.session_state["otp_fallback_code"] = otp
                            else:
                                # No on-screen code. Showing it here would hand a
                                # password reset to anyone who can merely submit
                                # this form — see show_otp_on_screen().
                                st.session_state["otp_result_kind"] = "error"
                                st.session_state["otp_result_message"] = (
                                    f"The reset email could not be delivered ({msg}). "
                                    "For your security the code is not shown on screen. "
                                    "Please try again shortly, or contact the IFT "
                                    "Department to have your password reset."
                                )
                                st.session_state["otp_fallback_code"] = None
                        elif show_otp_on_screen():
                            st.session_state["otp_result_kind"] = "warning"
                            st.session_state["otp_result_message"] = (
                                "Email delivery is not configured on this deployment. "
                                "The reset code is displayed below for local testing purposes only — "
                                "do not rely on this behaviour in a production environment."
                            )
                            st.session_state["otp_fallback_code"] = otp
                        else:
                            # Fail closed rather than print the key to the account.
                            st.session_state["otp_result_kind"] = "error"
                            st.session_state["otp_result_message"] = (
                                "Email delivery is not available on this deployment, so "
                                "password recovery cannot be completed here. For your "
                                "security the reset code is never shown on screen. "
                                "Please contact the IFT Department to have your "
                                "password reset."
                            )
                            st.session_state["otp_fallback_code"] = None
                            # The sentence a student sees must not name a missing
                            # secret — that would tell anyone probing the login
                            # page how the deployment is configured. The precise
                            # answer goes to the app's own log instead, which is
                            # where whoever has to fix this will actually look.
                            print("[email] " + email_status_report(), flush=True)
                        st.rerun()

        if st_compat.button("← Return to Sign In", use_container_width=True):
            _go("signin")


def _show_forgot_verify():
    username = st.session_state.get("reset_username", "")
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        if st.session_state.get("password_just_reset"):
            # A flow-completing success, so it gets a dialog rather than a
            # banner the user can scroll past. Parked + shown by
            # render_parked_dialog() because the rerun below would discard it.
            if not st.session_state.get("_pw_reset_dialog_shown"):
                st.session_state["_pw_reset_dialog_shown"] = True
                park_result_dialog(
                    "Your password has been updated. You can now sign in with "
                    "your new credentials.",
                    kind="success",
                    title="Password Changed",
                    button_label="Proceed to Sign In",
                )
            if st_compat.button("Proceed to Sign In →", use_container_width=True, type="primary"):
                st.session_state["password_just_reset"] = False
                st.session_state.pop("reset_username", None)
                _go("signin")
            return

        st.markdown(
            '<div class="login-form-header"><div class="login-form-header-bar"></div>'
            '<div class="login-form-header-tag">Account Recovery</div>'
            '<h2>Enter Your Reset Code</h2>'
            f'<p>Please check the inbox for <strong>{esc(username) if username else "your account"}</strong> '
            'and enter the 6-digit code provided below.</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("forgot_verify_form"):
            otp = st.text_input("6-Digit Reset Code", max_chars=6, placeholder="000000")
            new_password = st.text_input("New Password", type="password", placeholder="Minimum 8 characters")
            confirm_password = st.text_input("Confirm New Password", type="password", placeholder="Re-enter your new password")
            submitted = st_compat.form_submit_button("Reset Password →", use_container_width=True, type="primary")
            if submitted:
                if len(new_password) < 8:
                    st.error("Your new password must be at least 8 characters in length.")
                elif new_password != confirm_password:
                    st.error("The passwords entered do not match. Please try again.")
                else:
                    reset_email = st.session_state.get("reset_email", "")
                    ok, msg, canonical_username = db.verify_password_reset_by_email(reset_email, otp.strip())
                    if not ok:
                        st.error(msg)
                    else:
                        db.update_password(canonical_username, new_password)
                        changed_user = db.get_user(canonical_username)
                        if changed_user:
                            send_password_changed_email(changed_user["email"], changed_user["full_name"])
                        st.session_state["password_just_reset"] = True
                        st.rerun()

        if st_compat.button("← Return to Sign In", use_container_width=True):
            st.session_state.pop("reset_username", None)
            _go("signin")


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

def show_mandatory_password_change(username: str):
    """Blocks a signed-in user until their legacy hash is replaced.

    Accounts created by the first release of this project carry an unsalted
    SHA-256 digest. `db.verify_password` still accepts one, so they can sign in
    — but the row stays cheap to attack with precomputed tables until the
    password changes, and login no longer silently re-hashes. It used to, which
    upgraded the storage while leaving the user on the same password they had
    already reused elsewhere — fixing the wrong half of the problem.

    So the user is authenticated and then held here. `app.main()` calls this and
    returns, before the sidebar or any page renders, so the hold is structural
    rather than a link the user could simply decline to click.

    The sidebar stays hidden. Showing it would offer navigation that silently
    does nothing, which is worse than not offering it at all.
    """
    _hide_sidebar()
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(
            '<div class="admin-login-card">'
            f'<div class="admin-login-icon">{i("alert-triangle", 24, "#b45309")}</div>'
            '<div class="admin-login-title">Choose a New Password</div>'
            '<div class="admin-login-subtitle">Required before you can continue &mdash; '
            "a one-time security step on your account</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        html_alert(
            "Your password was set before this system used salted hashing, so it is "
            "stored in a form that is much easier to crack if the database is ever "
            "stolen. Setting a new one here replaces it with PBKDF2-SHA256 (100,000 "
            "rounds, a unique salt per account). Nothing else about your account "
            "changes.",
            kind="warning",
        )
        st.markdown("<div style='height:.7rem;'></div>", unsafe_allow_html=True)

        with st.form("mandatory_password_change_form", clear_on_submit=False):
            new_password = st.text_input(
                "New Password", type="password", placeholder="Minimum 8 characters"
            )
            confirm_password = st.text_input(
                "Confirm New Password", type="password",
                placeholder="Re-enter your new password",
            )
            submitted = st_compat.form_submit_button(
                "Set Password & Continue", use_container_width=True, type="primary"
            )
            if submitted:
                # Errors stay inline. This is form validation and the offending
                # input is directly above — see the note on `park_result_dialog`
                # for why a modal here would be the wrong call.
                if len(new_password) < 8:
                    st.error("Your new password must be at least 8 characters in length.")
                elif new_password != confirm_password:
                    st.error("The passwords entered do not match. Please try again.")
                else:
                    # Reject the current password. `verify_password` checks the
                    # stored hash, so this works for a legacy SHA-256 row too and
                    # catches the case where the user just presses the button and
                    # types what they already had — which would re-hash the same
                    # secret and satisfy the migration without improving anything.
                    current = db.get_user(username) or {}
                    if db.verify_password(
                        new_password, current.get("password_hash") or ""
                    ):
                        st.error(
                            "That is the password you signed in with. Choose a "
                            "different one."
                        )
                    else:
                        db.update_password(username, new_password)
                        changed = db.get_user(username)
                        if changed:
                            send_password_changed_email(
                                changed["email"], changed["full_name"]
                            )
                        # No session-state flag is cleared here: there is no
                        # flag. The row was just re-hashed, so the gate in
                        # `app.main()` stops holding on the next run by itself.
                        park_result_dialog(
                            "Your password is now stored with salted PBKDF2-SHA256. "
                            "You are signed in.",
                            kind="success",
                            title="Password Updated",
                            details=(
                                "This was a one-time step. The rest of the system "
                                "is already available to you."
                            ),
                            button_label="Continue",
                        )
                        st.rerun()


def show_login_page():
    _hide_sidebar()
    view = st.session_state.get("login_view", "signin")

    if view in ("register", "forgot_request", "forgot_verify"):
        # These flows are role-agnostic in the UI (registration is
        # student-only by design, forgot-password serves both roles).
        if view == "register":
            _show_register()
        elif view == "forgot_request":
            _show_forgot_request()
        else:
            _show_forgot_verify()
        return

    role = _role_switch()

    if role == "student":
        _show_student_signin()
    else:
        _show_admin_signin()
