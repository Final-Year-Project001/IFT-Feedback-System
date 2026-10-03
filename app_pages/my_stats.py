"""app_pages/my_stats.py — a student's personal submission history & analytics."""

import pandas as pd
import streamlit as st

import st_compat

from config import CATEGORIES, CAT_META
from db import load_data, parse_context, filter_by_username
from charts import make_rating_bar, make_sentiment_pie
from sentiment import confidence_tier
from components import html_metric, page_header, section_header, progress_bar, empty_state, esc
from icons import i, sentiment_icon, sentiment_color


def _confidence_pill(confidence_val) -> str:
    """Renders a small confidence badge HTML string.
    confidence_val: float 0–1 or None.

    The tier NAME comes from `sentiment.confidence_tier`, which reads the one
    shared `CONFIDENCE_TIERS` ladder. This function used to carry its own
    ladder (88 / 72 / 58, labelled High / Good / Moderate / Low) while the
    engine and the feedback form used a different one (90 / 78 / 65 / 55,
    labelled Very High / High / Moderate / Low), so the same 79% was called
    "Good" here and "High" on the submission summary. Only the COLOURS are
    still local, because they are a presentation choice with no counterpart in
    the engine.
    """
    if confidence_val is None:
        return ""
    try:
        conf = float(confidence_val)
    except (TypeError, ValueError):
        return ""

    pct = int(conf * 100)
    tier = confidence_tier(conf)

    if tier in ("Very High", "High"):
        clr, bg, bdr = "#059669", "rgba(5,150,105,.1)", "rgba(5,150,105,.25)"
    elif tier == "Moderate":
        clr, bg, bdr = "#2563eb", "rgba(37,99,235,.1)", "rgba(37,99,235,.25)"
    elif tier == "Low":
        clr, bg, bdr = "#d97706", "rgba(217,119,6,.1)", "rgba(217,119,6,.25)"
    else:
        clr, bg, bdr = "#94a3b8", "rgba(148,163,184,.1)", "rgba(148,163,184,.25)"

    return (
        f'<span class="sentiment-confidence-badge" '
        f'style="background:{bg};border-color:{bdr};color:{clr};" '
        f'title="{tier} confidence">'
        f'{i("shield", 10, clr)} {pct}%'
        f'</span>'
    )


def show_basic_stats(username, session: str | None = None):
    active_sess = session or "2025/2026"
    page_header("bar-chart", "My Feedback Statistics",
                f"A personal overview of your feedback submitted for the {active_sess} academic session, including ratings, sentiment analysis, and completion status.",
                badge_text=f"Personal Analytics · {active_sess}")

    df = load_data(session=active_sess)
    if df.empty:
        empty_state("inbox", f"No Feedback Data for {active_sess}",
                    f"No submissions recorded for the {active_sess} session yet. Use the sidebar to submit feedback across any category.")
        return

    mine = filter_by_username(df, username)
    submitted_count = len(mine)
    remaining_count = len(CATEGORIES) - submitted_count
    avg_r = round(mine["rating"].mean(), 1) if not mine.empty else 0
    completion = round(submitted_count / len(CATEGORIES) * 100)

    c1, c2, c3, c4 = st.columns(4)
    with c1: html_metric("check-circle", submitted_count, "Submitted", "green")
    with c2: html_metric("clock", remaining_count, "Remaining", "gold")
    with c3: html_metric("star", avg_r if not mine.empty else "—", "Avg Rating", "blue")
    with c4: html_metric("target", f"{completion}%", "Completion", "purple")

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    progress_bar("Overall Completion", submitted_count, len(CATEGORIES))

    if mine.empty:
        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        empty_state("edit", "No Submissions Recorded",
                    "Navigate to a feedback category using the sidebar to submit your first response.")
        return

    section_header("list-checks", "Category Progress")
    for cat in CATEGORIES:
        sub = mine[mine["category"] == cat]
        done = not sub.empty
        ctx_hint = ""
        if done:
            row = sub.iloc[0]
            avg_val = int(row["rating"])
            sent = row.get("effective_sentiment", row.get("sentiment", "Neutral"))
            clr = sentiment_color(sent)
            ctx = parse_context(row.get("context_data"))

            # Confidence badge
            conf_val = row.get("sentiment_confidence")
            if conf_val is not None and pd.notna(conf_val):
                try:
                    actual_conf = float(conf_val)
                except (TypeError, ValueError):
                    actual_conf = 0.85
            else:
                score_val = row.get("sentiment_score", 0.0)
                try:
                    score_f = float(score_val) if score_val is not None else 0.0
                except (TypeError, ValueError):
                    score_f = 0.0
                actual_conf = min(0.99, max(0.48, 0.55 + abs(score_f) * 0.40))
            conf_badge = _confidence_pill(actual_conf)

            if cat == "Course Content" and ctx.get("course_rated"):
                ctx_hint = f' · {esc(ctx["course_rated"][:40])}'
            elif cat == "Lecturer Teaching Style" and ctx.get("lecturer_name"):
                ctx_hint = f' · {esc(ctx["lecturer_name"])}'
            elif cat == "Facilities" and ctx.get("urgency"):
                ctx_hint = f' · {esc(ctx["urgency"].split("—")[0].strip())}'
            elif cat == "Curriculum" and ctx.get("industry_alignment"):
                ctx_hint = f' · Alignment: {esc(ctx["industry_alignment"])}'

            status_html = (
                f'<span class="badge-submitted">{i("check", 11)} Done</span>'
                f'<span style="font-size:.78rem;font-weight:700;color:#d97706;margin-left:.7rem;">{avg_val}/5</span>'
                f'<span style="font-size:.73rem;color:{clr};margin-left:.7rem;font-weight:600;">'
                f'{i(sentiment_icon(sent), 12, clr)} {sent}</span>'
                f'<span style="margin-left:.5rem;">{conf_badge}</span>'
            )
        else:
            status_html = f'<span class="badge-pending">{i("clock", 11)} Not submitted</span>'

        st.markdown(
            f'<div class="cat-breakdown-row">'
            f'<div class="cat-breakdown-icon-wrap">{i(CAT_META[cat]["icon"], 18, "#3b82f6")}</div>'
            f'<div class="cat-breakdown-info">'
            f'<div class="cat-breakdown-name">{cat}</div>'
            f'<div class="cat-breakdown-count">{CAT_META[cat]["desc"][:55]}…{ctx_hint}</div>'
            f'</div>'
            f'<div style="text-align:right;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;justify-content:flex-end;">{status_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    section_header("bar-chart", "Visual Breakdown")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="chart-wrap"><div class="chart-title">{i("bar-chart", 13)} Rating Distribution</div>', unsafe_allow_html=True)
        fig = make_rating_bar(mine, "My Rating Distribution")
        if fig:
            st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="chart-wrap"><div class="chart-title">{i("smile", 13)} Sentiment Breakdown</div>', unsafe_allow_html=True)
        fig = make_sentiment_pie(mine)
        if fig:
            st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    section_header("folder-open", "Submission History")
    # The header used to be opened inside a `<div class="data-table-wrap">` and
    # closed after the dataframe call, on the assumption the two would nest
    # into one card. They cannot: each `st.markdown` renders its own fragment
    # and the HTML parser closes the unclosed `<div>` at the end of that one
    # call, so the dataframe was never inside it. The wrap therefore styled
    # only this title bar — a border, radius and shadow around a single strip
    # of text, with the table below it unframed and the wrapper div a no-op.
    # The card treatment now lives on the header itself, and the table keeps
    # the frame `[data-testid="stDataFrame"]` already has, so the two read as
    # a deliberate pair of stacked cards instead of one broken card.
    st.markdown(
        f'<div class="data-table-header">{i("table", 13)} All Submitted Feedback Records</div>',
        unsafe_allow_html=True,
    )
    history_df = mine.copy()
    if "sentiment_confidence" in history_df.columns:
        history_df["confidence"] = history_df["sentiment_confidence"].apply(
            lambda v: f"{int(float(v)*100)}%" if pd.notna(v) else "—"
        )
    cols_list = [c for c in ["category", "rating", "effective_sentiment", "confidence", "comment", "timestamp"] if c in history_df.columns]
    display_df = history_df[cols_list].reset_index(drop=True).copy().rename(columns={"effective_sentiment": "sentiment"})
    if "comment" in display_df.columns:
        display_df["comment"] = display_df["comment"].str.slice(0, 80) + "…"
    st_compat.dataframe(display_df, use_container_width=True, hide_index=True)
