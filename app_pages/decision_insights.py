"""app_pages/decision_insights.py — AI-flavoured, rule-based recommendations per category."""

from collections import Counter
from datetime import datetime

import streamlit as st

import st_compat

from config import CATEGORIES, CAT_META, ALL_SESSIONS_LABEL
from db import (load_data, parse_context, context_text_list, load_admin_notes,
                save_admin_note)
from components import html_metric, page_header, section_header, empty_state, esc
from icons import i

PRIORITY_CONFIG = {
    "critical": {
        "color": "#ef4444", "bg": "rgba(239,68,68,.06)", "border": "rgba(239,68,68,.25)",
        "icon_bg": "rgba(239,68,68,.12)", "label": "Needs Urgent Action", "label_icon": "alert-triangle",
        "rec": "Immediate administrative intervention required. Average rating indicates systemic student concerns; "
               "direct student engagement and root-cause analysis recommended.",
    },
    "warning": {
        "color": "#f59e0b", "bg": "rgba(245,158,11,.06)", "border": "rgba(245,158,11,.25)",
        "icon_bg": "rgba(245,158,11,.1)", "label": "Needs Attention", "label_icon": "alert-circle",
        "rec": "Moderate student dissatisfaction detected. Review qualitative feedback and structured "
               "responses below to target specific areas for operational enhancement.",
    },
    "good": {
        "color": "#10b981", "bg": "rgba(16,185,129,.04)", "border": "rgba(16,185,129,.2)",
        "icon_bg": "rgba(16,185,129,.1)", "label": "Performing Well", "label_icon": "check-circle",
        "rec": "Strong positive student sentiment and performance. Document and standardise "
               "existing methodologies across departmental courses.",
    },
}

CTX_REC_TEMPLATES = {
    "Course Content": "Top student-requested emphasis areas",
    "Lecturer Teaching Style": "Most reported delivery challenges",
    "Facilities": "Most frequently flagged infrastructure items",
    "Curriculum": "Most requested missing topics",
}


def show_decision_support(admin_username: str = "admin", session: str | None = None):
    active_sess = session or ALL_SESSIONS_LABEL
    page_header("target", "Decision Insights",
                f"Departmental category assessment and prioritised recommendations for academic interventions ({active_sess}).",
                badge_text=f"AI Analysis · {active_sess}")

    df = load_data(session=active_sess)
    if df.empty:
        empty_state("inbox", f"No Data Available for {active_sess}",
                    f"Decision insights for the {active_sess} session will appear once feedback submissions are collected.")
        return

    notes = load_admin_notes()

    total = len(df)
    avg_all = round(df["rating"].mean(), 2)
    sentiments = df["effective_sentiment"]
    neg_total, pos_total = sentiments.eq("Negative").sum(), sentiments.eq("Positive").sum()
    neutral_total = total - neg_total - pos_total
    neg_pct_total = round(neg_total / total * 100, 1) if total else 0
    health = "Excellent" if avg_all >= 4 else "Good" if avg_all >= 3.5 else "Needs Work"
    health_icon = "heart" if avg_all >= 4 else "meh" if avg_all >= 3.5 else "alert-triangle"
    health_accent = "green" if avg_all >= 4 else "gold"

    c1, c2, c3, c4 = st.columns(4)
    with c1: html_metric("bar-chart", total, "Data Points", "blue")
    with c2: html_metric("star", avg_all, "Overall Rating", "gold")
    with c3: html_metric("frown", f"{neg_pct_total}%", "Negative Rate", "purple")
    with c4: html_metric(health_icon, health, "System Health", health_accent)

    st.markdown(
        f'<div class="stat-row">'
        f'<div class="stat-pill">{i("smile", 14, "#059669")} Positive: <strong>{pos_total}</strong></div>'
        f'<div class="stat-pill">{i("meh", 14, "#d97706")} Neutral: <strong>{neutral_total}</strong></div>'
        f'<div class="stat-pill">{i("frown", 14, "#dc2626")} Negative: <strong>{neg_total}</strong></div>'
        f'<div class="stat-pill">{i("folder", 14)} Categories: <strong>{df["category"].nunique()}/{len(CATEGORIES)}</strong></div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    section_header("search", "Category Analysis & Recommendations")

    items = []
    for cat in CATEGORIES:
        sub = df[df["category"] == cat]
        if sub.empty:
            continue
        avg = sub["rating"].mean()
        neg = sub["effective_sentiment"].eq("Negative").sum()
        neg_pct = neg / len(sub) * 100 if len(sub) else 0
        priority = "critical" if avg < 2.5 else "warning" if avg < 3.5 else "good"

        # `context_data` is free-form JSON, not a constrained enum — see the
        # note above full_dashboard's identical block. `context_text_list`
        # drops non-scalar elements so `Counter` cannot be handed an
        # unhashable value, which raised TypeError and killed the page.
        all_items = []
        for _, row in sub.iterrows():
            ctx = parse_context(row.get("context_data"))
            if cat == "Course Content":
                all_items.extend(context_text_list(ctx.get("emphasis_areas"), limit=40))
            elif cat == "Lecturer Teaching Style":
                all_items.extend(context_text_list(ctx.get("challenges"), limit=40))
            elif cat == "Facilities":
                all_items.extend(context_text_list(ctx.get("facilities_flagged"), limit=40))
            elif cat == "Curriculum":
                all_items.extend(context_text_list(ctx.get("missing_topics"), limit=40))

        top_items = [item for item, _ in Counter(all_items).most_common(3)] if all_items else []
        items.append({"cat": cat, "avg": round(avg, 2), "count": len(sub),
                      "neg_pct": round(neg_pct, 1), "priority": priority, "top_items": top_items})

    for item in sorted(items, key=lambda x: x["avg"]):
        cfg = PRIORITY_CONFIG[item["priority"]]
        neg_clr = "#ef4444" if item["neg_pct"] > 30 else "#f59e0b" if item["neg_pct"] > 15 else "#10b981"
        rating_clr = cfg["color"]

        ctx_insight_html = ""
        if item["top_items"]:
            # esc() is not optional here. Every one of these strings came out
            # of the `context_data` JSON blob, and that column is not
            # constrained to the option lists in config.py — one
            # `<img onerror=…>` typed into a "course name" would otherwise
            # execute in every admin's browser. full_dashboard.py made exactly
            # this fix for the identical data; this page was missed.
            tag_html = "".join(
                f'<span style="background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.2);'
                f'border-radius:6px;padding:.12rem .5rem;font-size:.7rem;font-weight:600;'
                f'color:#3b82f6;margin:.15rem .2rem;display:inline-block;">{esc(t)}</span>'
                for t in item["top_items"]
            )
            ctx_insight_html = (
                f'<div style="margin-top:.9rem;padding:.8rem 1rem;background:rgba(139,92,246,.04);'
                f'border:1px solid rgba(139,92,246,.15);border-radius:8px;">'
                f'<div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;'
                f'color:#7c3aed;font-weight:700;margin-bottom:.5rem;">'
                f'{i("microscope", 12, "#7c3aed")} {CTX_REC_TEMPLATES.get(item["cat"], "Key findings")}</div>'
                f"{tag_html}</div>"
            )

        st.markdown(
            f'<div class="insight-card" style="border-left:4px solid {cfg["color"]};'
            f'background:{cfg["bg"]};border-color:{cfg["border"]};">'
            f'<div class="insight-header"><div class="insight-header-left">'
            f'<div class="cat-breakdown-icon-wrap" style="background:{cfg["icon_bg"]};border:1px solid {cfg["border"]};">'
            f'{i(CAT_META[item["cat"]]["icon"], 18, cfg["color"])}</div>'
            f'<div><div class="insight-title">{item["cat"]}</div>'
            f'<div style="font-size:.7rem;color:var(--text-3);margin-top:.15rem;">'
            f'{item["count"]} response{"s" if item["count"]!=1 else ""} collected</div></div></div>'
            f'<span style="background:{cfg["icon_bg"]};color:{cfg["color"]};border:1px solid {cfg["border"]};'
            f'border-radius:999px;padding:.25rem 1rem;font-size:.68rem;font-weight:700;white-space:nowrap;'
            f'display:inline-flex;align-items:center;gap:.35rem;">'
            f'{i(cfg["label_icon"], 12, cfg["color"])} {cfg["label"]}</span></div>'
            f'<div class="insight-metrics">'
            f'<div class="insight-metric"><div class="insight-metric-value" style="color:{rating_clr};">{item["avg"]}</div>'
            f'<div class="insight-metric-label">Avg Rating</div></div>'
            f'<div class="insight-metric"><div class="insight-metric-value" style="color:var(--text-1);">{item["count"]}</div>'
            f'<div class="insight-metric-label">Responses</div></div>'
            f'<div class="insight-metric"><div class="insight-metric-value" style="color:{neg_clr};">{item["neg_pct"]}%</div>'
            f'<div class="insight-metric-label">Negative</div></div></div>'
            f'<div class="insight-rec">{i("lightbulb", 16)}<span>{cfg["rec"]}</span></div>'
            f"{ctx_insight_html}</div>",
            unsafe_allow_html=True,
        )

        # ── Admin action note: a short, persisted note the department can
        # attach to this category (e.g. "Raised with the lab coordinator,
        # new routers arriving w/c 12 Aug"). Purely additive — students
        # never see this; it lives only on this admin-only page.
        existing = notes.get(item["cat"], {})
        with st.expander(f"Action note for {item['cat']}" + (" · saved" if existing.get("note") else "")):
            note_val = st.text_area(
                "What is being done about this category?",
                value=existing.get("note", ""),
                key=f"note_{item['cat']}",
                placeholder="e.g. Flagged to the lab coordinator; procurement request submitted 04 Aug 2026.",
                label_visibility="collapsed",
                height=80,
            )
            save_col, meta_col = st.columns([1, 3])
            with save_col:
                if st_compat.button("Save note", key=f"save_note_{item['cat']}", icon=":material/save:", type="primary"):
                    save_admin_note(item["cat"], note_val.strip(), admin_username,
                                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    st_compat.toast(f"Note saved for {item['cat']}", icon=":material/check_circle:")
                    st.rerun()
            with meta_col:
                if existing.get("updated_at"):
                    st.caption(f"Last updated by {esc(existing.get('updated_by',''))} on {esc(existing.get('updated_at',''))}")

    trend_text = "Positive Trend" if avg_all >= 3.5 else "Needs Improvement"
    trend_icon = "trending-up" if avg_all >= 3.5 else "trending-down"
    cats_monitored = len(items)

    st.markdown(
        f'<div class="system-health-box">'
        f'<div class="system-health-title">{i(health_icon, 18, "#3b82f6")} Overall System Health Summary</div>'
        f'<div class="system-health-body">'
        f'Average rating: <span class="sh-tag" style="color:#d97706;">{i("star",12,"#d97706")} {avg_all}/5.0</span>'
        f'Trend: <span class="sh-tag" style="color:#3b82f6;">{i(trend_icon,12,"#3b82f6")} {trend_text}</span>'
        f'Total data points: <span class="sh-tag" style="color:var(--text-1);">{total}</span>'
        f'Categories: <span class="sh-tag" style="color:#7c3aed;">{cats_monitored}/{len(CATEGORIES)}</span>'
        f'Negative rate: <span class="sh-tag" style="color:{"#dc2626" if neg_pct_total > 20 else "#059669"};">{neg_pct_total}%</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )
