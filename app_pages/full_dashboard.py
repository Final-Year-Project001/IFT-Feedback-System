"""app_pages/full_dashboard.py — deep-dive admin analytics + structured aggregations."""

from collections import Counter

import pandas as pd
import streamlit as st

import st_compat

from config import CATEGORIES, CAT_META, CURRENT_SESSION, MIN_TRAINING_SAMPLES, ALL_SESSIONS_LABEL
from db import (
    load_data, parse_context, context_text_list, correct_sentiment,
    get_academic_sessions, get_active_session, create_academic_session,
    set_default_session, get_session_stats,
    delete_academic_session, count_session_submissions,
)
from charts import make_rating_bar, make_category_radar, make_sentiment_pie, make_level_pie, make_trend_line
from components import html_metric, page_header, section_header, empty_state, esc, html_alert
from icons import i, sentiment_icon, sentiment_color
from sentiment import engine_status, analyze_sentiment


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
    """Renders the premium engine status card with all diagnostics."""
    is_trained = status["trained_model_available"]
    is_vader = status["vader_available"]
    meta = status.get("trained_model_meta") or {}

    # Active engine pill
    problems = status.get("engine_problems") or []
    if problems:
        # A degraded engine must not be dressed up in the healthy green pill.
        engine_color = "#d97706"
        engine_bg = "rgba(217,119,6,.08)"
        engine_border = "rgba(217,119,6,.25)"
        engine_dot = "#f59e0b"
        engine_label = f"Degraded — {esc(status.get('engine_name', 'unavailable'))}"
        engine_icon_name = "alert-triangle"
    elif is_trained:
        engine_color = "#059669"
        engine_bg = "rgba(5,150,105,.08)"
        engine_border = "rgba(5,150,105,.25)"
        engine_dot = "#10b981"
        engine_label = esc(status.get("active_engine", "Supervised Classifier"))
        engine_icon_name = "cpu"
    elif is_vader:
        engine_color = "#2563eb"
        engine_bg = "rgba(37,99,235,.08)"
        engine_border = "rgba(37,99,235,.25)"
        engine_dot = "#3b82f6"
        engine_label = "VADER Academic Pro"
        engine_icon_name = "zap"
    else:
        engine_color = "#dc2626"
        engine_bg = "rgba(220,38,38,.06)"
        engine_border = "rgba(220,38,38,.2)"
        engine_dot = "#ef4444"
        engine_label = "Unavailable"
        engine_icon_name = "alert-circle"

    # Metric values
    lex_count = esc(status.get("domain_lexicon_terms", 0))
    mwe_count = esc(status.get("mwe_rules_count", 0))
    neg_count = esc(status.get("negation_tokens", 0))
    intens_count = esc(status.get("intensifier_tokens", 0))
    # These two lines used to be, in order:
    #     conf_range = esc(status.get("confidence_range", ""))
    #     conf_range = status.get("confidence_range", "48% – 99%")
    # The second overwrote the first, so the escape was thrown away and the
    # unescaped value was interpolated into `unsafe_allow_html` below. The
    # default also only applied when the KEY was absent, not when the value
    # was None — `esc(None)` renders the literal text "None".
    _conf_raw = status.get("confidence_range")
    conf_range = esc(_conf_raw) if _conf_raw else "48% &ndash; 99%"

    # Trained model extra stats
    trained_meta_html = ""
    if is_trained and meta:
        # Guarded: these come from a pickle on disk, and a model trained by an
        # older build (or hand-edited) can be missing any of these keys, hold
        # a string, or hold None. `{acc:.0%}` raises TypeError on a str and
        # ValueError on None, and the whole page died with it.
        acc = _as_float(meta.get("accuracy"))
        f1 = _as_float(meta.get("macro_f1"))
        n_samp = esc(meta.get("n_samples", "?"))
        trained_at = esc(str(meta.get("trained_at", "?"))[:10])
        acc_txt = esc(f"{acc:.0%}") if acc is not None else "—"
        f1_txt = esc(f"{f1:.0%}") if f1 is not None else "—"
        trained_meta_html = f"""
        <div class="engine-trained-row">
            <div class="engine-trained-stat">
                <div class="engine-trained-val" style="color:#059669;">{acc_txt}</div>
                <div class="engine-trained-lbl">Test Accuracy</div>
            </div>
            <div class="engine-trained-stat">
                <div class="engine-trained-val" style="color:#7c3aed;">{f1_txt}</div>
                <div class="engine-trained-lbl">Macro F1</div>
            </div>
            <div class="engine-trained-stat">
                <div class="engine-trained-val" style="color:#0891b2;">{n_samp}</div>
                <div class="engine-trained-lbl">Training Samples</div>
            </div>
            <div class="engine-trained-stat">
                <div class="engine-trained-val" style="color:#d97706;font-size:.75rem;">{trained_at}</div>
                <div class="engine-trained-lbl">Last Trained</div>
            </div>
        </div>"""

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
                {i("shield", 13, "#7c3aed")} Confidence Range: <strong>{conf_range}</strong>
            </div>
        </div>
        <div class="engine-metrics-row">
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#2563eb;">{lex_count}</div>
                <div class="engine-metric-lbl">{i("book-open", 11, "#94a3b8")} Domain Lexicon</div>
            </div>
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#7c3aed;">{mwe_count}</div>
                <div class="engine-metric-lbl">{i("git-merge", 11, "#94a3b8")} MWE Rules</div>
            </div>
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#dc2626;">{neg_count}</div>
                <div class="engine-metric-lbl">{i("slash", 11, "#94a3b8")} Negation Tokens</div>
            </div>
            <div class="engine-metric-box">
                <div class="engine-metric-val" style="color:#d97706;">{intens_count}</div>
                <div class="engine-metric-lbl">{i("zap", 11, "#94a3b8")} Intensifiers</div>
            </div>
        </div>
        {trained_meta_html}
        {"".join(
            f'<div class="engine-error-pill">{i("alert-triangle", 13, "#dc2626")} {esc(str(p)[:140])}</div>'
            for p in status.get("engine_problems", [])
        )}
    </div>
    """, unsafe_allow_html=True)


def _render_live_preview():
    """Renders the real-time sentiment live preview panel."""
    st.markdown("""
    <div class="live-preview-card">
        <div class="live-preview-header">
            <div style="display:flex;align-items:center;gap:.7rem;">
                <div class="live-preview-icon">⚡</div>
                <div>
                    <div class="live-preview-title">Live Sentiment Preview</div>
                    <div class="live-preview-sub">Type any student comment below to see real-time engine analysis</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    preview_text = st.text_area(
        "Sample comment",
        placeholder="e.g. The practical sessions are very hands-on, but the lab computers are broken and outdated…",
        height=90,
        key="sentiment_live_preview_input",
        label_visibility="collapsed",
    )

    if preview_text and preview_text.strip():
        result = analyze_sentiment(preview_text.strip())
        bd = result.to_dict()

        label_colors = {"Positive": "#059669", "Negative": "#dc2626", "Neutral": "#d97706"}
        label_bgs = {"Positive": "rgba(5,150,105,.08)", "Negative": "rgba(220,38,38,.07)", "Neutral": "rgba(217,119,6,.08)"}
        label_borders = {"Positive": "rgba(5,150,105,.25)", "Negative": "rgba(220,38,38,.2)", "Neutral": "rgba(217,119,6,.2)"}

        lc = label_colors.get(result.label, "#475569")
        lb = label_bgs.get(result.label, "rgba(71,85,105,.06)")
        lbr = label_borders.get(result.label, "rgba(71,85,105,.2)")

        conf_pct = result.confidence_pct
        conf_label = result.confidence_label

        # Polarity bars
        pos_w = round(bd.get("pos", 0) * 100)
        neg_w = round(bd.get("neg", 0) * 100)
        neu_w = max(0, 100 - pos_w - neg_w)

        contrast_html = ""
        if bd.get("contrast_detected"):
            contrast_html = f"""
            <div class="preview-tag" style="background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.25);color:#7c3aed;">
                {i("git-branch", 11, "#7c3aed")} Contrastive clause detected
            </div>"""

        pos_cues_html = ""
        if bd.get("pos_cues"):
            tags = "".join(f'<span class="preview-cue-tag preview-cue-pos">{esc(c)}</span>'
                           for c in bd["pos_cues"][:6])
            pos_cues_html = f'<div class="preview-cues-row">{i("smile", 11, "#059669")} <strong style="color:#059669;font-size:.72rem;">Positive signals:</strong> {tags}</div>'

        neg_cues_html = ""
        if bd.get("neg_cues"):
            tags = "".join(f'<span class="preview-cue-tag preview-cue-neg">{esc(c)}</span>'
                           for c in bd["neg_cues"][:6])
            neg_cues_html = f'<div class="preview-cues-row">{i("frown", 11, "#dc2626")} <strong style="color:#dc2626;font-size:.72rem;">Negative signals:</strong> {tags}</div>'

        st.markdown(f"""
        <div class="preview-result-card">
            <div class="preview-result-top">
                <div class="preview-label-pill" style="background:{lb};border-color:{lbr};color:{lc};">
                    {i(sentiment_icon(result.label), 15, lc)} {result.label}
                </div>
                <div class="preview-conf-wrap">
                    <div class="preview-conf-bar-track">
                        <div class="preview-conf-bar-fill" style="width:{conf_pct}%;background:{lc};"></div>
                    </div>
                    <span class="preview-conf-text">{conf_pct}% confidence · <em>{conf_label}</em></span>
                </div>
                <div class="preview-score-pill">score: <strong>{result.score:+.3f}</strong></div>
            </div>
            <div class="preview-polarity-bars">
                <div class="preview-pol-item">
                    <div class="preview-pol-label" style="color:#059669;">{i("smile",10,"#059669")} Positive</div>
                    <div class="preview-pol-track"><div class="preview-pol-fill" style="width:{pos_w}%;background:#059669;"></div></div>
                    <span class="preview-pol-pct">{pos_w}%</span>
                </div>
                <div class="preview-pol-item">
                    <div class="preview-pol-label" style="color:#94a3b8;">{i("meh",10,"#94a3b8")} Neutral</div>
                    <div class="preview-pol-track"><div class="preview-pol-fill" style="width:{neu_w}%;background:#94a3b8;"></div></div>
                    <span class="preview-pol-pct">{neu_w}%</span>
                </div>
                <div class="preview-pol-item">
                    <div class="preview-pol-label" style="color:#dc2626;">{i("frown",10,"#dc2626")} Negative</div>
                    <div class="preview-pol-track"><div class="preview-pol-fill" style="width:{neg_w}%;background:#dc2626;"></div></div>
                    <span class="preview-pol-pct">{neg_w}%</span>
                </div>
            </div>
            {pos_cues_html}
            {neg_cues_html}
            {contrast_html}
            <div class="preview-engine-tag">{i("cpu", 10, "#94a3b8")} Engine: {esc(result.engine)}</div>
        </div>
        """, unsafe_allow_html=True)
    elif preview_text is not None and preview_text.strip() == "":
        st.markdown(
            '<div class="preview-empty-hint">↑ Type a comment above to see analysis</div>',
            unsafe_allow_html=True
        )


def _render_session_manager(admin_username: str):
    """Renders the Academic Session management panel for administrators."""
    sessions = get_academic_sessions()
    active_def = get_active_session()
    stats = get_session_stats()

    with st.expander("Academic Sessions Management (Create & Set Active Session)"):
        st.markdown(
            '<div style="font-size:.82rem;color:var(--text-2);margin-bottom:.85rem;">'
            "Manage the academic sessions for student feedback collection. Sessions created here immediately reflect across "
            "all student submission portals, administrative filters, and analytics dashboards."
            "</div>",
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns([1.2, 0.8], gap="medium")

        with col_left:
            st.markdown(f'<div style="font-size:.78rem;font-weight:700;color:var(--text-1);margin-bottom:.5rem;">{i("list", 13)} Existing Academic Sessions</div>', unsafe_allow_html=True)
            for sess in sessions:
                s_stat = stats.get(sess, {"total_feedback": 0, "avg_rating": 0.0, "unique_students": 0})
                is_cur_def = (sess == active_def)
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
                    f'</div>'
                    f'<div style="display:flex;align-items:center;gap:.5rem;">{badge_html}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

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
                set_as_default = st.checkbox("Set as active default session", value=False)
                submitted = st_compat.form_submit_button("Create Session →", type="primary", use_container_width=True)
                if submitted:
                    if not new_sess_name.strip():
                        st.error("Please provide a valid session name.")
                    else:
                        ok, msg = create_academic_session(new_sess_name.strip(), admin_username, set_as_default)
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

    # Render Academic Session Manager
    _render_session_manager(st.session_state.get("username", "admin"))
    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

    df = load_data(session=active_sess)
    if df.empty:
        empty_state("inbox", f"No Data For {active_sess}", "Try selecting a different academic session or creating new responses.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1: html_metric("inbox", len(df), "Total Responses", "blue")
    with c2: html_metric("star", round(df["rating"].mean(), 1), "Avg Rating", "gold")
    with c3: html_metric("users", df["username"].nunique(), "Unique Respondents", "green")
    with c4: html_metric("folder", df["category"].nunique(), "Active Categories", "purple")

    # ── Export ──
    st_compat.download_button(
        "Export raw data (CSV)", data=df.to_csv(index=False).encode("utf-8"),
        file_name="futo_feedback_export.csv", mime="text/csv",
        icon=":material/download:", use_container_width=False, type="primary",
    )

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

    section_header("trending-up", "Distribution & Overview")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="chart-wrap"><div class="chart-title">{i("bar-chart", 13)} Overall Rating Distribution</div>', unsafe_allow_html=True)
        fig = make_rating_bar(df, "Rating Distribution")
        if fig: st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="chart-wrap"><div class="chart-title">{i("radar", 13)} Category Overview (Radar)</div>', unsafe_allow_html=True)
        fig = make_category_radar(df)
        if fig: st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown(f'<div class="chart-wrap"><div class="chart-title">{i("smile", 13)} Sentiment Analysis</div>', unsafe_allow_html=True)
        fig = make_sentiment_pie(df)
        if fig: st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="chart-wrap"><div class="chart-title">{i("graduation-cap", 13)} By Student Level</div>', unsafe_allow_html=True)
        fig = make_level_pie(df)
        if fig: st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    fig = make_trend_line(df)
    if fig:
        st.markdown("<div style='height:.3rem;'></div>", unsafe_allow_html=True)
        section_header("trending-down", "Rating Trend Over Time")
        st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        st_compat.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

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
                # `context_data` is a JSON blob in the feedback row, and the
                # course/emphasis/facility strings inside it are not restricted
                # to the option lists in config.py — anything a client can post
                # ends up here. Rendered unescaped into an
                # unsafe_allow_html block, one `<img onerror=…>` in a course
                # name executed in every admin's browser.
                top_ctx = (
                    f' · Most flagged: <em style="color:#3b82f6;">'
                    f'{esc(most_common[0][0])}</em>'
                )

        st.markdown(
            f'<div class="cat-breakdown-row">'
            f'<div class="cat-breakdown-icon-wrap">{i(CAT_META[cat]["icon"], 18, "#3b82f6")}</div>'
            f'<div class="cat-breakdown-info"><div class="cat-breakdown-name">{cat}</div>'
            f'<div class="cat-breakdown-count">{cnt} response{"s" if cnt != 1 else ""}{top_ctx}</div></div>'
            f'<div class="cat-breakdown-stats">'
            f'<div class="cat-breakdown-rating" style="color:{rating_clr};">{avg}</div>'
            f'<div class="cat-breakdown-sent" style="color:{sent_clr};">{i(sentiment_icon(top_s), 12, sent_clr)} {top_s}</div>'
            f"</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
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
                # The full distribution, not just the winner. A single headline
                # figure hid the disagreement that actually makes a facilities
                # problem actionable — a 40/30/30 split across urgency levels
                # reads very differently from one flat 70% top answer, and an
                # admin acting on "Moderate" alone would under-react to the
                # students who said "Critical".
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
                # This was labelled "Average industry alignment perception" but
                # computed `Counter(...).most_common(1)[0][0]`, which is the
                # MODE, not the average. On an ordinal 1-5 scale that is a
                # materially different and much less useful number: a set of
                # answers of [Very Poor, Poor, Poor, Poor, Excellent] reports
                # "Poor" either way, but [Poor, Poor, Poor, Excellent,
                # Excellent] reports "Poor" as a mode and would have been
                # dragged to "Moderate" as a mean. The mean is what the label
                # claims and what a departmental decision needs, so the mean is
                # what is computed — with the mode kept alongside it, because
                # the mode is what students actually said.
                _ALIGN_SCALE = ["Very Poor", "Poor", "Moderate", "Good", "Excellent"]
                _align_counts = Counter(align_list)
                _align_mean = (
                    sum(_ALIGN_SCALE.index(v) + 1 for v in align_list if v in _ALIGN_SCALE)
                    / max(1, sum(1 for v in align_list if v in _ALIGN_SCALE))
                )
                _align_top, _align_top_n = _align_counts.most_common(1)[0]
                # Round to the nearest whole scale point for a plain-language
                # reading. `round` is banker's rounding, so nudge halves up
                # explicitly rather than let 3.5 become 4 by luck of parity.
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

    # ── Sentiment Engine Section ──────────────────────────────────────
    section_header("flask", "Sentiment Engine — Improve Accuracy")

    status = engine_status()
    _render_engine_status_card(status)

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    _render_live_preview()

    corrected_count = int((df["admin_corrected_sentiment"].notna()).sum()) if "admin_corrected_sentiment" in df.columns else 0
    with st.expander(f"Review & correct sentiment labels ({corrected_count} corrected so far)"):
        st.caption(
            f"Correcting mislabeled comments here builds the training set for a classifier tuned to this "
            f"department's own feedback language. Once {MIN_TRAINING_SAMPLES}+ comments are corrected, run "
            f"`python train_model.py` from the project folder to train it — see SETUP_GUIDE.md."
        )
        review_df = df[["id", "category", "comment", "effective_sentiment"]].copy()
        review_df = review_df[review_df["comment"].fillna("").str.strip() != ""]
        review_df = review_df.rename(columns={"effective_sentiment": "sentiment"})
        edited = st_compat.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            disabled=["id", "category", "comment"],
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "comment": st.column_config.TextColumn("Comment", width="large"),
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

    st.markdown("<div style='height:.3rem;'></div>", unsafe_allow_html=True)
    with st.expander("View Raw Data Table"):
        st_compat.dataframe(df.reset_index(drop=True), use_container_width=True, hide_index=True)
