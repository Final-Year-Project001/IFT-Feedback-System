"""app_pages/full_dashboard.py — deep-dive admin analytics + structured aggregations."""

from collections import Counter

import pandas as pd
import streamlit as st

import st_compat

from config import CATEGORIES, CAT_META, CURRENT_SESSION, ALL_SESSIONS_LABEL, SEMESTERS
from db import (
    load_data, parse_context, context_text_list, correct_sentiment,
    get_academic_sessions, get_active_session, create_academic_session,
    set_default_session, get_session_stats,
    delete_academic_session, count_session_submissions,
    get_active_semester, set_active_semester, get_all_session_semesters,
)
from charts import make_rating_bar, make_category_radar, make_sentiment_pie, make_level_pie, make_trend_bar
from app_pages.targets import (
    render_lecturer_targets, render_course_targets, render_facility_targets,
    chart_card,
)
from components import html_metric, page_header, section_header, empty_state, esc, html_alert
from icons import i, sentiment_icon, sentiment_color
from sentiment import engine_status, display_engine_name


def _as_float(value):
    """Returns `value` as a float, or None if it is not numeric.

    The engine status card formats numbers straight into HTML. Model metadata
    comes from an untrusted pickle, so a `None`, a string or a nested dict must
    degrade to an em dash rather than raise.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _render_engine_status_card(status: dict):
    """Renders the rating engine's status card.

    VADER and the trained classifier are both gone, so there is no "which engine
    is running" question left to answer — there is exactly one, it is three
    integer comparisons, and it cannot be degraded. The card now reports the
    thresholds instead, which is the only thing an administrator can actually
    check.
    """
    problems = status.get("engine_problems") or []

    engine_color = "#059669"
    engine_bg = "rgba(5,150,105,.08)"
    engine_border = "rgba(5,150,105,.25)"
    engine_dot = "#10b981"
    engine_label = esc(display_engine_name(status.get("active_engine") or "rating_threshold_engine"))
    engine_icon_name = "zap"
    if problems:
        # Kept as a branch rather than deleted: `engine_status()` is a public
        # helper, and if it ever reports a problem this card must not dress it
        # up in the healthy green pill.
        engine_color = "#d97706"
        engine_bg = "rgba(217,119,6,.08)"
        engine_border = "rgba(217,119,6,.25)"
        engine_dot = "#f59e0b"
        engine_label = f"Degraded — {esc(display_engine_name(status.get('engine_name', 'unavailable')))}"
        engine_icon_name = "alert-triangle"

    # `lex_count`, `mwe_count`, `neg_count` and `intens_count` used to be read
    # here for a row of lexicon metrics. They are gone: `engine_status()` reports
    # 0 for all four, so the row rendered four zeros, and the bands below them
    # — the only figures an administrator can act on — were the ones that had
    # been pushed off the card when the engine card was rewritten.
    #
    # `esc` is not optional here and the fallback below deliberately keeps a
    # real default rather than the literal text "None": this value is
    # interpolated into `unsafe_allow_html`.
    _conf_raw = status.get("confidence_range")
    conf_range = esc(_conf_raw) if _conf_raw else "90% &ndash; 99%"
    _thresholds = esc(status.get("rating_thresholds", "1-2 Negative · 3 Neutral · 4-5 Positive"))

    st.markdown(f"""
    <div class="engine-status-card">
        <div class="engine-status-header">
            <div class="engine-status-left">
                <div class="engine-status-icon" style="background:{engine_bg};border-color:{engine_border};">
                    {i(engine_icon_name, 22, engine_color)}
                </div>
                <div>
                    <div class="engine-status-title">Sentiment Analysis Engine</div>
                    <div class="engine-active-pill" style="background:{engine_bg};border-color:{engine_border};color:{engine_color};">
                        <span style="display:inline-block;width:7px;height:7px;border-radius:50%;
                            background:{engine_dot};box-shadow:0 0 6px {engine_dot};margin-right:.4rem;
                            flex-shrink:0;"></span>
                        {engine_label}
                    </div>
                </div>
            </div>
            <div class="engine-conf-badge">
                {i("chart-bar", 13, "#7c3aed")} Bands: <strong>{_thresholds}</strong>
            </div>
        </div>
        <div class="engine-metrics-row">
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#2563eb;">3</div>
                <div class="engine-metric-lbl">{i("chart-bar", 11, "#94a3b8")} Bands</div>
            </div>
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#7c3aed;">{esc(status.get('negative_max', 2))}&ndash;{esc(status.get('neutral', 3))}</div>
                <div class="engine-metric-lbl">{i("frown", 11, "#94a3b8")} Negative &middot; Neutral</div>
            </div>
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#059669;">{esc(status.get('neutral', 3))}&ndash;5</div>
                <div class="engine-metric-lbl">{i("smile", 11, "#94a3b8")} Neutral &middot; Positive</div>
            </div>
        </div>
        {"".join(
            f'<div class="engine-error-pill">{i("alert-triangle", 13, "#dc2626")} {esc(str(p)[:140])}</div>'
            for p in status.get("engine_problems", [])
        )}
    </div>
    """, unsafe_allow_html=True)


def _render_session_manager(admin_username: str):
    """Renders the Academic Session management panel for administrators."""
    sessions = get_academic_sessions()
    active_def = get_active_session()
    semesters = get_all_session_semesters()
    stats = get_session_stats()

    with st.expander("Academic Sessions Management (Create, Set Active & Semester)"):
        st.markdown(
            '<div style="font-size:.82rem;color:var(--text-2);margin-bottom:.85rem;">'
            "Manage the academic sessions for student feedback collection. Each session runs one "
            "<strong>active semester</strong> &mdash; Rain or Harmattan. Students may only submit feedback "
            "for that semester; choosing the other one tells them it is not active. Sessions created here "
            "immediately reflect across all student submission portals, administrative filters, and analytics "
            "dashboards."
            "</div>",
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns([1.2, 0.8], gap="medium")

        with col_left:
            st.markdown(f'<div style="font-size:.78rem;font-weight:700;color:var(--text-1);margin-bottom:.5rem;">{i("list", 13)} Existing Academic Sessions</div>', unsafe_allow_html=True)
            for sess in sessions:
                s_stat = stats.get(sess, {"total_feedback": 0, "avg_rating": 0.0, "unique_students": 0})
                is_cur_def = (sess == active_def)
                active_sem = semesters.get(sess, SEMESTERS[0])
                badge_html = (
                    '<span style="background:rgba(5,150,105,.1);color:#059669;border:1px solid rgba(5,150,105,.25);'
                    'padding:.15rem .6rem;border-radius:999px;font-size:.65rem;font-weight:700;">Active Default</span>'
                    if is_cur_def else
                    '<span style="background:rgba(148,163,184,.1);color:#64748b;border:1px solid rgba(148,163,184,.2);'
                    'padding:.15rem .6rem;border-radius:999px;font-size:.65rem;font-weight:600;">Standard Session</span>'
                )
                st.markdown(
                    f'<div style="background:var(--navy-card2);border:1px solid var(--navy-border);border-radius:10px;'
                    f'padding:.65rem .85rem;margin-bottom:.5rem;display:flex;align-items:center;justify-content:space-between;">'
                    f'<div>'
                    f'<div style="font-weight:700;font-size:.85rem;color:var(--text-1);">{esc(sess)}</div>'
                    f'<div style="font-size:.68rem;color:var(--text-3);margin-top:.15rem;">'
                    f'{s_stat["total_feedback"]} submissions · {s_stat["unique_students"]} students · {s_stat["avg_rating"]}/5 avg'
                    f'</div>'
                    f'<div style="font-size:.68rem;color:var(--text-3);margin-top:.15rem;">'
                    f'Active semester: <strong style="color:var(--text-2);">{esc(active_sem)}</strong>'
                    f'</div>'
                    f'</div>'
                    f'<div style="display:flex;align-items:center;gap:.5rem;">{badge_html}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # The active semester is the whole gate the student form
                # respects, so it needs a control an administrator can reach
                # without recreating the session. With two semesters the
                # remaining choice is unambiguous, so one button flips it.
                other_sem = SEMESTERS[1] if active_sem == SEMESTERS[0] else SEMESTERS[0]
                if st_compat.button(
                    f"Set {other_sem} active for '{sess}'",
                    key=f"set_semester_{sess}",
                    use_container_width=True,
                ):
                    ok, msg = set_active_semester(sess, other_sem, admin_username)
                    if ok:
                        st.session_state["flash_message"] = msg
                        st.session_state["flash_kind"] = "success"
                        st.rerun()
                    else:
                        st.error(msg)

                # Previously `set_default_session` was imported here and never
                # called: a session could be created and flagged "set as active
                # default" at creation time, but an existing default could never
                # be moved. This button is the missing control.
                if not is_cur_def:
                    if st_compat.button(
                        f"Make '{sess}' the active default",
                        key=f"set_default_{sess}",
                        use_container_width=True,
                    ):
                        ok, msg = set_default_session(sess, admin_username)
                        if ok:
                            st.session_state["flash_message"] = msg
                            st.session_state["flash_kind"] = "success"
                            st.rerun()
                        else:
                            st.error(msg)

                # Deleting a session, with a confirmation. Same rule as the
                # account-deletion flow on the User Management page: a list of
                # identically shaped buttons is exactly where one stray press acts
                # on the wrong row, and this one removes the session every filter
                # in the app offers.
                #
                # The two refusals are enforced in db.py rather than by hiding the
                # button, because the rules depend on live state (is this still
                # the only session? is it still the default?) that a render-time
                # check and the eventual click could disagree about.
                if not is_cur_def and len(sessions) > 1:
                    _pending = f"delete_session_{sess}"
                    if st.session_state.get(_pending):
                        _n = count_session_submissions(sess)
                        st.warning(
                            f"Delete academic session '{sess}'? It will no longer be "
                            "offered as a filter anywhere in the app."
                            + (f" Its {_n} submission(s) are kept and remain counted "
                               f"under {ALL_SESSIONS_LABEL}." if _n else ""),
                            icon=":material/warning:",
                        )
                        _c1, _c2 = st.columns(2)
                        with _c1:
                            if st_compat.button(
                                "Yes, delete it", key=f"{_pending}_yes",
                                type="primary", use_container_width=True,
                            ):
                                ok, msg = delete_academic_session(
                                    sess, admin_username, confirmed=True)
                                st.session_state.pop(_pending, None)
                                if ok:
                                    st.session_state["flash_message"] = msg
                                    st.session_state["flash_kind"] = "success"
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with _c2:
                            if st_compat.button(
                                "Cancel", key=f"{_pending}_no", use_container_width=True,
                            ):
                                st.session_state.pop(_pending, None)
                                st.rerun()
                    elif st_compat.button(
                        f"Delete '{sess}'", key=f"{_pending}_ask",
                        icon=":material/delete:", use_container_width=True,
                    ):
                        st.session_state[_pending] = True
                        st.rerun()

        with col_right:
            st.markdown(f'<div style="font-size:.78rem;font-weight:700;color:var(--text-1);margin-bottom:.5rem;">{i("plus-circle", 13)} Create New Session</div>', unsafe_allow_html=True)
            with st.form("create_new_session_form"):
                new_sess_name = st.text_input(
                    "Session Identifier",
                    placeholder="e.g. 2026/2027",
                    help="Enter standard university session format like 2026/2027",
                )
                new_semester = st.selectbox(
                    "Active semester for this session",
                    SEMESTERS,
                    index=0,
                    help="Students may only give feedback for this semester. You can switch it later "
                         "from the session list on the left.",
                )
                set_as_default = st.checkbox("Set as active default session", value=False)
                submitted = st_compat.form_submit_button("Create Session →", type="primary", use_container_width=True)
                if submitted:
                    if not new_sess_name.strip():
                        st.error("Please provide a valid session name.")
                    else:
                        ok, msg = create_academic_session(
                            new_sess_name.strip(), admin_username, set_as_default,
                            active_semester=new_semester,
                        )
                        if ok:
                            st_compat.toast(msg, icon=":material/check_circle:")
                            st.rerun()
                        else:
                            st.error(msg)


def show_full_dashboard(session: str | None = None):
    # Was a bare "All Sessions", which is not the label any other page uses for
    # the same filter — the admin saw two spellings of one control depending on
    # where they were, and neither was what db.load_data's canonical spelling is.
    active_sess = session or ALL_SESSIONS_LABEL
    page_header("search", "Full Dashboard",
                f"Granular departmental analytics, cross-category visualisations, and submission records ({active_sess}).",
                badge_text=f"Admin View · {active_sess}")

    # A session action (create, set active, set semester, delete) parks its
    # result here and reruns. Without consuming it on THIS page, the message sat
    # in session_state until the administrator next loaded the login screen —
    # the action appeared to do nothing but change a badge. Popped, not read, so
    # a single action produces a single banner.
    _flash = st.session_state.pop("flash_message", None)
    if _flash:
        getattr(st, st.session_state.pop("flash_kind", "success"))(_flash)

    df = load_data(session=active_sess)
    if df.empty:
        empty_state("inbox", f"No Data For {active_sess}", "Try selecting a different academic session or creating new responses.")
        # The session manager must stay reachable on an empty database: it is
        # what creates the sessions that will one day hold data, and gating it
        # behind "has data" strands a fresh deployment with no way to begin.
        _render_session_manager(st.session_state.get("username", "admin"))
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1: html_metric("inbox", len(df), "Total Responses", "blue", badge="Volume")
    with c2: html_metric("star", round(df["rating"].mean(), 1), "Avg Rating", "gold", delta="Benchmark: ≥ 4.0 / 5.0", badge="Score")
    with c3: html_metric("users", df["username"].nunique(), "Unique Respondents", "green", delta=f"{df['category'].nunique()} of {len(CATEGORIES)} Categories", badge="Turnout")
    with c4: html_metric("folder", df["category"].nunique(), "Active Categories", "purple", badge="Coverage")

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

    sentiments = df["effective_sentiment"]
    total_pos, total_neg = sentiments.eq("Positive").sum(), sentiments.eq("Negative").sum()
    st.markdown(
        f'<div class="stat-row">'
        f'<div class="stat-pill">{i("smile", 14, "#059669")} Positive: <strong>{total_pos}</strong></div>'
        f'<div class="stat-pill">{i("frown", 14, "#dc2626")} Negative: <strong>{total_neg}</strong></div>'
        f'<div class="stat-pill">{i("calendar", 14)} Latest: <strong>{str(df["timestamp"].max())[:10] if not df.empty else "—"}</strong></div>'
        f'<div class="stat-pill">{i("bar-chart", 14)} Avg Score: <strong>{round(df["rating"].mean(),2)}/5.0</strong></div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    tab_analytics, tab_targets, tab_drilldown, tab_admin = st.tabs([
        "Executive Analytics & Trends",
        "Action Targets (Lecturers, Courses & Facilities)",
        "Structured Feedback Drilldowns",
        "Sessions & Administration",
    ])

    with tab_analytics:
        st.markdown(
            f'<div class="tab-intro-card">'
            f'<div class="tab-intro-text">'
            f'<strong>Executive Analytics:</strong> Cross-category ratings, sentiment distribution, and student participation for <strong>{esc(active_sess)}</strong>.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        section_header("trending-up", "Distribution & Overview")
        c1, c2 = st.columns(2)
        with c1:
            chart_card("Overall Rating Distribution", "bar-chart", make_rating_bar(df, ""))
        with c2:
            chart_card("Category Overview", "radar", make_category_radar(df))

        c3, c4 = st.columns(2)
        with c3:
            chart_card("Sentiment Analysis", "smile", make_sentiment_pie(df))
        with c4:
            chart_card("By Student Level", "graduation-cap", make_level_pie(df))

        st.markdown("<div style='height:.3rem;'></div>", unsafe_allow_html=True)
        chart_card("Rating Trend Over Time", "chart-bar", make_trend_bar(df))

        st.markdown("<div style='height:.3rem;'></div>", unsafe_allow_html=True)
        section_header("folder", "Per-Category Breakdown")

        for cat in CATEGORIES:
            sub = df[df["category"] == cat]
            if sub.empty:
                continue
            avg, cnt = round(sub["rating"].mean(), 1), len(sub)
            sents = sub["effective_sentiment"]
            top_s = sents.value_counts().idxmax() if not sents.empty else "Neutral"
            sent_clr = sentiment_color(top_s)
            rating_clr = "#059669" if avg >= 4 else "#d97706" if avg >= 3 else "#dc2626"

            ctx_extras = []
            for _, row in sub.iterrows():
                ctx = parse_context(row.get("context_data"))
                if cat == "Course Content" and ctx.get("course_rated"):
                    ctx_extras.extend(context_text_list(ctx["course_rated"]))
                elif cat == "Facilities" and ctx.get("facilities_flagged"):
                    ctx_extras.extend(context_text_list(ctx["facilities_flagged"]))
                elif cat == "Curriculum" and ctx.get("missing_topics"):
                    ctx_extras.extend(context_text_list(ctx["missing_topics"]))
                elif cat == "Lecturer Teaching Style" and ctx.get("challenges"):
                    ctx_extras.extend(context_text_list(ctx["challenges"]))

            top_ctx = ""
            if ctx_extras:
                most_common = Counter(ctx_extras).most_common(1)
                if most_common:
                    top_ctx = (
                        f' · Most flagged: <em style="color:#3b82f6;">'
                        f'{esc(most_common[0][0])}</em>'
                    )

            meter_pct = min(100, max(0, int(round((avg / 5.0) * 100))))
            fill_style = f"width:{meter_pct}%;background:{rating_clr};"
            st.markdown(
                f'<div class="cat-breakdown-row">'
                f'<div class="cat-breakdown-icon-wrap">{i(CAT_META[cat]["icon"], 18, "#3b82f6")}</div>'
                f'<div class="cat-breakdown-info">'
                f'<div class="cat-breakdown-name">{cat}</div>'
                f'<div class="cat-breakdown-count">{cnt} response{"s" if cnt != 1 else ""}{top_ctx}</div>'
                f'<div class="cat-meter-track"><div class="cat-meter-fill" style="{fill_style}"></div></div>'
                f'</div>'
                f'<div class="cat-breakdown-stats">'
                f'<div class="cat-breakdown-rating" style="color:{rating_clr};">{avg} / 5.0</div>'
                f'<div class="cat-breakdown-sent" style="color:{sent_clr};">{i(sentiment_icon(top_s), 12, sent_clr)} {top_s}</div>'
                f"</div></div>",
                unsafe_allow_html=True,
            )

    with tab_targets:
        st.markdown(
            f'<div class="tab-intro-card">'
            f'<div class="tab-intro-text">'
            f'<strong>Priority Targets:</strong> Specific lecturers who need advisory support, courses requiring syllabus rework, and facilities needing urgent repair.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        section_header("target", "Who & What Needs Attention")
        st.caption(
            "The three decisions this system exists to inform: which lecturer to "
            "advise, which course to rework, and what to repair first. Each uses the "
            "structured answers students selected rather than free text, so the "
            "figures are counts of what was ticked."
        )
        render_lecturer_targets(session=session or ALL_SESSIONS_LABEL)
        st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
        render_course_targets(session=session or ALL_SESSIONS_LABEL)
        st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
        render_facility_targets(session=session or ALL_SESSIONS_LABEL)

        html_alert(
            "For full urgency analysis, policy recommendations, and the Action Plan Matrix, visit the <strong>Decision Insights</strong> portal.",
            "info", raw=True,
        )

    with tab_drilldown:
        st.markdown(
            f'<div class="tab-intro-card">'
            f'<div class="tab-intro-text">'
            f'<strong>Granular Feedback Aggregations:</strong> Structured checklists and student preference distributions across all four departmental categories.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        section_header("microscope", "Structured Feedback Aggregations")

        with st.expander("Course Content — Top emphasis areas requested"):
            sub = df[df["category"] == "Course Content"]
            if sub.empty:
                st.write("No data yet.")
            else:
                all_areas, courses_seen = [], []
                for _, row in sub.iterrows():
                    ctx = parse_context(row.get("context_data"))
                    all_areas.extend(context_text_list(ctx.get("emphasis_areas"), limit=40))
                    courses_seen.extend(context_text_list(ctx.get("course_rated")))
                if all_areas:
                    st_compat.dataframe(pd.DataFrame(Counter(all_areas).most_common(), columns=["Emphasis Area", "Votes"]),
                                 use_container_width=True, hide_index=True)
                if courses_seen:
                    st.markdown(f"**Courses rated:** {', '.join(set(courses_seen))}")

        with st.expander("Teaching Style — Most flagged challenges"):
            sub = df[df["category"] == "Lecturer Teaching Style"]
            if sub.empty:
                st.write("No data yet.")
            else:
                all_challenges, all_methods = [], []
                for _, row in sub.iterrows():
                    ctx = parse_context(row.get("context_data"))
                    all_challenges.extend(context_text_list(ctx.get("challenges"), limit=40))
                    all_methods.extend(context_text_list(ctx.get("effective_methods"), limit=40))
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Top challenges:**")
                    if all_challenges:
                        st_compat.dataframe(pd.DataFrame(Counter(all_challenges).most_common(), columns=["Challenge", "Count"]),
                                     use_container_width=True, hide_index=True)
                with col2:
                    st.markdown("**Most preferred methods:**")
                    if all_methods:
                        st_compat.dataframe(pd.DataFrame(Counter(all_methods).most_common(), columns=["Method", "Count"]),
                                     use_container_width=True, hide_index=True)

        with st.expander("Facilities — Most reported issues"):
            sub = df[df["category"] == "Facilities"]
            if sub.empty:
                st.write("No data yet.")
            else:
                all_fac, urgency_list = [], []
                for _, row in sub.iterrows():
                    ctx = parse_context(row.get("context_data"))
                    all_fac.extend(context_text_list(ctx.get("facilities_flagged"), limit=40))
                    urgency_list.extend(context_text_list(ctx.get("urgency")))
                if all_fac:
                    st_compat.dataframe(pd.DataFrame(Counter(all_fac).most_common(), columns=["Facility", "Reports"]),
                                 use_container_width=True, hide_index=True)
                if urgency_list:
                    _urg_counts = Counter(urgency_list).most_common()
                    _urg_top, _urg_top_n = _urg_counts[0]
                    st.markdown("**Urgency level reported:**")
                    st_compat.dataframe(
                        pd.DataFrame([{"Urgency level": lvl, "Students": n}
                                      for lvl, n in _urg_counts], columns=["Urgency level", "Students"]),
                        use_container_width=True, hide_index=True)
                    _urg_split = ", ".join(
                        f"{lvl.split('—')[0].strip()} {n}" for lvl, n in _urg_counts)
                    st.caption(
                        f"Most common: {_urg_top} ({_urg_top_n} of {len(urgency_list)} "
                        f"responses). Full split — {_urg_split}."
                    )

        with st.expander("Curriculum — Gaps & outdated areas"):
            sub = df[df["category"] == "Curriculum"]
            if sub.empty:
                st.write("No data yet.")
            else:
                all_missing, all_outdated, align_list = [], [], []
                for _, row in sub.iterrows():
                    ctx = parse_context(row.get("context_data"))
                    all_missing.extend(context_text_list(ctx.get("missing_topics"), limit=40))
                    all_outdated.extend(context_text_list(ctx.get("outdated_areas"), limit=40))
                    align_list.extend(context_text_list(ctx.get("industry_alignment")))
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Most requested missing topics:**")
                    if all_missing:
                        st_compat.dataframe(pd.DataFrame(Counter(all_missing).most_common(), columns=["Topic", "Votes"]),
                                     use_container_width=True, hide_index=True)
                with col2:
                    st.markdown("**Most flagged outdated areas:**")
                    if all_outdated:
                        st_compat.dataframe(pd.DataFrame(Counter(all_outdated).most_common(), columns=["Area", "Votes"]),
                                     use_container_width=True, hide_index=True)
                if align_list:
                    _ALIGN_SCALE = ["Very Poor", "Poor", "Moderate", "Good", "Excellent"]
                    _align_counts = Counter(align_list)
                    _align_mean = (
                        sum(_ALIGN_SCALE.index(v) + 1 for v in align_list if v in _ALIGN_SCALE)
                        / max(1, sum(1 for v in align_list if v in _ALIGN_SCALE))
                    )
                    _align_top, _align_top_n = _align_counts.most_common(1)[0]
                    _align_idx = int(_align_mean - 0.5) + 1
                    _align_idx = max(1, min(len(_ALIGN_SCALE), _align_idx))
                    st.markdown("**Industry alignment perception:**")
                    st_compat.dataframe(
                        pd.DataFrame([{"Rating": lvl, "Students": n}
                                      for lvl, n in sorted(_align_counts.items(),
                                                           key=lambda kv: _ALIGN_SCALE.index(kv[0])
                                                           if kv[0] in _ALIGN_SCALE else 99)],
                                      columns=["Rating", "Students"]),
                        use_container_width=True, hide_index=True)
                    st.caption(
                        f"Average {_align_mean:.2f} of {len(_ALIGN_SCALE)} → "
                        f"**{_ALIGN_SCALE[_align_idx - 1]}** "
                        f"({len(align_list)} responses). "
                        f"Most common answer: {_align_top} ({_align_top_n})."
                    )

    with tab_admin:
        st.markdown(
            f'<div class="tab-intro-card">'
            f'<div class="tab-intro-text">'
            f'<strong>Administrative & System Controls:</strong> Manage academic sessions, active semesters, rating sentiment overrides, and data exports.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Academic Session Manager
        _render_session_manager(st.session_state.get("username", "admin"))
        st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

        # ── Sentiment Engine Section ──
        section_header("flask", "How Sentiment Is Decided")

        status = engine_status()
        _render_engine_status_card(status)

        corrected_count = int((df["admin_corrected_sentiment"].notna()).sum()) if "admin_corrected_sentiment" in df.columns else 0
        with st.expander(f"Review & override sentiment labels ({corrected_count} overridden so far)"):
            st.caption(
                f"The band on every submission comes from its rating, so there is nothing to "
                f"correct in the normal case. An override is for the rare record where the rating "
                f"and the structured answers plainly disagree — a 5-star rating on a submission that "
                f"flags every delivery challenge, for instance. It is recorded against the row and "
                f"takes precedence over the rating on every chart and export. "
                f"{corrected_count} of {len(df)} record(s) currently carry one."
            )
            review_df = df[["id", "category", "rating", "effective_sentiment"]].copy()
            review_df = review_df.rename(columns={"effective_sentiment": "sentiment"})
            edited = st_compat.data_editor(
                review_df,
                use_container_width=True,
                hide_index=True,
                disabled=["id", "category"],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "rating": st.column_config.NumberColumn("Rating", width="small"),
                    "sentiment": st.column_config.SelectboxColumn(
                        "Sentiment", options=["Positive", "Neutral", "Negative"], required=True,
                    ),
                },
                key="sentiment_review_editor",
            )
            if st_compat.button("Save corrections", icon=":material/save:", type="primary"):
                changes = edited.merge(review_df, on="id", suffixes=("_new", "_old"))
                changed_rows = changes[changes["sentiment_new"] != changes["sentiment_old"]]
                for _, r in changed_rows.iterrows():
                    correct_sentiment(int(r["id"]), r["sentiment_new"], st.session_state.get("username", "admin"))
                if len(changed_rows):
                    st.success(f"Saved {len(changed_rows)} correction(s).")
                    st.rerun()
                else:
                    st.info("No changes to save.")

        st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
        section_header("database", "Data Records & Exports")

        st_compat.download_button(
            "Export raw data (CSV)", data=df.to_csv(index=False).encode("utf-8"),
            file_name="futo_feedback_export.csv", mime="text/csv",
            icon=":material/download:", use_container_width=False, type="primary",
        )
        st.markdown("<div style='height:.3rem;'></div>", unsafe_allow_html=True)
        with st.expander("View Raw Data Table"):
            st_compat.dataframe(df.reset_index(drop=True), use_container_width=True, hide_index=True)
