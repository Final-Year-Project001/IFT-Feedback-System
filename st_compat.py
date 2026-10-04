"""
st_compat.py
------------
Graceful Streamlit version compatibility shims.

Streamlit's Python API gains parameters almost every release, and some older
ones are deprecated in favour of replacements. Rather than sprinkle
`hasattr`/`inspect` checks through the page code, every widget that has moved
is called through this module, which:

  * drops a keyword argument the installed version does not accept,
  * rewrites `use_container_width=True/False` into the newer
    `width="stretch"/"content"` pair when that is available,
  * degrades to a sensible inline rendering when a whole feature is missing
    (`st.dialog` -> a bordered container, `st.segmented_control` -> a radio).

Every helper is a thin pass-through on a modern Streamlit, so there is no
behaviour to keep in sync — the shim only removes the version check from the
calling code.
"""

from __future__ import annotations

import inspect
from functools import wraps

import streamlit as st


def _params_of(func) -> dict | None:
    """The target function's parameters, or None if they cannot be read."""
    if func is None:
        return None
    try:
        return dict(inspect.signature(func).parameters)
    except (TypeError, ValueError, AttributeError):
        return None


def _supports_kwarg(func, kwarg: str) -> bool:
    params = _params_of(func)
    return bool(params) and kwarg in params


# ── Capability probes (all use getattr so a missing attribute is never fatal) ──
_BUTTON_SUPPORTS_ICON = _supports_kwarg(getattr(st, "button", None), "icon")
_DOWNLOAD_BUTTON_SUPPORTS_ICON = _supports_kwarg(getattr(st, "download_button", None), "icon")
_TOAST_SUPPORTS_ICON = _supports_kwarg(getattr(st, "toast", None), "icon")
_COLUMNS_SUPPORTS_VALIGN = _supports_kwarg(getattr(st, "columns", None), "vertical_alignment")
_DIALOG_SUPPORTS_WIDTH = _supports_kwarg(getattr(st, "dialog", None), "width")
_CONTAINER_SUPPORTS_KEY = _supports_kwarg(getattr(st, "container", None), "key")

# Kept for the module's own diagnostics; `_call` decides per target function
# rather than from this global, because Streamlit added `width` to buttons
# before it added it to `st.plotly_chart` / `st.dataframe`.
_WIDTH_SUPPORTS_KW = _supports_kwarg(getattr(st, "button", None), "width")

# `st.segmented_control` landed in 1.40; older versions get a radio instead.
_HAS_SEGMENTED_CONTROL = callable(getattr(st, "segmented_control", None))

# `st.fragment(run_every=...)` landed in 1.37 and is the only built-in way to get
# a repeating callback — Streamlit has no timer. Used here to clear a
# confirmation message on a wall-clock deadline rather than on the next click.
_HAS_FRAGMENT = callable(getattr(st, "fragment", None))
_HAS_SCOPED_RERUN = _supports_kwarg(getattr(st, "rerun", None), "scope")


def autorun_fragment(interval: str):
    """Decorator: re-run the wrapped function every `interval`, if supported.

    On a Streamlit too old for fragments the function is returned unchanged and
    behaves as an ordinary call. That is a real degradation — the message would
    then clear on the next interaction instead of after `interval` — but it is a
    cosmetic one, and silently failing to render the message at all would not be.
    """
    def decorate(func):
        if not _HAS_FRAGMENT:
            return func
        try:
            return st.fragment(run_every=interval)(func)
        except TypeError:
            # The installed version has `st.fragment` but not `run_every`.
            return func

    return decorate


def rerun_fragment():
    """Re-runs just the current fragment, where that is meaningful.

    Falls back to a full rerun on versions without `scope`, which is correct
    rather than broken — it just redraws more than strictly necessary.
    """
    if _HAS_SCOPED_RERUN:
        st.rerun(scope="fragment")
    else:
        st.rerun()


def _call(func, *args, **kwargs):
    """Calls a Streamlit function, dropping keywords it does not accept.

    Three things have to happen, in this order:

    1. `use_container_width` is re-spelled. The decision is made from *this*
       target's own signature rather than from a global probe, because
       Streamlit introduced `width="stretch"/"content"` on buttons before it
       did so on the data and plot widgets — probing `st.button` and applying
       the answer everywhere injected an unsupported `width` into
       `st.plotly_chart` on the versions in between.
    2. Keywords the target does not accept are dropped. The previous version
       only did this when the function happened to have a parameter called
       `label`, so `st.plotly_chart` (whose first parameter is
       `figure_or_data`) got no filtering at all.
    3. Only then is the call made.
    """
    if not kwargs:
        return func(*args)

    params = _params_of(func)
    if params is None:
        return func(*args, **kwargs)

    flag = kwargs.pop("use_container_width", None)
    if flag is not None:
        if "width" in params:
            kwargs["width"] = "stretch" if flag else "content"
        elif "use_container_width" in params:
            kwargs["use_container_width"] = flag
        # If the target supports neither spelling there is nothing sensible to
        # send, so the width request is dropped rather than raising.

    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        kwargs = {k: v for k, v in kwargs.items() if k in params}

    return func(*args, **kwargs)


# ══════════════════════════════════════════════════════════════
#  BUTTONS
# ══════════════════════════════════════════════════════════════

def button(label: str, icon: str | None = None, **kwargs):
    if icon is not None and _BUTTON_SUPPORTS_ICON:
        kwargs["icon"] = icon
    return _call(st.button, label, **kwargs)


def form_submit_button(label: str, icon: str | None = None, **kwargs):
    """`st.form_submit_button` — same shim rules as `button`."""
    target = getattr(st, "form_submit_button", None)
    if target is None:
        return st.button(label, **kwargs)
    if icon is not None and _supports_kwarg(target, "icon"):
        kwargs["icon"] = icon
    return _call(target, label, **kwargs)


def download_button(label: str, icon: str | None = None, **kwargs):
    if icon is not None and _DOWNLOAD_BUTTON_SUPPORTS_ICON:
        kwargs["icon"] = icon
    return _call(st.download_button, label, **kwargs)


def toast(body: str, icon: str | None = None, **kwargs):
    """A transient message. Falls back to st.info on Streamlit < 1.27."""
    target = getattr(st, "toast", None)
    if target is None:
        return st.info(body)
    if icon is not None and _TOAST_SUPPORTS_ICON:
        kwargs["icon"] = icon
    return _call(target, body, **kwargs)


# ══════════════════════════════════════════════════════════════
#  DATA & CHART WIDGETS
# ══════════════════════════════════════════════════════════════

def dataframe(data, **kwargs):
    return _call(st.dataframe, data, **kwargs)


def data_editor(data, **kwargs):
    return _call(st.data_editor, data, **kwargs)


def plotly_chart(figure, **kwargs):
    return _call(st.plotly_chart, figure, **kwargs)


# ══════════════════════════════════════════════════════════════
#  LAYOUT
# ══════════════════════════════════════════════════════════════

def columns(spec, vertical_alignment: str | None = None, **kwargs):
    if vertical_alignment is not None and _COLUMNS_SUPPORTS_VALIGN:
        kwargs["vertical_alignment"] = vertical_alignment
    return st.columns(spec, **kwargs)


def container(border: bool = False, key: str | None = None, **kwargs):
    """`st.container`, dropping `key` on Streamlit < 1.39 where it is absent."""
    if key is not None and not _CONTAINER_SUPPORTS_KEY:
        key = None
    return st.container(border=border, key=key, **kwargs)


def segmented_control(label: str, options: list, default=None, key: str | None = None, **kwargs):
    """A segmented pill toggle where available, otherwise a horizontal radio.

    Used for the Student/Administrator portal switch, which previously wrapped
    a radio in a `<div class="role-switch-container">` — a div that Streamlit's
    HTML parser auto-closes at the end of its own markdown container, so none
    of the styling ever applied. Styling a real widget's own test-id cannot
    have that failure mode.
    """
    if _HAS_SEGMENTED_CONTROL:
        if default is None:
            return st.segmented_control(label, options, key=key, **kwargs)
        return st.segmented_control(label, options, default=default, key=key, **kwargs)
    kwargs.pop("selection_mode", None)
    return st.radio(
        label, options, index=options.index(default) if default in options else 0,
        horizontal=True, key=key, label_visibility="collapsed" if label else "visible",
    )


# ══════════════════════════════════════════════════════════════
#  DIALOG
# ══════════════════════════════════════════════════════════════

def dialog(title: str, width: str = "large"):
    """Returns a dialog decorator.

    On Streamlit >= 1.31 this is the real modal. On older versions it degrades
    to a bordered container with the same heading, so the deletion confirmation
    still works — it just renders inline instead of as an overlay.
    """
    target = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if target is not None:
        if _DIALOG_SUPPORTS_WIDTH:
            return target(title, width=width)
        return target(title)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with st.container(border=True):
                st.subheader(title)
                return func(*args, **kwargs)
        return wrapper

    return decorator
