"""app_pages/home.py — student landing page after login."""

import streamlit as st

from config import CATEGORIES, CAT_META, CURRENT_SESSION
from db import load_data, filter_by_username
from components import html_metric, page_header, section_header, progress_bar, html_alert
from icons import i


def show_home(user, username, session: str | None = None):
    active_sess = session or CURRENT_SESSION
    page_header(
        "home",
        f"Welcome back, {user['name'].split()[0]}",
        f"Submit your feedback for the {active_sess} academic session and track your contributions.",
        badge_text=f"Student Portal · {active_sess} Session",
    )

    df = load_data(session=active_sess)
    total = len(df)
    avg_r = round(df["rating"].mean(), 1) if not df.empty else 0
    # Routed through filter_by_username because every other username lookup in
    # this app is case-insensitive. Comparing the column with `==` made this
    # counter silently read 0 for an account whose stored casing differed from
    # the one in session_state — the student saw "0 submissions" on a page they
    # had in fact submitted, and a 0% completion bar.
    mine = len(filter_by_username(df, username))
    completion = round(mine / len(CATEGORIES) * 100)

    c1, c2, c3, c4 = st.columns(4)
    with c1: html_metric("inbox", total, "Total Responses", "blue")
    with c2: html_metric("star", avg_r, "System Avg Rating", "gold")
    with c3: html_metric("check-circle", mine, "Your Submissions", "green")
    with c4: html_metric("target", f"{completion}%", "Your Completion", "purple")

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    progress_bar("Feedback Progress", mine, len(CATEGORIES))
    section_header("folder", "Feedback Categories")

    cols = st.columns(2)
    for idx, cat in enumerate(CATEGORIES):
        meta = CAT_META[cat]
        sub = df[df["category"] == cat] if not df.empty else df
        done = not filter_by_username(sub, username).empty
        avg = round(sub["rating"].mean(), 1) if not sub.empty else "—"
        count = len(sub)
        badge = (
            f'<span class="badge-submitted">{i("check", 12)} Submitted</span>' if done
            else f'<span class="badge-pending">{i("clock", 12)} Pending</span>'
        )
        with cols[idx % 2]:
            st.markdown(
                f'<div class="cat-card">'
                f'<div class="cat-card-header">'
                f'<div class="cat-card-icon-wrap">{i(meta["icon"], 22, "#3b82f6")}</div>'
                f"{badge}</div>"
                f'<div class="cat-card-title">{cat}</div>'
                f'<div class="cat-card-desc">{meta["desc"]}</div>'
                f'<div class="cat-card-footer">'
                f'<span class="cat-stat">{i("bar-chart", 12)} {count} responses</span>'
                f'<span class="cat-stat">{i("star", 12)} {avg} avg</span>'
                f"</div></div>",
                unsafe_allow_html=True,
            )

    remaining = len(CATEGORIES) - mine
    if remaining > 0:
        st.markdown("<div style='height:.3rem;'></div>", unsafe_allow_html=True)
        html_alert(
            f"You have <strong>{remaining}</strong> categor{'y' if remaining == 1 else 'ies'} remaining. "
            "Please navigate to each category using the sidebar to complete your feedback.",
            "info", raw=True,
        )
