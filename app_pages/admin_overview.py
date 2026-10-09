"""app_pages/admin_overview.py — high-level admin summary."""

import streamlit as st

import st_compat

from config import CATEGORIES, CAT_META, ALL_SESSIONS_LABEL
from db import load_data
from charts import make_rating_bar, make_category_radar
from app_pages.targets import chart_card
from components import html_metric, page_header, section_header, empty_state, html_alert
from icons import i, sentiment_icon, sentiment_color


def show_admin_overview(session: str | None = None):
    active_sess = session or ALL_SESSIONS_LABEL
    page_header("bar-chart", "Analytics Overview",
                f"Comprehensive departmental overview of student feedback submissions, rating distributions, and sentiment trends ({active_sess}).",
                badge_text=f"Admin Portal · {active_sess}")

    df = load_data(session=active_sess)
    if df.empty:
        empty_state("inbox", f"No Feedback Data for {active_sess}",
                    f"Student feedback for the {active_sess} session will appear here once submissions begin coming in.")
        return

    total = len(df)
    avg_all = round(df["rating"].mean(), 1)
    respondents = df["username"].nunique()
    categories_active = df["category"].nunique()
    sentiments = df["effective_sentiment"]
    total_pos = sentiments.eq("Positive").sum()
    total_neg = sentiments.eq("Negative").sum()
    neg_pct = round(total_neg / total * 100, 1) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1: html_metric("inbox", total, "Total Responses", "blue")
    with c2: html_metric("star", avg_all, "Overall Avg Rating", "gold")
    with c3: html_metric("users", respondents, "Unique Students", "green")
    with c4: html_metric("frown", f"{neg_pct}%", "Negative Sentiment", "purple")

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="stat-row">'
        f'<div class="stat-pill">{i("smile", 14, "#059669")} Positive: <strong>{total_pos}</strong></div>'
        f'<div class="stat-pill">{i("meh", 14, "#d97706")} Neutral: <strong>{total - total_pos - total_neg}</strong></div>'
        f'<div class="stat-pill">{i("frown", 14, "#dc2626")} Negative: <strong>{total_neg}</strong></div>'
        f'<div class="stat-pill">{i("folder", 14)} Active Categories: <strong>{categories_active}/{len(CATEGORIES)}</strong></div>'
        f'<div class="stat-pill">{i("calendar", 14)} Latest Submission: <strong>{str(df["timestamp"].max())[:10]}</strong></div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    section_header("folder", "Category Performance At-a-Glance")
    for cat in CATEGORIES:
        sub = df[df["category"] == cat]
        if sub.empty:
            count_label, avg_val, rating_clr = "No responses yet", "—", "#94a3b8"
            top_s, sent_clr = "Neutral", "#94a3b8"
        else:
            avg_val = round(sub["rating"].mean(), 1)
            sents = sub["effective_sentiment"]
            top_s = sents.value_counts().idxmax() if not sents.empty else "Neutral"
            sent_clr = sentiment_color(top_s)
            rating_clr = "#059669" if avg_val >= 4 else "#d97706" if avg_val >= 3 else "#dc2626"
            pct_complete = round(len(sub) / respondents * 100) if respondents else 0
            count_label = f"{len(sub)} responses · {pct_complete}% student participation"
        st.markdown(
            f'<div class="cat-breakdown-row">'
            f'<div class="cat-breakdown-icon-wrap">{i(CAT_META[cat]["icon"], 18, "#3b82f6")}</div>'
            f'<div class="cat-breakdown-info"><div class="cat-breakdown-name">{cat}</div>'
            f'<div class="cat-breakdown-count">{count_label}</div></div>'
            f'<div class="cat-breakdown-stats">'
            f'<div class="cat-breakdown-rating" style="color:{rating_clr};">{avg_val}</div>'
            f'<div class="cat-breakdown-sent" style="color:{sent_clr};">{i(sentiment_icon(top_s), 12, sent_clr)} {top_s}</div>'
            f"</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    section_header("trending-up", "Quick Charts")
    c1, c2 = st.columns(2)
    with c1:
        chart_card("Rating Distribution", "bar-chart", make_rating_bar(df, ""),
                   caption="How many submissions gave each star rating.")
    with c2:
        chart_card("Category Overview", "radar", make_category_radar(df),
                   caption="Average rating per category, on the same 1-5 scale.")

    html_alert(
        "<strong>Advisory:</strong> Consult the <strong>Full Dashboard</strong> for granular analytics and "
        "raw submission records, or navigate to <strong>Decision Insights</strong> for prioritised departmental action items.",
        "info", raw=True,
    )
