"""
app_pages/targets.py
--------------------
The three "who / what needs attention" breakdowns, rendered as cards rather
than as dataframes.

Why a card and not a table
--------------------------
Every one of these answers a question that ends in an action — "speak to this
lecturer about this", "rework this course at this level", "repair this item
first". A dataframe makes the reader do that last step themselves: sort it, read
the column headings, work out which row is worst. The card puts the answer in
the heading and the evidence underneath, which is what the reader came for.

Everything here escapes its own input. The values are counts and strings that
came out of `context_data`, which is a free-form JSON column with no constraint
on what a crafted request could put in it — the same reason the existing admin
pages escape before interpolating.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import st_compat

from components import esc, section_header, empty_state
from db import lecturer_summary, course_summary, facility_summary
from icons import i


# ── shared pieces ────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════
#  CHART CARD
#
#  Why this is a component and not two `st.markdown` calls
#  --------------------------------------------------------
#  Every chart on every page used to be wrapped like this:
#
#      st.markdown('<div class="chart-wrap"><div class="chart-title">…</div>')
#      st_compat.plotly_chart(fig, …)
#      st.markdown('</div>')
#
#  which renders the card as nothing. Streamlit closes the markup it is given at
#  the end of each element, so the opening `<div>` is auto-closed before the
#  chart is ever drawn, and the chart lands on the bare page below an empty box.
#  Splitting one element across three Streamlit elements cannot work — the
#  document is not the same document.
#
#  The card is therefore a real Streamlit container, styled through a test-id
#  of our own rather than one of Streamlit's internals.
#
#  Why `key="st…"` and not Streamlit's border-wrapper test-id
#  ---------------------------------------------------------
#  A `key` beginning with `st` becomes that element's `data-testid`. So naming
#  the container `stChartCard…` gives us a hook that is guaranteed present on
#  the element we actually rendered. Styling an internal wrapper instead
#  (`stVerticalBlockBorderWrapper`) is a guess about a name Streamlit does not
#  document and may rename between releases; when it is wrong the selector
#  matches nothing and the card silently loses its frame, which is exactly the
#  failure this is meant to prevent. `tests/test_css.py` verifies every
#  `data-testid` in the stylesheet against the real frontend bundle, so an
#  invented name fails the build rather than the page.
# ══════════════════════════════════════════════════════════════════════

def _card_key(title: str) -> str:
    """A stable, valid `st…` key for one chart card.

    Slugged from the title so the key is the same on every rerun — an
    `abs(hash(...))` would be salted per process and Streamlit would treat each
    run as a different element.
    """
    slug = "".join(ch if ch.isalnum() else "" for ch in title.title())
    return f"stChartCard{slug}"[:60]


def chart_card(title: str, icon: str = "chart-bar", figure=None, caption: str = ""):
    """Render a titled card containing one chart. Returns True if a chart drew.

    `figure=None` — which every builder here returns when there is not enough
    data yet — still renders the card and the caption, so the page keeps its
    shape instead of a section header appearing and then nothing under it.
    """
    with st_compat.container(border=True, key=_card_key(title)):
        st.markdown(
            f'<div class="chart-card-head">'
            f'<span class="chart-card-icon">{i(icon, 14)}</span>'
            f'<span class="chart-card-title">{esc(title)}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if figure is not None:
            st_compat.plotly_chart(figure, use_container_width=True,
                                   config={"displayModeBar": False})
        else:
            st.markdown(
                '<div class="chart-card-empty">Not enough data to chart yet.</div>',
                unsafe_allow_html=True,
            )
        if caption:
            st.markdown(
                f'<div class="chart-card-caption">{esc(caption)}</div>',
                unsafe_allow_html=True,
            )
    return figure is not None


# ══════════════════════════════════════════════════════════════════════
#  SEVERITY / STAR / TAG PRIMITIVES
# ══════════════════════════════════════════════════════════════════════

def _severity_of(avg_rating: float) -> tuple[str, str, str]:
    """(colour, tint, word) for an average rating.

    Cut on the same bands the sentiment engine uses, so a card and a chart
    beside it cannot colour the same number two different ways.
    """
    if avg_rating <= 2:
        return "#ef4444", "rgba(239,68,68,.06)", "Needs attention"
    if avg_rating < 4:
        return "#f59e0b", "rgba(245,158,11,.06)", "Mixed"
    return "#10b981", "rgba(16,185,129,.05)", "Performing well"


def _svg_star(size: int) -> str:
    """One filled star. Only `size` is interpolated, and it is an int parameter.

    Kept as its own function so `_stars` does not build a string containing a
    raw `{size}` — a helper that emits finished markup is something the static
    XSS gate can reason about, where a f-string assembled in the caller cannot.
    """
    return (
        f'<svg width="{int(size)}" height="{int(size)}" viewBox="0 0 24 24" '
        f'fill="{{colour}}" style="vertical-align:-2px" aria-hidden="true">'
        f'<path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.3 5.9 20.6 '
        f'1.4-6.8L2.2 9.1l6.9-.8z"/></svg>'
    )


def _badge_style(colour: str) -> str:
    """The CSS for a severity pill. `colour` is always one of three literals
    returned by `_severity_of`."""
    safe_colour = _hex(colour)
    return (
        f"background:{safe_colour}1a;color:{safe_colour};"
        f"border:1px solid {safe_colour}40;"
        f"border-radius:999px;padding:.25rem 1rem;font-size:.7rem;font-weight:700;"
        f"white-space:nowrap;display:inline-flex;align-items:center;gap:.35rem;"
    )


def _icon_wrap(colour: str, inner: str) -> str:
    """The square icon tile beside a card title."""
    safe_colour = _hex(colour)
    return (
        f'<div class="cat-breakdown-icon-wrap" '
        f'style="background:{safe_colour}1a;'
        f'border:1px solid {safe_colour}40;">{inner}</div>'
    )


def _hex(colour: str) -> str:
    """Passes through a colour literal; strips anything that is not one.

    The three severity colours and the four band colours are the only values
    that reach here, all of them literals in this module or in `sentiment.py`.
    This narrows that to something provable rather than merely true today: a
    colour can only be injected into a `style=` attribute through this.
    """
    import re

    return esc(re.sub(r"[^#0-9a-fA-F]", "", str(colour)))


def _card_open(colour: str, tint: str) -> str:
    """The opening tag of one insight card, tinted by severity."""
    safe_colour, safe_tint = _hex(colour), _hex(tint)
    return (
        f'<div class="insight-card" style="border-left:4px solid {safe_colour};'
        f'background:{safe_tint};border-color:{safe_colour}33;">'
    )


def _card_close() -> str:
    return "</div>"


def _star_badge(avg_rating: float, word: str, size: int = 13) -> str:
    """The `<stars> 3.4 · Mixed` pill at the right of a card header.

    A helper rather than inline f-string so the two card renderers cannot
    drift, and so the one place that emits the numeric average applies
    `html.escape` to it. The value is a `round(mean(), 2)` today, but it is
    derived from a column and the static XSS gate requires any value crossing
    into `unsafe_allow_html` to be escaped or justified by name — and a helper
    that escapes it once is better than three justifications.
    """
    return (
        f'<span style="{_badge_style(_severity_of(avg_rating)[0])}">'
        f"{_stars(avg_rating, size)} {esc(f'{avg_rating:.1f}')} · {esc(word)}</span>"
    )


def _count_of(value) -> str:
    """An escaped count, for the "N student responses" lines.

    Every count on this page comes from a `len()` or a `Counter`, so it is a
    number — but it is derived from `context_data` rows in some cases, and the
    static gate does not know that. One helper that escapes is cheaper to
    defend than an allowlist entry per call site.
    """
    return esc(value)


def _stars(avg_rating: float, size: int = 13) -> str:
    """A 5-star row with a fractional fill, built inline.

    `star_row` takes an int, which would round a 3.4 average to three stars and
    make every average look like a whole number. This keeps one decimal visible
    in the text beside it instead of pretending to finer precision in the icon.
    """
    full = int(avg_rating)
    out = []
    for idx in range(1, 6):
        # A literal, chosen by a boolean. Nothing outside this line reaches the
        # `fill` attribute, so the star's colour cannot be influenced by a value
        # that arrived in a row.
        colour = "#f59e0b" if idx <= full else "#cbd5e1"
        out.append(_svg_star(size).replace("{colour}", colour))
    return "".join(out)


def _tags(pairs, empty_note: str = "") -> str:
    """`(label, count)` pairs as small tags. `pairs` may be a Counter's
    `most_common()` result, which is exactly what the rollups return."""
    if not pairs:
        return (f'<span class="sub-tag">{esc(empty_note)}</span>' if empty_note else "")
    return "".join(_tag(str(label), count) for label, count in pairs)


def _tag(label: str, count) -> str:
    """One `<label> · <count>` tag.

    `label` is escaped and `count` coerced with `int()` inside one helper, so a
    caller cannot accidentally interpolate either of them raw — and so there is
    a single place the gate's allowlist has to name.
    """
    suffix = f" · {int(count)}" if count is not None else ""
    return f'<span class="sub-tag sub-tag-gold">{esc(label)}{suffix}</span>'


def _count_line(items) -> str:
    """How many distinct levels a target was reported from, in plain words."""
    if not items:
        return ""
    return f"reported from {len(items)} level{'s' if len(items) != 1 else ''}"


# ══════════════════════════════════════════════════════════════════════
#  LECTURERS
# ══════════════════════════════════════════════════════════════════════

def render_lecturer_targets(session: str | None = None, top_n: int = 3):
    """Every lecturer rated, with what was flagged against them.

    Not split by level, and the card says so on purpose: a lecturer can be rated
    by a 200-level and a 400-level student for different courses, and the
    department's question is about the person.
    """
    rows = lecturer_summary(session=session, top_n=top_n)
    if not rows:
        empty_state("users", "No teaching-style feedback yet",
                    "Once students rate their lecturers, each one appears here with "
                    "the challenges flagged against them.")
        return

    section_header("users", f"Lecturers to Advise ({len(rows)})")
    st.caption(
        "Every lecturer rated, worst average first, with the challenges students "
        "flagged most often. One row per person — a lecturer taught at more than "
        "one level is combined, because the conversation to have is with the "
        "lecturer, not with each cohort separately."
    )

    for row in rows:
        colour, tint, word = _severity_of(row["avg_rating"])
        unknown = "" if row.get("known") else (
            ' <span class="sub-tag">not on the handbook list</span>'
            if row["name"] != "Not identified"
            else ' <span class="sub-tag">no lecturer named</span>'
        )
        st.markdown(
            _card_open(colour, tint)
            + f'<div class="insight-header">'
            + f'<div class="insight-header-left">'
            + _icon_wrap(colour, i("user", 18, colour))
            + f'<div><div class="insight-title">{esc(row["display"])}{unknown}</div>'
            f'<div style="font-size:.7rem;color:var(--text-3);margin-top:.15rem;">'
            f'{_count_of(row["responses"])} student response'
            f'{"" if row["responses"] == 1 else "s"}'
            f'{(" · " + esc(", ".join(row["levels"]))) if row["levels"] else ""}'
            f'</div></div></div>'
            f'{_star_badge(row["avg_rating"], word)}'
            f'</div>'
            f'<div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;'
            f'color:var(--text-3);font-weight:700;margin:.85rem 0 .4rem;">'
            f'{i("alert-triangle", 12, "#d97706")} Most flagged challenges</div>'
            f'<div>{_tags(row["top_challenges"], "No delivery challenge flagged")}</div>'
            f'<div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;'
            f'color:var(--text-3);font-weight:700;margin:.85rem 0 .4rem;">'
            f'{i("thumbs-up", 12, "#059669")} Methods students said worked</div>'
            f'<div>{_tags(row["top_methods"], "None recorded")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:.4rem;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  COURSES
# ══════════════════════════════════════════════════════════════════════

def render_course_targets(session: str | None = None, top_n: int = 3):
    """The top courses per level, with the emphasis areas asked for.

    Grouped by level and labelled with it, because a 200-level and a 500-level
    course are different decisions even when the code is similar.
    """
    rows = course_summary(session=session, top_n=top_n)
    if not rows:
        empty_state("book-open", "No course feedback yet",
                    "Once students rate their course materials, the most-mentioned "
                    "courses appear here per level.")
        return

    by_level: dict[str, list] = {}
    for row in rows:
        by_level.setdefault(row["level"], []).append(row)

    section_header("book-open", "Courses to Rework, by Level")
    st.caption(
        f"The {top_n} most-mentioned courses at each level, with the areas students "
        f"asked for more emphasis. Split by level on purpose: the handbook "
        f"schedules these differently and they draw on different staff."
    )

    for level in sorted(by_level):
        st.markdown(
            f'<div class="form-section-label" style="margin:.9rem 0 .35rem;">'
            f'{i("graduation-cap", 13)} {esc(level)} Level '
            f'({len(by_level[level])} course{"" if len(by_level[level]) == 1 else "s"})'
            f'</div>',
            unsafe_allow_html=True,
        )
        for row in by_level[level]:
            colour, tint, word = _severity_of(row["avg_rating"])
            st.markdown(
                _card_open(colour, tint)
                + f'<div class="insight-header">'
                + f'<div class="insight-header-left">'
                + _icon_wrap(colour, i("book-open", 18, colour))
                + f'<div><div class="insight-title">{esc(row["course"])}</div>'
                f'<div style="font-size:.7rem;color:var(--text-3);margin-top:.15rem;">'
                f'{_count_of(row["responses"])} student response'
                f'{"" if row["responses"] == 1 else "s"}'
                f'</div></div></div>'
                f'{_star_badge(row["avg_rating"], word)}'
                f'</div>'
                f'<div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;'
                f'color:var(--text-3);font-weight:700;margin:.85rem 0 .4rem;">'
                f'{i("target", 12, "#7c3aed")} Most requested emphasis</div>'
                f'<div>{_tags(row["emphasis_areas"], "No emphasis area selected")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:.4rem;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  FACILITIES
# ══════════════════════════════════════════════════════════════════════

def render_facility_targets(session: str | None = None, top_n: int = 5):
    """The top infrastructure items across every level.

    Not split by level: a dead projector affects every cohort, and the repair
    decision is one departmental decision.
    """
    rows = facility_summary(session=session, top_n=top_n)
    if not rows:
        empty_state("wrench", "No facilities feedback yet",
                    "Once students flag infrastructure, the most-reported items "
                    "appear here with how urgently they were rated.")
        return

    section_header("wrench", f"Facilities to Repair (top {len(rows)})")
    st.caption(
        f"The {top_n} most-reported infrastructure items across every level, with the "
        f"urgency students gave them. Not split by level: broken equipment and "
        f"unstable power affect all cohorts at once."
    )

    frame = pd.DataFrame([{
        "Item": r["facility"],
        "Reports": r["reports"],
        "Levels": len(r["levels"]),
        # `urgency_counts` is a plain dict — see `db.facility_summary` — so the
        # most common entry is the max by value. Calling `.most_common()` here
        # raised AttributeError and took the whole admin dashboard down.
        "Most common urgency": (
            max(r["urgency_counts"].items(), key=lambda kv: kv[1])[0]
            if r.get("urgency_counts") else "—"),
    } for r in rows])
    st_compat.dataframe(frame, use_container_width=True, hide_index=True)

    # The top item gets a card: it is the one a maintenance request is written
    # from, so it is worth stating rather than leaving in a sortable table.
    worst = rows[0]
    locations = ", ".join(loc for loc, _ in (worst.get("top_locations") or []))
    # `urgency_counts` is a plain dict (see `db.facility_summary`), so it is
    # iterated rather than having `most_common()` called on it. That call was
    # left here from when the rollup returned a Counter, and it raised
    # AttributeError on every facilities card — the page still rendered, with
    # the worst item's card silently missing from the bottom of it.
    urgency_items = sorted(
        (worst.get("urgency_counts") or {}).items(),
        key=lambda kv: -kv[1],
    )
    urgency_split = ", ".join(
        f"{esc(str(u).split(chr(8212))[0].strip())} {esc(n)}" for u, n in urgency_items
    )
    st.markdown(
        f'<div class="insight-card" style="border-left:4px solid #dc2626;'
        f'background:rgba(239,68,68,.05);border-color:rgba(239,68,68,.25);">'
        f'<div class="insight-header"><div class="insight-header-left">'
        f'<div class="cat-breakdown-icon-wrap" style="background:rgba(239,68,68,.12);'
        f'border:1px solid rgba(239,68,68,.25);">{i("alert-triangle", 18, "#dc2626")}</div>'
        f'<div><div class="insight-title">Write this one up first</div>'
        f'<div style="font-size:.7rem;color:var(--text-3);margin-top:.15rem;">'
        f'{esc(worst["facility"])}</div></div></div>'
        f'<span style="background:rgba(239,68,68,.12);color:#dc2626;'
        f'border:1px solid rgba(239,68,68,.25);border-radius:999px;padding:.25rem 1rem;'
        f'font-size:.7rem;font-weight:700;white-space:nowrap;">'
        f'{_count_of(worst["reports"])} reports</span></div>'
        f'<div class="detail-row"><strong>Reported from</strong><span>'
        f'{esc(_count_line(worst["levels"]) or "—")}'
        f'{" · " + esc(", ".join(worst["levels"])) if worst["levels"] else ""}</span></div>'
        f'<div class="detail-row"><strong>Urgency as rated</strong><span>'
        f'{esc(urgency_split or "—")}</span></div>'
        f'<div class="detail-row"><strong>Locations named</strong><span>'
        f'{esc(locations or "—")}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )