"""
app_pages/feedback_form.py
-----------------------
Category-specific context panels (rendered *outside* st.form so the
checkboxes stay interactive) plus the shared rating+comment form and the
"already submitted" read-only summary view.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

import st_compat

from config import (
    CAT_META, CATEGORIES, COURSE_CONTENT_EMPHASIS_AREAS, TEACHING_STYLE_METHODS,
    TEACHING_STYLE_CHALLENGES, FACILITIES_ITEMS, CURRICULUM_ALIGNMENT_AREAS,
    CURRICULUM_OUTDATED_AREAS, CURRENT_SESSION, courses_for_level,
    courses_for_level_semester, SEMESTERS,
)
from db import load_data, save_data, parse_context, filter_by_username
from sentiment import analyze_sentiment
from email_service import is_email_configured, send_submission_email, send_completion_email
from components import (
    html_alert, html_metric, page_header, section_header, render_tag_list, star_row, esc,
)
from icons import i, sentiment_icon, sentiment_color


# ══════════════════════════════════════════════════════════════
#  CATEGORY-SPECIFIC CONTEXT PANELS
# ══════════════════════════════════════════════════════════════

def render_course_content_context(level: str):
    st.markdown(
        f'<div class="context-panel"><div class="context-panel-title">{i("course", 15)} Course & Content Focus</div></div>',
        unsafe_allow_html=True,
    )
    level_label = f"{level} Level" if level and level != "Staff" else "your"

    st.markdown(f'<div class="form-section-label">{i("calendar", 13)} Which semester are you rating?</div>',
                unsafe_allow_html=True)
    semester = st.radio(
        "Semester", SEMESTERS, key="ctx_semester_select", horizontal=True, label_visibility="collapsed",
        help="Harmattan and Rain semester courses are different — pick the one your course was taught in.",
    )

    course_options = courses_for_level_semester(level, semester)
    course = st.selectbox(
        "Which course are you rating?", course_options, key=f"ctx_course_select_{semester}",
        help=f"Showing {semester} semester courses from the {level_label} curriculum "
             f"(Department Handbook §17.0). Pick 'Other / General' if yours isn't listed.",
    )

    st.markdown(
        f'<div class="form-section-label" style="margin-top:1rem;">{i("target", 13)} Areas that need more emphasis</div>'
        '<div class="checkbox-hint">Select all areas you feel deserve greater attention in this course.</div>',
        unsafe_allow_html=True,
    )
    selected_emphasis = []
    cols = st.columns(2)
    for idx, area in enumerate(COURSE_CONTENT_EMPHASIS_AREAS):
        with cols[idx % 2]:
            if st.checkbox(area, key=f"ctx_emph_{idx}"):
                selected_emphasis.append(area)

    return {
        "semester": semester,
        "course_rated": course if course != "Select a course…" else "",
        "emphasis_areas": selected_emphasis,
    }


def render_teaching_style_context(level: str):
    st.markdown(
        f'<div class="context-panel"><div class="context-panel-title">{i("teaching", 15)} Teaching Methods & Experience</div></div>',
        unsafe_allow_html=True,
    )
    lecturer_name = st.text_input("Lecturer / Course Instructor",
                                   placeholder="e.g. Dr. Obi, Prof. Eze",
                                   key="ctx_lecturer_name")
    course_options = courses_for_level(level)
    course_code = st.selectbox(
        "Course (optional)", course_options, key="ctx_course_code",
        help="Optional — pick the specific course this feedback is about, from your level's curriculum.",
    )

    st.markdown(
        f'<div class="form-section-label" style="margin-top:1rem;">{i("check", 13)} Teaching methods you find most effective</div>'
        '<div class="checkbox-hint">Select the approaches that improve your learning experience.</div>',
        unsafe_allow_html=True,
    )
    selected_methods = []
    cols = st.columns(2)
    for idx, method in enumerate(TEACHING_STYLE_METHODS):
        with cols[idx % 2]:
            if st.checkbox(method, key=f"ctx_method_{idx}"):
                selected_methods.append(method)

    st.markdown(
        f'<div class="form-section-label" style="margin-top:1.2rem;">{i("alert-triangle", 13)} Challenges you have encountered</div>'
        '<div class="checkbox-hint">Identify delivery issues that have negatively affected your learning.</div>',
        unsafe_allow_html=True,
    )
    selected_challenges = []
    cols2 = st.columns(2)
    for idx, challenge in enumerate(TEACHING_STYLE_CHALLENGES):
        with cols2[idx % 2]:
            if st.checkbox(challenge, key=f"ctx_challenge_{idx}"):
                selected_challenges.append(challenge)

    return {
        "lecturer_name": lecturer_name.strip(),
        "course_code": course_code if course_code != "Select a course…" else "",
        "effective_methods": selected_methods,
        "challenges": selected_challenges,
    }


def render_facilities_context(level: str):
    # `level` is accepted (but intentionally unused) purely so every
    # context renderer shares one call signature for _CONTEXT_RENDERERS
    # below. Facilities feedback is deliberately general — a broken
    # projector or unstable power supply affects every level equally,
    # so this category is never filtered by academic level.
    st.markdown(
        f'<div class="context-panel"><div class="context-panel-title">{i("facilities", 15)} Facilities Requiring Attention</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="form-section-label">{i("wrench", 13)} Which facilities need immediate attention?</div>'
        '<div class="checkbox-hint">Select all infrastructure items that require improvement or repair.</div>',
        unsafe_allow_html=True,
    )
    selected_facilities = []
    cols = st.columns(2)
    for idx, item in enumerate(FACILITIES_ITEMS):
        with cols[idx % 2]:
            if st.checkbox(item, key=f"ctx_fac_{idx}"):
                selected_facilities.append(item)

    st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
    urgency = st.select_slider(
        "Overall urgency level of facilities issues",
        options=["Low — Minor inconvenience", "Moderate — Affects learning",
                 "High — Seriously disrupts studies", "Critical — Immediate action required"],
        value="Moderate — Affects learning", key="ctx_fac_urgency",
    )
    location = st.text_input("Specific location / building (optional)",
                              placeholder="e.g. IFT Lab 1, Block C Classroom, Library annex…",
                              key="ctx_fac_location")

    return {"facilities_flagged": selected_facilities, "urgency": urgency, "location": location.strip()}


def render_curriculum_context(level: str):
    # Same reasoning as render_facilities_context above: curriculum
    # feedback is about the shape of the whole programme, not any one
    # level's coursework, so it stays general on purpose.
    st.markdown(
        f'<div class="context-panel"><div class="context-panel-title">{i("curriculum", 15)} Curriculum Alignment & Gaps</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="form-section-label">{i("rocket", 13)} Topics/skills missing from the current curriculum</div>'
        '<div class="checkbox-hint">Select emerging areas you feel should be incorporated into the IFT programme.</div>',
        unsafe_allow_html=True,
    )
    selected_missing = []
    cols = st.columns(2)
    for idx, topic in enumerate(CURRICULUM_ALIGNMENT_AREAS):
        with cols[idx % 2]:
            if st.checkbox(topic, key=f"ctx_curr_miss_{idx}"):
                selected_missing.append(topic)

    st.markdown(
        f'<div class="form-section-label" style="margin-top:1.2rem;">{i("refresh", 13)} Areas that appear outdated or need restructuring</div>'
        '<div class="checkbox-hint">Flag curriculum sections that no longer reflect current industry or academic standards.</div>',
        unsafe_allow_html=True,
    )
    selected_outdated = []
    cols2 = st.columns(2)
    for idx, area in enumerate(CURRICULUM_OUTDATED_AREAS):
        with cols2[idx % 2]:
            if st.checkbox(area, key=f"ctx_curr_old_{idx}"):
                selected_outdated.append(area)

    industry_align = st.select_slider(
        "How well does the current curriculum align with industry expectations?",
        options=["Very Poor", "Poor", "Moderate", "Good", "Excellent"],
        value="Moderate", key="ctx_curr_align",
    )
    return {
        "missing_topics": selected_missing,
        "outdated_areas": selected_outdated,
        "industry_alignment": industry_align,
    }


# Every renderer takes the student's academic level as its one argument,
# even the two that ignore it — see the comments on those two functions
# for why. A uniform signature keeps this dispatch dict (and the single
# call site in show_feedback_form below) simple.
_CONTEXT_RENDERERS = {
    "Course Content": render_course_content_context,
    "Lecturer Teaching Style": render_teaching_style_context,
    "Facilities": render_facilities_context,
    "Curriculum": render_curriculum_context,
}


# ══════════════════════════════════════════════════════════════
#  MAIN FEEDBACK FORM PAGE
# ══════════════════════════════════════════════════════════════

def _render_already_submitted(category, row, session_name: str = ""):
    # ── Submission confirmation banner ──────────────────────────────
    sess_hint = f" for the <strong>{esc(session_name)}</strong> Academic Session" if session_name else ""
    st.markdown(
        f'<div class="submission-result-card">'
        f'<div class="src-icon">{i("check-circle", 48, "#059669")}</div>'
        f'<h3>Submission Confirmed</h3>'
        f'<p>Your feedback for <strong>{esc(category)}</strong>{sess_hint} has been received and recorded. '
        'Thank you for contributing to the improvement of the Information Technology Department. '
        'A read-only summary of your submission is presented below.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    section_header("bar-chart", "Submission Summary")

    # ── Four metric cards: rating / sentiment / confidence / date ───
    conf_val = row.get("sentiment_confidence")
    if conf_val is not None and pd.notna(conf_val):
        conf_pct = f"{int(float(conf_val) * 100)}%"
    else:
        # Fallback approximation from compound score
        score_f = float(row.get("sentiment_score", 0.0) or 0.0)
        conf_pct = f"{int(min(99, max(52, 55 + abs(score_f) * 40)))}%"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card metric-accent-gold">'
            f'<div class="metric-icon-wrap">{star_row(int(row["rating"]), 16)}</div>'
            f'<div class="metric-value" style="font-size:1.3rem;">{int(row["rating"])}/5</div>'
            f'<div class="metric-label">Your Rating</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        sent = row.get("effective_sentiment", row.get("sentiment", "Neutral"))
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon-wrap">{i(sentiment_icon(sent), 24, sentiment_color(sent))}</div>'
            f'<div class="metric-value" style="font-size:1.3rem;color:{sentiment_color(sent)};">{sent}</div>'
            f'<div class="metric-label">Sentiment Label</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card metric-accent-green">'
            f'<div class="metric-icon-wrap">{i("shield-check", 22, "#059669")}</div>'
            f'<div class="metric-value" style="font-size:1.3rem;color:#059669;">{conf_pct}</div>'
            f'<div class="metric-label">Engine Confidence</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        ts = str(row["timestamp"])[:10] if pd.notna(row["timestamp"]) else "—"
        html_metric("calendar", ts, "Submitted On")

    # ── Structured context responses (info-card) ──────────────────────
    ctx = parse_context(row.get("context_data"))
    if ctx:
        st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
        section_header("folder-open", "Structured Responses You Provided")

        # Build rows of structured data into a clean info-card
        rows_html = ""
        if category == "Course Content":
            if ctx.get("semester"):
                rows_html += f'<div class="detail-row"><strong>Semester</strong><span>{esc(ctx["semester"])}</span></div>'
            if ctx.get("course_rated"):
                rows_html += f'<div class="detail-row"><strong>Course Rated</strong><span>{esc(ctx["course_rated"])}</span></div>'
            if ctx.get("emphasis_areas"):
                tags = render_tag_list(ctx["emphasis_areas"])
                rows_html += f'<div class="detail-row"><strong>Areas Needing More Emphasis</strong><span>{tags}</span></div>'
        elif category == "Lecturer Teaching Style":
            if ctx.get("lecturer_name"):
                rows_html += f'<div class="detail-row"><strong>Lecturer</strong><span>{esc(ctx["lecturer_name"])}</span></div>'
            if ctx.get("course_code"):
                rows_html += f'<div class="detail-row"><strong>Course</strong><span>{esc(ctx["course_code"])}</span></div>'
            if ctx.get("effective_methods"):
                tags = render_tag_list(ctx["effective_methods"], "sub-tag sub-tag-green")
                rows_html += f'<div class="detail-row"><strong>Effective Methods Identified</strong><span>{tags}</span></div>'
            if ctx.get("challenges"):
                tags = render_tag_list(ctx["challenges"], "sub-tag sub-tag-gold")
                rows_html += f'<div class="detail-row"><strong>Challenges Flagged</strong><span>{tags}</span></div>'
        elif category == "Facilities":
            if ctx.get("facilities_flagged"):
                tags = render_tag_list(ctx["facilities_flagged"], "sub-tag sub-tag-gold")
                rows_html += f'<div class="detail-row"><strong>Facilities Flagged</strong><span>{tags}</span></div>'
            if ctx.get("urgency"):
                rows_html += f'<div class="detail-row"><strong>Urgency Level</strong><span>{esc(ctx["urgency"])}</span></div>'
            if ctx.get("location"):
                rows_html += f'<div class="detail-row"><strong>Location</strong><span>{esc(ctx["location"])}</span></div>'
        elif category == "Curriculum":
            if ctx.get("missing_topics"):
                tags = render_tag_list(ctx["missing_topics"])
                rows_html += f'<div class="detail-row"><strong>Missing Topics Identified</strong><span>{tags}</span></div>'
            if ctx.get("outdated_areas"):
                tags = render_tag_list(ctx["outdated_areas"], "sub-tag sub-tag-gold")
                rows_html += f'<div class="detail-row"><strong>Outdated Areas Flagged</strong><span>{tags}</span></div>'
            if ctx.get("industry_alignment"):
                rows_html += f'<div class="detail-row"><strong>Industry Alignment Rating</strong><span>{esc(ctx["industry_alignment"])}</span></div>'

        if rows_html:
            st.markdown(
                f'<div class="info-card">'
                f'<div class="info-card-title">{i("list", 13)} Structured Context Details</div>'
                f'{rows_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Comment (quote-card) ──────────────────────────────────────────
    if pd.notna(row.get("comment")) and str(row["comment"]).strip():
        st.markdown("<div style='height:.4rem;'></div>", unsafe_allow_html=True)
        section_header("message-square", "Your Comment")
        st.markdown(
            f'<div class="quote-card">'
            f'<p>{esc(str(row["comment"]).strip())}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )


def show_feedback_form(category, user, username, session: str | None = None):
    meta = CAT_META[category]
    active_sess = session or CURRENT_SESSION
    page_header(meta["icon"], category, meta["desc"], badge_text=f"Feedback Submission · {active_sess} Session")

    # A confirmation parked by the submit handler below. It is popped here
    # rather than on the login page, so a student who submits and is then
    # bounced to the portal does not see a stale "feedback submitted" banner
    # over the sign-in form. `flash_scope` is checked so the login page can
    # leave its own messages alone.
    _flash = None
    if st.session_state.get("flash_scope") == f"feedback:{category}":
        st.session_state.pop("flash_scope", None)
        _flash = st.session_state.pop("flash_message", None)
    if _flash:
        st.success(_flash)

    df = load_data(category, session=active_sess)
    # Case-insensitive, like every other username lookup here. With `==` the
    # "you already submitted" view failed to appear for an account whose
    # stored casing differed, so the student was shown the form again and the
    # save was then rejected by the UNIQUE(username, category, session) index.
    mine = filter_by_username(df, username)

    if not mine.empty:
        row = mine.iloc[0]
        _render_already_submitted(category, row, active_sess)
        # Celebrate only on the run that follows the save, not on every later
        # visit to this read-only summary. The pop is what makes it once.
        if st.session_state.pop("just_submitted", None) == category:
            st.balloons()
        return

    section_header("folder-open", "Structured Context")
    level = user.get("level") if isinstance(user, dict) else None
    context_data = _CONTEXT_RENDERERS.get(category, lambda level: {})(level)

    st.markdown("<div style='height:.4rem;'></div>", unsafe_allow_html=True)
    section_header("edit", "Rating & Written Comments")

    with st.form(f"form_{category}"):
        st.markdown(f'<div class="form-section-label">{i("star", 13)} Overall Rating</div>', unsafe_allow_html=True)
        rating = st.slider("Rate from 1 (Poor) to 5 (Excellent)", 1, 5, 3, key=f"sl_{category}")
        labels = ["", "Poor", "Fair", "Good", "Very Good", "Excellent"]
        colors = ["", "#ef4444", "#f97316", "#f59e0b", "#22c55e", "#10b981"]
        st.markdown(
            f'<div class="rating-display">{star_row(rating)}'
            f'<span class="rating-text" style="color:{colors[rating]};">{labels[rating]}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="form-section-label" style="margin-top:1rem;">{i("message", 13)} Written Comments</div>',
                    unsafe_allow_html=True)
        comment = st.text_area(
            "Provide a detailed account of your experience",
            placeholder="Describe what is working well, what requires improvement, and any specific recommendations…",
            height=150, key=f"ta_{category}",
        )
        submitted = st_compat.form_submit_button("Submit Feedback →", use_container_width=True, type="primary")
        if submitted:
            if category == "Lecturer Teaching Style" and not context_data.get("lecturer_name"):
                html_alert("Please enter the name of the lecturer you wish to give feedback on.", "warning")
            elif not comment.strip():
                html_alert("A written comment is required before submission. Please provide your observations.", "warning")
            else:
                s_res = analyze_sentiment(comment)
                ok, msg = save_data(category, {
                    "username": username, "student_level": user["level"], "rating": rating,
                    "comment": comment, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "additional_info": "", "sentiment": s_res.label, "sentiment_score": s_res.score,
                    "sentiment_engine": s_res.engine,
                    "sentiment_confidence": s_res.confidence,
                    "sentiment_cues": {"pos": s_res.pos_cues, "neg": s_res.neg_cues, "contrast": s_res.contrast_detected},
                    "context_data": context_data,
                    "session": active_sess,
                })
                if ok:
                    # The e-mails go out before the rerun, because a rerun
                    # discards the rest of this script run.
                    _send_post_submission_emails(category, user, username, active_sess)
                    # Park the confirmation, then rerun so the page comes back
                    # as the read-only "Submission Confirmed" view.
                    #
                    # Without this the form kept its values, so the student was
                    # still looking at the editable form *and* the success alert
                    # on the same screen, one click away from re-submitting.
                    # The re-submission then failed with "You have already
                    # submitted feedback for this category and academic
                    # session" — a constraint enforced by a UNIQUE index the
                    # student never saw, surfaced as if the save itself had
                    # failed. Worse, the balloons had already celebrated a
                    # submission that the second attempt rejected.
                    #
                    # The balloons are NOT called here: st.rerun() raises, so an
                    # element queued on this run is discarded before it reaches
                    # the browser. The flag below makes the confirmed view
                    # celebrate on the run that actually survives.
                    st.session_state["flash_message"] = msg
                    st.session_state["flash_scope"] = f"feedback:{category}"
                    st.session_state["just_submitted"] = category
                    st.rerun()
                else:
                    # A real failure stays on the page with the form intact so
                    # the comment is not lost and can be edited and retried.
                    # html_alert escapes its message, so this is not
                    # double-escaped.
                    html_alert(msg, "error")


def _send_post_submission_emails(category: str, user: dict, username: str, session_name: str = CURRENT_SESSION):
    """Best-effort: never blocks or fails the submission itself."""
    if not is_email_configured() or not user.get("email"):
        return
    send_submission_email(user["email"], user["name"], category)
    # Check whether this was the student's final remaining category for this session.
    fresh = load_data(session=session_name)
    mine = filter_by_username(fresh, username)
    if len(mine) >= len(CATEGORIES):
        send_completion_email(user["email"], user["name"], session_name)
