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
    courses_for_level_semester, SEMESTERS, LECTURER_OPTIONS, LECTURER_PLACEHOLDER,
)
from db import load_data, save_data, parse_context, filter_by_username, get_active_semester
from sentiment import analyze_sentiment, rating_label, label_color, normalize_rating
from email_service import is_email_configured, send_submission_email, send_completion_email
from components import (
    html_alert, html_metric, page_header, section_header, render_tag_list, star_row, esc,
    request_confirmation, take_confirmation,
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

    # The semester is chosen once, at the top of the page, and gated against the
    # session's active semester before this renderer is ever reached. Reading it
    # from session_state rather than offering a second radio here means a
    # student cannot pick "Rain" in one control and "Harmattan" in another, and
    # the course list always matches the semester the page already validated.
    semester = st.session_state.get("feedback_semester") or SEMESTERS[0]
    st.markdown(
        f'<div class="course-semester-note">{i("calendar", 13)} '
        f'Showing <strong>{esc(semester)}</strong> semester courses for the '
        f'{esc(level_label)} curriculum.</div>',
        unsafe_allow_html=True,
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
    lecturer_name = st.selectbox(
        "Lecturer / Course Instructor",
        LECTURER_OPTIONS,
        key="ctx_lecturer_name",
        help="The teaching staff of the Department of Information Technology, "
             "from the Department Handbook §5.1. Pick the person, not a spelling "
             "of their name — the administrative breakdown groups on the exact "
             "entry you choose.",
    )
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
        "lecturer_name": "" if lecturer_name == LECTURER_PLACEHOLDER else lecturer_name,
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

    # ── Three metric cards: rating / band / date ────────────────────
    # The "Engine Confidence" card is gone with the engine it described. A
    # rating sits exactly on its band, so a confidence figure for it was
    # always 99% and told the student nothing.
    sent = row.get("effective_sentiment", row.get("sentiment", "Neutral"))
    # `normalize_rating` rather than `int()`: this is the first thing that
    # touches `row["rating"]` after it came out of the database, and a NULL or
    # malformed value would raise here and take the whole summary page with it.
    rating_val = normalize_rating(row.get("rating"))
    # Everything rendered below is escaped at the point of interpolation. The
    # band and its colour both come from `row`, and `label_color` returns a
    # fixed hex for each of three labels — but the label itself is a DB column,
    # and an unrecognised value would fall through to the neutral colour while
    # still being printed.
    sent_safe = esc(sent)
    sent_colour = label_color(sent)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="metric-card metric-accent-gold">'
            f'<div class="metric-icon-wrap">{star_row(rating_val, 16)}</div>'
            f'<div class="metric-value" style="font-size:1.3rem;">{esc(rating_val)}/5</div>'
            f'<div class="metric-label">Your Rating</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon-wrap">{i(sentiment_icon(sent), 24, sent_colour)}</div>'
            f'<div class="metric-value" style="font-size:1.3rem;color:{sent_colour};">{sent_safe}</div>'
            f'<div class="metric-label">Sentiment Band</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
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

    # ── Rating → sentiment, stated plainly ─────────────────────────────
    # The two are the same judgement now: the sentiment IS the rating band.
    # Showing them as two independent figures was what let a reader believe
    # they could disagree, so they are shown once, with the band named.
    _label = sent
    _rating = normalize_rating(row.get("rating"))
    _word = rating_label(_rating)
    st.markdown(
        f'<div class="info-card">'
        f'<div class="info-card-title">{i("shield-check", 13)} How your rating was recorded</div>'
        f'<div class="detail-row"><strong>Rating</strong><span>'
        f'{star_row(_rating, 14)} {esc(_rating)}/5 &mdash; {esc(_word)}'
        f'</span></div>'
        f'<div class="detail-row"><strong>Sentiment band</strong><span>'
        f'<strong style="color:{sent_colour}">{sent_safe}</strong></span></div>'
        f'<div class="detail-row"><strong>How it was decided</strong>'
        f'<span>Your rating alone. 1&ndash;2 Negative &middot; 3 Neutral &middot; 4&ndash;5 Positive.</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _set_semester_choice(semester: str):
    """Radio callback: record the student's chosen semester.

    A widget callback runs before the script body, which makes it the one place
    that can write the radio's own key without Streamlit rejecting the write
    ("cannot be modified after the widget is instantiated"). The switch button
    in the gate below uses it, and so does the radio itself.
    """
    st.session_state["feedback_semester"] = semester


def _render_semester_picker(active_semester: str) -> str:
    """Renders the Rain/Harmattan choice and returns the selection.

    The active semester is the default, but the other one stays selectable: the
    requirement is that choosing it *explains* that it is not active, not that
    the control is disabled and silently unresponsive.
    """
    if st.session_state.get("feedback_semester") not in SEMESTERS:
        st.session_state["feedback_semester"] = active_semester
    st.markdown(
        f'<div class="semester-picker">'
        f'<div class="semester-picker-label">{i("calendar", 14)} Which semester is this feedback for?</div>'
        f'<div class="semester-picker-hint">Only the active semester accepts feedback. '
        f'For this session that is <strong>{esc(active_semester)}</strong>.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    return st.radio(
        "Semester", SEMESTERS, key="feedback_semester",
        horizontal=True, label_visibility="collapsed",
    )


def _render_inactive_semester_gate(active_sess: str, chosen: str, active_semester: str):
    """Explains that `chosen` is not the session's active semester.

    Rendered INSTEAD of the form. Letting the student fill in a whole category
    for a semester the department is not collecting would waste their effort and
    pollute nothing (the save would be valid), so the gate is a return, not a
    warning beside a still-open form.
    """
    st.markdown(
        f'<div class="semester-gate">'
        f'<div class="semester-gate-icon">{i("calendar", 34, "#b45309")}</div>'
        f'<h3 class="semester-gate-title">The {esc(chosen)} semester is not active</h3>'
        f'<p class="semester-gate-text">Feedback for the <strong>{esc(active_sess)}</strong> '
        f'academic session is currently open for the <strong>{esc(active_semester)}</strong> '
        f'semester only. You selected <strong>{esc(chosen)}</strong>, so there are no '
        f'courses to rate yet. Switch to {esc(active_semester)} to continue.</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st_compat.button(
        f"Switch to {active_semester} and continue",
        key="semester_switch_btn",
        type="primary",
        use_container_width=True,
        on_click=_set_semester_choice,
        args=(active_semester,),
    ):
        # The callback has already set the radio; the rerun it triggers lands on
        # the active semester's form. Nothing to do inline.
        pass


def _confirmation_rows(category: str, pending: dict, semester: str):
    """The (label, value) summary rows for the confirmation modal.

    Plain text, never markup — `components._render_confirm_dialog` escapes each
    value. Values come from closed widget sets, but a facilities location is
    free text, which is exactly why the escaping lives at the dialog and not
    here.
    """
    ctx = pending.get("context_data") or {}
    rows = [
        ("Category", category),
        ("Academic Session", pending.get("active_sess", "")),
        ("Semester", semester),
    ]
    course = ctx.get("course_rated") or ctx.get("course_code")
    if course:
        rows.append(("Course", course))
    lecturer = ctx.get("lecturer_name")
    if lecturer:
        rows.append(("Lecturer", lecturer))
    if category == "Facilities":
        flagged = ctx.get("facilities_flagged") or []
        if flagged:
            rows.append(("Facilities flagged", f"{len(flagged)} selected"))
    if category == "Curriculum":
        missing = ctx.get("missing_topics") or []
        if missing:
            rows.append(("Missing topics flagged", f"{len(missing)} selected"))
    return rows


def _execute_submission(category: str, pending: dict, user: dict, username: str):
    """Writes a submission that the student confirmed in the modal.

    Reached only from `take_confirmation`, i.e. only after an explicit Confirm.
    The sentiment is derived from the rating here, not taken from the page, so a
    confirmed row and a directly-saved row cannot disagree.
    """
    rating = pending["rating"]
    s_res = analyze_sentiment(rating=rating)
    ok, msg = save_data(category, {
        "username": pending["username"],
        "student_level": pending["level"],
        "rating": rating,
        "comment": "",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "additional_info": "",
        "sentiment": s_res.label,
        "sentiment_score": s_res.score,
        "sentiment_engine": s_res.engine,
        "sentiment_confidence": s_res.confidence,
        "context_data": pending["context_data"],
        "session": pending["active_sess"],
    })
    if ok:
        _send_post_submission_emails(category, user, username, pending["active_sess"])
        st.session_state["flash_message"] = msg
        st.session_state["flash_scope"] = f"feedback:{category}"
        st.session_state["just_submitted"] = category
        st.rerun()
    else:
        html_alert(msg, "error")


def show_feedback_form(category, user, username, session: str | None = None):
    meta = CAT_META[category]
    active_sess = session or CURRENT_SESSION
    active_semester = get_active_semester(active_sess)

    page_header(
        meta["icon"], category, meta["desc"],
        badge_text=f"{active_sess} Session · {active_semester} Semester",
    )

    # ── Execute a submission the student explicitly confirmed ─────────────
    # `take_confirmation` is True only on the run after the modal's Confirm
    # button, and only once. Nothing is written before this point: the submit
    # handler parks the payload and opens the modal, it does not save.
    if take_confirmation(f"submit:{category}"):
        pending_confirmed = st.session_state.pop("pending_submission", None)
        if pending_confirmed and pending_confirmed.get("category") == category:
            _execute_submission(category, pending_confirmed, user, username)

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

    # ── Semester choice, then the active-semester gate ────────────────────
    # The gate sits before the context renderer so an inactive semester never
    # even builds the course list, and before the form so there is nothing to
    # submit.
    chosen_semester = _render_semester_picker(active_semester)
    if chosen_semester != active_semester:
        # Choosing an inactive semester abandons any parked submission for the
        # active one, so switching back later cannot surface a stale modal.
        st.session_state.pop("pending_submission", None)
        _render_inactive_semester_gate(active_sess, chosen_semester, active_semester)
        return

    section_header("folder-open", "Structured Context")
    level = user.get("level") if isinstance(user, dict) else None
    context_data = _CONTEXT_RENDERERS.get(category, lambda level: {})(level)

    st.markdown("<div style='height:.4rem;'></div>", unsafe_allow_html=True)
    section_header("edit", "Your Rating")

    with st.form(f"form_{category}"):
        st.markdown(
            f'<div class="form-section-label">{i("star", 13)} Overall Rating</div>'
            '<div class="checkbox-hint">This is the whole of your verdict. 1 star is Poor, '
            '3 stars is average, 5 stars is Excellent.</div>',
            unsafe_allow_html=True,
        )
        rating = st.slider("Rate from 1 (Poor) to 5 (Excellent)", 1, 5, 3, key=f"sl_{category}")
        labels = ["", "Poor", "Fair", "Good", "Very Good", "Excellent"]
        colors = ["", "#ef4444", "#f97316", "#f59e0b", "#22c55e", "#10b981"]
        st.markdown(
            f'<div class="rating-display">{star_row(rating)}'
            f'<span class="rating-text" style="color:{colors[rating]};">{labels[rating]}</span></div>',
            unsafe_allow_html=True,
        )
        submitted = st_compat.form_submit_button("Submit Feedback →", use_container_width=True, type="primary")
        if submitted:
            if category == "Lecturer Teaching Style" and not context_data.get("lecturer_name"):
                html_alert("Please choose the lecturer you wish to give feedback on.", "warning")
            else:
                # Park the intended submission. The modal below asks before
                # anything is written; `take_confirmation` performs the save on
                # a later run, only if the student pressed Confirm.
                st.session_state["pending_submission"] = {
                    "category": category,
                    "rating": rating,
                    "context_data": context_data,
                    "username": username,
                    "level": user["level"],
                    "active_sess": active_sess,
                }

    # ── Confirm before writing anything ───────────────────────────────────
    # Opened here, outside the form, and re-opened on every run while a pending
    # submission exists. That is deliberate: the run that carries the modal's
    # button click must re-create the modal for the handler to run at all. The
    # modal is non-dismissible, so the only exits are Cancel and Confirm.
    pending = st.session_state.get("pending_submission")
    if pending and pending.get("category") == category:
        request_confirmation(
            title="Submit this feedback?",
            token=f"submit:{category}",
            intro=(
                "You are about to record your feedback for this category. "
                "Please check the details below, then confirm."
            ),
            rows=_confirmation_rows(category, pending, chosen_semester),
            rating=pending.get("rating"),
            warning="Once submitted, this feedback cannot be edited or withdrawn.",
            confirm_label="Yes, submit feedback",
            cancel_label="Keep editing",
            cancel_keys=("pending_submission",),
        )


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
