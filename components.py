"""
components.py
--------------
Small, reusable HTML-rendering helpers shared by every page. Centralizing
these means a visual tweak (e.g. metric card layout) only has to change
in one place.

IMPORTANT: any *user-supplied* text (comments, names, free-text fields)
that gets interpolated into an `unsafe_allow_html=True` block MUST be
passed through `esc()` first. The original version of this app rendered
raw user text straight into HTML, which is an HTML/script-injection
(XSS) hole — one student could have put `<script>...</script>` in a
comment and it would have executed in every other viewer's browser.
"""

from __future__ import annotations

import html

import streamlit as st

from icons import i, icon_badge
import st_compat


def esc(text) -> str:
    """Escape user-supplied text before it goes into an HTML string."""
    return html.escape(str(text)) if text is not None else ""


def html_alert(msg: str, kind: str = "info", icon_name: str | None = None, raw: bool = False):
    """A coloured inline alert banner.

    `msg` is escaped by default. It was the only helper in this module that
    interpolated its message raw, so every caller had to remember to call
    `esc()` itself — and callers pass f-strings built from a comment, a
    username or an admin note. Escaping here, and requiring the two callers
    that genuinely need markup to opt in with `raw=True`, makes the safe thing
    the default instead of a rule each call site has to re-learn.
    """
    icon_name = icon_name or {"success": "check-circle", "error": "x",
                               "warning": "alert-triangle", "info": "info"}.get(kind, "info")
    body = msg if raw else esc(msg)
    st.markdown(
        f'<div class="alert alert-{kind}">{i(icon_name, 18)}<span>{body}</span></div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════
#  RESULT DIALOG
# ══════════════════════════════════════════════════════════════
# A modal for the moments a FLOW COMPLETES and the user has to acknowledge
# it: registration finished, password reset finished, an account was deleted.
#
# Deliberately NOT used for form-validation errors. A modal on a validation
# failure is a regression, not an upgrade: the user is mid-form, the offending
# field is right there, and making them dismiss a dialog before they can type
# again puts a click between the mistake and the fix. Those stay inline
# `html_alert`s, next to the input they concern.
#
# The park/render split exists because of Streamlit's rerun semantics. An
# element queued on a run is thrown away by the `st.rerun()` that follows it,
# which is exactly why the original "Account created successfully" message had
# to be stored in session_state and re-rendered on the other side of the
# redirect. `park_result_dialog` is that storage; `render_parked_dialog` is the
# re-render, and it pops the payload so a later refresh cannot resurrect a
# dialog the user already dismissed.
#
# The dialog itself is a TOP-LEVEL function decorated with `st.dialog`. Streamlit
# registers dialogs at decoration time, so the decorated function must be at
# module scope, not nested inside another function. The payload is read from
# session_state inside the dialog body.
#
# Two payload keys are used:
#   "_pending_result_dialog" — parked for the NEXT run (park/render pattern)
#   "_dialog_payload" — for immediate display (result_dialog)
# Both are transferred to "_dialog_payload" before the dialog is invoked.

_RESULT_DIALOG_KEY = "_pending_result_dialog"

_DIALOG_ICON = {
    "success": "check-circle",
    "error": "x-circle",
    "warning": "alert-triangle",
    "info": "info",
}


# ── Top-level result dialog ──────────────────────────────────────────────
#
# Streamlit's `st.dialog` decorator must be applied to a top-level function.
# The dialog reads its payload from session_state, which is populated by
# `park_result_dialog` (for deferred display) or `result_dialog` (for immediate
# display). The dialog function itself is stateless — it just renders whatever
# is in the payload key.
#
# The payload is a dict with keys: message, kind, title, details, button_label.
# It is stored under "_dialog_payload" by the parking/rendering functions.

@st_compat.dialog("Confirm Action", width="small")
def _render_result_dialog():
    """Renders the result dialog from the payload in session_state."""
    payload = st.session_state.get("_dialog_payload")
    if not payload:
        return

    kind = payload["kind"]
    icon = _DIALOG_ICON.get(kind, "info")
    message = esc(payload["message"])
    details_html = (
        f'<div class="result-dialog-details">{esc(payload["details"])}</div>'
        if payload.get("details") else ""
    )
    # The dynamic title goes in the body as a header, since st.dialog title
    # is fixed at decoration time.
    title = esc(payload["title"]) if payload.get("title") else ""

    st.markdown(
        f'<div class="result-dialog result-dialog-{kind}">'
        f'<div class="result-dialog-icon">{i(icon, 30)}</div>'
        f'<div class="result-dialog-body">'
        f'{f"<div class=\"result-dialog-title\">{title}</div>" if title else ""}'
        f'{message}'
        f"{details_html}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
    if st_compat.button(
        payload.get("button_label") or "Continue",
        type="primary",
        use_container_width=True,
        key="_result_dialog_ok",
    ):
        # Clear the payload so the dialog doesn't reopen on the next run.
        st.session_state.pop("_dialog_payload", None)
        st.rerun()


# ── Park / render helpers ────────────────────────────────────────────────

def park_result_dialog(message: str, kind: str = "success", title: str | None = None,
                       details: str | None = None, button_label: str = "Continue"):
    """Stores a result dialog to be shown on the NEXT run.

    Call this immediately before the `st.rerun()` that follows the action. The
    dialog is deliberately not opened here: anything rendered on this run is
    discarded by the `st.rerun()` that follows it, so the modal would flash and vanish.
    """
    st.session_state[_RESULT_DIALOG_KEY] = {
        "message": message,
        "kind": kind if kind in _DIALOG_ICON else "info",
        "title": title,
        "details": details,
        "button_label": button_label,
    }


def result_dialog(message: str, kind: str = "success", title: str | None = None,
                  details: str | None = None, button_label: str = "Continue"):
    """Opens a result dialog immediately, on the current run.

    Use this when no `st.rerun()` is going to follow. If one is, park it with
    `park_result_dialog` instead — see that function's note.
    """
    st.session_state["_dialog_payload"] = {
        "message": message,
        "kind": kind if kind in _DIALOG_ICON else "info",
        "title": title,
        "details": details,
        "button_label": button_label,
    }
    _render_result_dialog()


def render_parked_dialog() -> bool:
    """Shows and clears a dialog parked on a previous run.

    Returns True if one was shown. Call this at the TOP LEVEL of a page
    function — Streamlit renders a dialog as a page-level modal, so invoking
    it from inside a `st.columns()` context is not the intended usage.
    """
    payload = st.session_state.pop(_RESULT_DIALOG_KEY, None)
    if not payload:
        return False
    st.session_state["_dialog_payload"] = payload
    _render_result_dialog()
    return True


# ══════════════════════════════════════════════════════════════
#  CONFIRMATION DIALOG
# ══════════════════════════════════════════════════════════════
# A two-button modal for an irreversible ACTION the user is about to take:
# submit feedback that can no longer be edited, delete an account, move the
# active semester. It is the deliberate counterpart of the result dialog above
# — that one reports something that already happened, this one asks BEFORE
# anything happens.
#
# The point that matters is the split between *asking* and *doing*. This dialog
# writes no data and performs no action. Each button records an answer in
# session_state and `st.rerun()`s; the calling page then reads
# `take_confirmation(...)` on the next run and only then runs the action. The
# earlier feedback flow did the opposite — it popped the parked submission and
# saved it on the very run that merely *displayed* the dialog, and the dialog's
# own `st.rerun()` discarded the modal. The user was asked to confirm something
# that had already happened; that is the bug this replaces.
#
# Everything printed is escaped here from a structured payload (title, intro,
# label/value rows, a rating, a warning). Callers hand over values, never HTML,
# so a student-typed field can never reach the modal unescaped.

_CONFIRM_DIALOG_KEY = "_pending_confirm_dialog"
_CONFIRM_APPROVED_KEY = "_confirmed_action"


# Non-dismissible: the calling page re-creates this modal on every run while its
# own pending state is set, so a dismiss-by-outside-click would just reappear on
# the next interaction. Forcing an explicit choice is also the right interaction
# for an irreversible action.
@st_compat.dialog("Please confirm", width="small", dismissible=False)
def _render_confirm_dialog():
    """Renders the confirmation modal that is currently active, if any."""
    payload = st.session_state.get(_CONFIRM_DIALOG_KEY)
    if not payload:
        return

    rows = payload.get("rows") or []
    rows_html = "".join(
        f'<div class="confirm-dialog-row"><span>{esc(label)}</span>'
        f'<strong>{esc(value)}</strong></div>'
        for label, value in rows
    )
    rating = payload.get("rating")
    rating_html = (
        f'<div class="confirm-dialog-rating">{star_row(int(rating), 18)}'
        f'<span>{esc(int(rating))}/5</span></div>'
        if rating is not None else ""
    )
    warning_text = payload.get("warning") or ""
    warning_html = (
        f'<div class="confirm-dialog-warning">{i("alert-triangle", 16)}'
        f"<span>{esc(warning_text)}</span></div>"
        if warning_text else ""
    )

    st.markdown(
        f'<div class="confirm-dialog">'
        f'<div class="confirm-dialog-icon">{i(payload.get("icon", "alert-triangle"), 26)}</div>'
        f'<div class="confirm-dialog-title">{esc(payload.get("title") or "Please confirm")}</div>'
        f'<div class="confirm-dialog-intro">{esc(payload.get("intro") or "")}</div>'
        f'{rating_html}'
        f'<div class="confirm-dialog-summary">{rows_html}</div>'
        f"{warning_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    cancel_col, confirm_col = st.columns(2)
    with cancel_col:
        if st_compat.button(
            payload.get("cancel_label") or "Cancel",
            key="_confirm_dialog_cancel",
            use_container_width=True,
        ):
            # Cancel unwinds the flow: drop the modal and whatever the caller
            # parked alongside it (e.g. a half-finished submission), then rerun
            # so the modal is not re-opened from the same payload.
            st.session_state.pop(_CONFIRM_DIALOG_KEY, None)
            for key in payload.get("cancel_keys", ()):
                st.session_state.pop(key, None)
            st.rerun()
    with confirm_col:
        if st_compat.button(
            payload.get("confirm_label") or "Confirm",
            key="_confirm_dialog_confirm",
            type="primary",
            use_container_width=True,
        ):
            # Record the answered token and nothing else. The caller performs
            # the action on the next run, so a dismissal that never reaches
            # this line cannot have side effects.
            st.session_state[_CONFIRM_APPROVED_KEY] = payload["token"]
            st.session_state.pop(_CONFIRM_DIALOG_KEY, None)
            st.rerun()


def _sanitise_confirmation(title: str, token: str, intro: str, rows, rating,
                           warning: str, confirm_label: str, cancel_label: str,
                           icon: str, cancel_keys) -> dict:
    """Normalises a caller's arguments into the payload the modal renders from."""
    return {
        "title": title,
        "token": token,
        "intro": intro,
        "rows": [(str(label), value) for label, value in (rows or [])],
        "rating": rating,
        "warning": warning,
        "confirm_label": confirm_label,
        "cancel_label": cancel_label,
        "icon": icon,
        "cancel_keys": tuple(cancel_keys or ()),
    }


def request_confirmation(title: str, token: str, intro: str = "", rows=None,
                         rating=None, warning: str = "",
                         confirm_label: str = "Confirm", cancel_label: str = "Cancel",
                         icon: str = "alert-triangle", cancel_keys=()):
    """Opens a two-button confirmation modal on the current run.

    The calling page invokes this on every run while its own pending state is
    set, so the modal is re-created on the run that carries a button click --
    that is what lets the Confirm/Cancel handlers actually fire. The dialog
    performs no action itself: *Confirm* records ``token`` under the approved
    key and *Cancel* clears the caller's `cancel_keys`; the caller reads
    `take_confirmation(token)` on the next run and only then does the work.

    All display values are escaped inside `_render_confirm_dialog`, so pass text
    and `(label, value)` pairs, never markup.
    """
    st.session_state[_CONFIRM_DIALOG_KEY] = _sanitise_confirmation(
        title, token, intro, rows, rating, warning,
        confirm_label, cancel_label, icon, cancel_keys,
    )
    _render_confirm_dialog()


def take_confirmation(token: str) -> bool:
    """True exactly once, on the run after *Confirm* was pressed for `token`.

    The token is consumed here so the action cannot run twice if a later widget
    triggers another rerun on the same confirmed state.
    """
    if st.session_state.get(_CONFIRM_APPROVED_KEY) == token:
        st.session_state.pop(_CONFIRM_APPROVED_KEY, None)
        return True
    return False


def html_metric(icon_name: str, value, label: str, accent: str = "",
                delta: str | None = None, badge: str | None = None):
    badge_html = f'<div class="metric-top-badge">{esc(badge)}</div>' if badge else ""
    delta_html = f'<div class="metric-delta-row">{esc(delta)}</div>' if delta else ""
    st.markdown(
        f'<div class="metric-card metric-accent-{accent}">'
        f'{badge_html}'
        f'<div class="metric-icon-wrap">{icon_badge(icon_name, size=22, box=44)}</div>'
        f'<div class="metric-value">{esc(value)}</div>'
        f'<div class="metric-label">{esc(label)}</div>'
        f'{delta_html}'
        f"</div>",
        unsafe_allow_html=True,
    )


def page_header(icon_name: str, title: str, subtitle: str, badge_text: str | None = None):
    badge_html = ""
    if badge_text:
        badge_html = f'<div class="page-header-badge">{i("circle-dot", 12)} {esc(badge_text)}</div>'
    st.markdown(
        f'<div class="page-header">{badge_html}'
        f'<div class="page-header-top">'
        f'<div class="page-header-icon-wrap">{i(icon_name, 30, "#3b82f6")}</div>'
        f"<div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def section_header(icon_name: str, text: str):
    st.markdown(
        f'<div class="section-header">'
        f'<div class="section-header-pill">{i(icon_name, 13)} {esc(text)}</div>'
        f'<div class="section-header-line"></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def empty_state(icon_name: str, title: str, desc: str):
    st.markdown(
        f'<div class="empty-state">'
        f'<div class="empty-state-icon-wrap">{i(icon_name, 44, "#94a3b8")}</div>'
        f'<div class="empty-state-title">{esc(title)}</div>'
        f'<div class="empty-state-desc">{esc(desc)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def progress_bar(label: str, value: float, max_val: float, color: str | None = None):
    pct = min(100, round(value / max_val * 100)) if max_val else 0
    fill_style = f"width:{pct}%;"
    if color:
        fill_style += f"background:{color};"
    st.markdown(
        f'<div class="progress-wrap">'
        f'<div class="progress-label"><span>{esc(label)}</span><span>{esc(value)}/{esc(max_val)}</span></div>'
        f'<div class="progress-track"><div class="progress-fill" style="{fill_style}"></div></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_tag_list(items, style_class: str = "sub-tag") -> str:
    """Render a list of chips.

    The docstring here used to say these are "predefined checklist items only
    (never raw free text) -> safe to skip esc()". That reasoning was wrong
    twice over: `context_data` is a free-form JSON column, so a value read
    out of it is not guaranteed to be a checklist item; and a comment telling
    the next reader to skip escaping is precisely how the identical bug this
    codebase already fixed once comes back. Every element is escaped here,
    and the reason is not "we know what these are" but "it costs one call".
    """
    if not items:
        return ""
    if isinstance(items, (str, bytes)):
        # A bare string where a list was expected. Without this the loop below
        # would render one chip per character.
        items = [items]
    tags = "".join(f'<span class="{style_class}">{esc(item)}</span>' for item in items)
    return f'<div class="sub-tag-wrap">{tags}</div>'


def star_row(rating: int, size: int = 20) -> str:
    filled = "#d97706"
    empty = "#94a3b8"
    stars = "".join(i("star", size, filled if n <= rating else empty) for n in range(1, 6))
    return f'<div class="rating-stars">{stars}</div>'
