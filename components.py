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


def html_metric(icon_name: str, value, label: str, accent: str = ""):
    st.markdown(
        f'<div class="metric-card metric-accent-{accent}">'
        f'<div class="metric-icon-wrap">{icon_badge(icon_name, size=22, box=44)}</div>'
        f'<div class="metric-value">{esc(value)}</div>'
        f'<div class="metric-label">{esc(label)}</div>'
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
