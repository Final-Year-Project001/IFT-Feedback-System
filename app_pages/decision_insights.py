"""app_pages/decision_insights.py — AI-flavoured, rule-based recommendations per category."""

from collections import Counter
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape

import pandas as pd
import streamlit as st

import st_compat

from config import CATEGORIES, CAT_META, ALL_SESSIONS_LABEL
from db import (load_data, parse_context, context_text_list, load_admin_notes,
                save_admin_note)
from components import html_metric, page_header, section_header, empty_state, esc
from icons import i

_NEG_CRITICAL_PCT = 40.0   # at or above this share of negative ratings
_NEG_ANY_PCT = 1.0         # any negative at all is worth surfacing
_NEG_CRITICAL_MIN_N = 3    # responses required before "urgent" is claimed

# The share alone is not enough to call something urgent, because the share is
# very volatile at small numbers: two responses, one of them a 1, is 50% — the
# same figure as fifty responses with twenty-five 1s. Declaring a departmental
# emergency on one data point is the same error as declaring everything fine,
# so `urgent` needs both a large share and a floor on the sample behind it.
#
# This is the only place a count is allowed to affect the band, and it can only
# ever make a category *less* urgent than its share suggests, never more.

PRIORITY_CONFIG = {
    "critical": {
        "color": "#ef4444", "bg": "rgba(239,68,68,.06)", "border": "rgba(239,68,68,.25)",
        "icon_bg": "rgba(239,68,68,.12)", "label": "Needs Urgent Action", "label_icon": "alert-triangle",
        "rec": f"At least {_NEG_CRITICAL_PCT:.0f}% of responses here were rated 1 or 2. "
               "That is a level of dissatisfaction worth acting on directly.",
    },
    "warning": {
        "color": "#f59e0b", "bg": "rgba(245,158,11,.06)", "border": "rgba(245,158,11,.25)",
        "icon_bg": "rgba(245,158,11,.1)", "label": "Needs Attention", "label_icon": "alert-circle",
        "rec": "Some students rated this negatively. Review the structured responses "
               "below to see what specifically they objected to.",
    },
    # Not an alert. Nobody is unhappy; nobody is enthusiastic either. This is
    # the case that previously fell through to `critical`.
    "steady": {
        "color": "#3b82f6", "bg": "rgba(59,130,246,.05)", "border": "rgba(59,130,246,.2)",
        "icon_bg": "rgba(59,130,246,.1)", "label": "Neutral", "label_icon": "circle-dot",
        "rec": "No negative ratings so far. Responses of 3 mean neutral on the 1-5 "
               "scale, so this reads as unremarkable rather than unpopular.",
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

# ── How far above average is "good", per category ────────────────────────────
#
# The thresholds below are not arbitrary. Each is derived from the fact that a
# rating band is `1-2 Negative / 3 Neutral / 4-5 Positive`, which means 3.0 is
# the neutral point and 4.0 is where a category starts reading positive. So:
#
#   >= 4.0   performing well        (the whole Positive band)
#   >= 3.3   mixed but acceptable   (above neutral, not yet positive)
#   <  3.3   needs attention
#
# A category at 3.5 is genuinely "nothing anyone is complaining about" and
# should not be shown beside a category at 2.0 in the same alarming red. The
# old single cut at 3.5 did exactly that: eight of nine categories rendered as
# "Good" in a semester where the average was 2.6, because the comparison was
# against an absolute number rather than against what the scale means.
_POSITIVE_AT = 4.0

# ── Why the mean cannot decide the label ────────────────────────────────────
#
# It used to: `>= 4.0 good`, `>= 3.3 warning`, below that `critical`. Two bugs
# came out of that, and they are the same bug seen from opposite sides.
#
#   avg 3.0, 0% negative  ->  "Needs Urgent Action"
#   avg 3.5, 50% negative ->  "Needs Attention"
#
# Both cards print a "Negative" percentage right next to the label, and that
# percentage comes from the *distribution* while the label came from the
# *mean*. The two could therefore disagree — the first card declares an
# emergency with zero negative responses behind it, and on the second a mean
# of 3.5 describes nobody at all: it is one angry student and one delighted
# one averaged into a number that looks unremarkable.
#
# The mean is also not a decision input. It is one number built from two
# opposed opinions, and every use it made here was a way of not looking at
# either.
#
# So the label is read off the same counts the card displays. It is now
# impossible for the label and the figure beside it to disagree, because there
# is only one number and both are derived from it.
#
# The thresholds themselves are still not arbitrary: 1-2 is Negative and 4-5 is
# Positive by the engine's definition, so a category is "critical" once enough
# students have said something is wrong, and it cannot read "performing well"
# while anybody in it is negative.
# What to do about it, keyed on the evidence rather than on the average alone.
# The average says a category is struggling; the structured answers say *what*,
# and an administrator cannot act on the first without the second.
_PLAYBOOK = {
    "critical": [
        "Read the top three flagged items below before doing anything else — they "
        "name what students actually complained about.",
        "Treat this as a review item with a deadline, not a note for later. A "
        "category this far below neutral for a whole session is not a perception "
        "problem.",
        "Check whether the responses concentrate in one level, one course or one "
        "lecturer: a narrow problem is far cheaper to fix than a general one.",
    ],
    "warning": [
        "The average is above neutral but below the positive band, so this is "
        "improvement rather than crisis.",
        "Pick the single most-flagged item and address it. Attempting all of "
        "them at once is how none of them get addressed.",
        "Re-check next session: the gap between this and the positive band is "
        "narrow, and a small change should close it.",
    ],
    "steady": [
        "Nobody has rated this negatively, so there is nothing to fix. Record it "
        "as the baseline to compare against next session.",
        "An average below 4.0 with no negative ratings means ratings of 3 — "
        "neutral, not unhappy. Treat that as indifference rather than "
        "dissatisfaction: the course is unremarkable, not disliked.",
        "If it stays flat, ask what students would want covered. A neutral "
        "rating from a student who had nothing to complain about is a different "
        "signal from one who expected more.",
    ],
    "good": [
        "No action needed. Document what is working so it survives a change of "
        "staff or of curriculum.",
        "Worth checking the responses too: students tick 'no issues' alongside a "
        "high rating more often than departments expect, and a quiet category "
        "is not always a satisfied one.",
    ],
}


def _band(neg_pct: float, avg: float, count: int = 99) -> str:
    """The label for a category, read off the negative share.

    `neg_pct` rather than the average, because that is the figure printed next
    to the label on the card. One source, so the two cannot disagree.

    `steady` is the band that was missing: no negative ratings, but nothing
    strongly positive either. It previously fell through to `critical`, which
    is how a category rated 3/5 by everybody it had heard from — which the
    scale defines as Neutral — was flagged as an emergency.

    `count` guards `urgent` only. See `_NEG_CRITICAL_MIN_N`.
    """
    if neg_pct >= 100:
        # Unanimous. Two responses and both are 1-2 is not a volatile
        # percentage, it is the clearest possible signal there is — so the
        # sample-size floor below must not apply to it. Guarding it would mean
        # a category every single student rated 1-2 only becomes urgent once
        # three people had answered, which is backwards.
        return "critical"
    if neg_pct >= _NEG_CRITICAL_PCT and count >= _NEG_CRITICAL_MIN_N:
        return "critical"
    if neg_pct >= _NEG_ANY_PCT:
        return "warning"
    if avg >= _POSITIVE_AT:
        return "good"
    return "steady"


def _evidence_for(cat: str, sub: pd.DataFrame) -> list[tuple[str, int]]:
    """The top structured answers for a category, as `(label, count)` pairs."""
    key = {
        "Course Content": "emphasis_areas",
        "Lecturer Teaching Style": "challenges",
        "Facilities": "facilities_flagged",
        "Curriculum": "missing_topics",
    }[cat]
    items: list[str] = []
    for raw in sub.get("context_data", []):
        items.extend(context_text_list(parse_context(raw).get(key), limit=40))
    return Counter(items).most_common(3)


def _reach(sub: pd.DataFrame) -> tuple[int, int]:
    """(distinct students, distinct levels) behind a category's numbers.

    `responses` alone is misleading on its own: 40 submissions from one student
    is one opinion recorded forty times, and 40 from forty students is a
    different claim entirely. Both numbers are shown so the reader can tell
    which they are looking at.
    """
    students = {str(u).strip().lower() for u in sub.get("username", []) if str(u).strip()}
    levels = {str(v).strip() for v in sub.get("student_level", []) if str(v).strip()}
    return len(students), len(levels)


def _briefing_rows(items, notes) -> list[dict]:
    """One plain-data row per category for the briefing exporters below.

    Both the Markdown and the PDF builders read from here, so the two files
    can never disagree about the numbers — the only difference between them
    is presentation. Everything returned is plain data (no markup), and the
    PDF builder escapes it for reportlab's XML-ish paragraphs at render time.
    """
    rows = []
    for it in items or []:
        cat = it.get("cat", "")
        cfg = PRIORITY_CONFIG.get(it.get("priority"), {})
        rows.append({
            "cat": cat,
            "priority": cfg.get("label", it.get("priority", "")),
            "avg": it.get("avg", "—"),
            "count": it.get("count", 0),
            "students": it.get("students", 0),
            "levels": it.get("levels", 0),
            "pos": it.get("pos", 0),
            "neu": it.get("neu", 0),
            "neg": it.get("neg", 0),
            "neg_pct": it.get("neg_pct", 0),
            "evidence": ", ".join(it.get("top_items") or []) or "None flagged",
            "directive": (notes.get(cat, {}) or {}).get("note")
                         or "No action directive recorded.",
        })
    return rows


def _build_briefing_md(*, session_label: str, generated_on: str, health: str,
                       avg_all, total, neg_pct_total, items, notes) -> str:
    """The briefing as Markdown text (also the no-reportlab fallback)."""
    md = (
        f"# Federal University of Technology, Owerri (FUTO)\n"
        f"## Department of Information Technology (IFT)\n"
        f"### Executive Academic Feedback & Decision Briefing\n\n"
        f"**Academic Session:** {session_label}  \n"
        f"**Generated On:** {generated_on}  \n"
        f"**Overall System Health:** {health}  \n"
        f"**Departmental Average Rating:** {avg_all} / 5.0  \n"
        f"**Total Student Feedback Submissions:** {total}  \n"
        f"**Negative Feedback Share:** {neg_pct_total}%  \n\n"
        f"---\n\n"
        f"### Category Assessments & Action Plan Matrix\n\n"
    )
    for row in _briefing_rows(items, notes):
        md += (
            f"#### {row['cat']}\n"
            f"- **Priority Status:** {row['priority']}\n"
            f"- **Rating Score:** {row['avg']}/5.0 across {row['count']} submissions "
            f"({row['students']} students, {row['levels']} levels)\n"
            f"- **Sentiment Split:** Positive: {row['pos']} | Neutral: {row['neu']} | "
            f"Negative: {row['neg']} ({row['neg_pct']}%)\n"
            f"- **Key Feedback Evidence:** {row['evidence']}\n"
            f"- **Departmental Action Directive:** {row['directive']}\n\n"
        )
    return md


def _build_briefing_pdf(*, session_label: str, generated_on: str, health: str,
                        avg_all, total, neg_pct_total, items, notes) -> bytes | None:
    """The briefing as a print-ready PDF, or None when reportlab is absent.

    reportlab is a declared dependency, so None only happens on a stale
    install — in which case the caller serves the Markdown instead of a dead
    button. Returns raw PDF bytes otherwise. All dynamic text goes through
    `_xml_escape`: admin directives and course names are free text, and an
    unescaped `&` or `<` in either would corrupt the whole document (or worse,
    smuggle markup into a file the board will open).
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle)
    except ImportError:
        return None

    import io as _io

    navy = colors.HexColor("#0f172a")
    slate = colors.HexColor("#475569")
    light = colors.HexColor("#f1f5f9")
    thin = colors.HexColor("#cbd5e1")

    title = ParagraphStyle("Title2", fontName="Helvetica-Bold", fontSize=17,
                           leading=21, textColor=navy, spaceAfter=2)
    subtitle = ParagraphStyle("Sub2", fontName="Helvetica-Bold", fontSize=11,
                              leading=14, textColor=navy, spaceBefore=10,
                              spaceAfter=4)
    body = ParagraphStyle("Body2", fontName="Helvetica", fontSize=9,
                          leading=12.5, textColor=colors.black, spaceAfter=3)
    meta = ParagraphStyle("Meta2", fontName="Helvetica", fontSize=9,
                          leading=12.5, textColor=slate, spaceAfter=1)
    cell = ParagraphStyle("Cell2", fontName="Helvetica", fontSize=8,
                          leading=10.5, textColor=colors.black)
    cell_h = ParagraphStyle("CellH2", fontName="Helvetica-Bold", fontSize=8,
                            leading=10.5, textColor=colors.white)

    def tx(value) -> str:
        return _xml_escape("" if value is None else str(value))

    story = [
        Paragraph(tx("Federal University of Technology, Owerri (FUTO)"), title),
        Paragraph(tx("Department of Information Technology (IFT) — "
                     "Executive Academic Feedback & Decision Briefing"), subtitle),
        Paragraph(tx(f"Academic Session: {session_label}  ·  Generated: {generated_on}"),
                  meta),
        Paragraph(tx(f"Overall Health: {health}  ·  Average Rating: {avg_all} / 5.0  ·  "
                     f"Submissions: {total}  ·  Negative Share: {neg_pct_total}%"),
                  meta),
        Spacer(1, 6),
    ]

    rows = _briefing_rows(items, notes)
    table_data = [[Paragraph("<b>Category</b>", cell_h),
                   Paragraph("<b>Priority</b>", cell_h),
                   Paragraph("<b>Avg / 5</b>", cell_h),
                   Paragraph("<b>n</b>", cell_h),
                   Paragraph("<b>Neg %</b>", cell_h)]]
    for row in rows:
        table_data.append([Paragraph(tx(row["cat"]), cell),
                           Paragraph(tx(row["priority"]), cell),
                           Paragraph(tx(row["avg"]), cell),
                           Paragraph(tx(row["count"]), cell),
                           Paragraph(tx(row["neg_pct"]), cell)])
    summary = Table(table_data, colWidths=[150, 130, 55, 45, 55], repeatRows=1)
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.6, thin),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [summary, Spacer(1, 8)]

    for row in rows:
        story.append(Paragraph(tx(row["cat"]), subtitle))
        story.append(Paragraph(
            tx(f"Priority: {row['priority']}  ·  Rating: {row['avg']}/5.0 across "
               f"{row['count']} submissions ({row['students']} students, "
               f"{row['levels']} levels)"), body))
        story.append(Paragraph(
            tx(f"Sentiment — Positive: {row['pos']} · Neutral: {row['neu']} · "
               f"Negative: {row['neg']} ({row['neg_pct']}%)"), body))
        story.append(Paragraph(tx(f"Key evidence: {row['evidence']}"), body))
        story.append(Paragraph(tx(f"Action directive: {row['directive']}"), body))
        story.append(Spacer(1, 4))

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm,
                            rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm,
                            title="FUTO IFT Executive Briefing",
                            author="FUTO IFT Feedback System")
    doc.build(story)
    return buf.getvalue()


def show_decision_support(admin_username: str = "admin", session: str | None = None,
                          heading: bool = True):
    """The category-by-category assessment and its recommended actions.

    `heading=False` lets the Full Dashboard embed the same analysis under its
    own section header instead of this page's, which reads as a second page
    title in the middle of one. The two render the same numbers, so a reader who
    lands on either page sees the same assessment.
    """
    active_sess = session or ALL_SESSIONS_LABEL
    if heading:
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
    # The system-wide verdict uses the same thresholds as every category card.
    # It used to cut on the average alone (>= 4 Excellent, >= 3.5 Good, else
    # Needs Work), which could report "Good" for a session that a third of
    # students rated 1-2 — the same disagreement between mean and distribution
    # that was fixed on the cards, in one place higher up.
    health = ("Excellent" if neg_pct_total < _NEG_ANY_PCT and avg_all >= _POSITIVE_AT
              else "Good" if neg_pct_total < _NEG_ANY_PCT
              else "Mixed" if neg_pct_total < _NEG_CRITICAL_PCT
              else "Needs Work")
    health_icon = ("heart" if health == "Excellent" else "check-circle" if health == "Good"
                   else "meh" if health == "Mixed" else "alert-triangle")
    health_accent = ("green" if health in ("Excellent", "Good")
                     else "gold" if health == "Mixed" else "purple")

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
        # `effective_sentiment`, not `rating`, so an administrator's correction
        # is counted here too — the label below has to reflect what the row
        # actually displays everywhere else on the page.
        sentiments = sub["effective_sentiment"]
        neg = int(sentiments.eq("Negative").sum())
        pos = int(sentiments.eq("Positive").sum())
        neu = int(len(sub) - neg - pos)
        neg_pct = neg / len(sub) * 100 if len(sub) else 0
        priority = _band(neg_pct, avg, len(sub))
        students, levels = _reach(sub)
        # `context_data` is free-form JSON, not a constrained enum. See the note
        # on full_dashboard's identical block: `context_text_list` drops
        # non-scalar elements so `Counter` cannot be handed an unhashable value,
        # which raised TypeError and killed the page.
        top_items = [item for item, _ in _evidence_for(cat, sub)]
        # The full distribution, not just the winner. A single headline figure
        # hides the disagreement that makes a problem actionable: a 40/30/30
        # split reads very differently from one flat 70% top answer, and an
        # administrator acting on the top answer alone under-reacts to the
        # students who chose otherwise.
        counts = dict(_evidence_for(cat, sub))
        items.append({"cat": cat, "avg": round(avg, 2), "count": len(sub),
                      "neg_pct": round(neg_pct, 1), "priority": priority,
                      "neg": neg, "neu": neu, "pos": pos,
                      "top_items": top_items, "evidence": counts,
                      "students": students, "levels": levels})

    # Worst first, and within a band by the size of the negative share rather
    # than by the average. Sorting by average is what put a 2-and-5 category
    # (50% negative) below three neutral ones.
    _BAND_ORDER = {"critical": 0, "warning": 1, "steady": 2, "good": 3}
    for item in sorted(items,
                       key=lambda x: (_BAND_ORDER[x["priority"]], -x["neg_pct"], x["avg"])):
        cfg = PRIORITY_CONFIG[item["priority"]]
        neg_clr = ("#ef4444" if item["neg_pct"] >= _NEG_CRITICAL_PCT
                   else "#f59e0b" if item["neg_pct"] >= _NEG_ANY_PCT else "#10b981")
        rating_clr = cfg["color"]

        # ── When the average is not describing anybody ────────────────────
        # A mean built from opposed ratings belongs to nobody. Two responses of
        # 2 and 5 average to 3.5 — a number that looks unremarkable and
        # describes neither student. The rating stays on the card, because
        # omitting it would be hiding data, but the distribution is shown next
        # to it so the average is read as what it is.
        # Built already-escaped — every part is escaped where it is interpolated — so
        # it is inserted whole. Escaping the assembled string on top would
        # double-encode the `&ndash;` entities below, and the static XSS gate
        # reads names rather than provenance, so it needs a justified entry
        # either way (see SAFE_NAMES in test_xss_static.py).
        spread_note = ""
        if item["count"] >= 2 and item["neg"] > 0 and item["pos"] > 0:
            spread_note = (
                f'<div class="insight-split-note">'
                f'{i("alert-circle", 14, cfg["color"])}'
                f'<span>The {item["avg"]} average spans opposed opinions — '
                f'{esc(item["neg"])} response{"" if item["neg"] == 1 else "s"} rated 1&ndash;2 and '
                f'{esc(item["pos"])} rated 4&ndash;5. Read the split, not the mean.</span></div>'
            )

        ctx_insight_html = ""
        if item["top_items"]:
            # esc() is not optional here. Every one of these strings came out
            # of the `context_data` JSON blob, and that column is not
            # constrained to the option lists in config.py — one
            # `<img onerror=…>` typed into a "course name" would otherwise
            # execute in every admin's browser. full_dashboard.py made exactly
            # this fix for the identical data; this page was missed.
            #
            # The count is shown beside each tag, and the full spread below the
            # row. The top item alone is the number most likely to be quoted
            # out of context — "the top issue is pace of delivery" is a very
            # different intervention depending on whether 8 students or 1 did.
            # Every value below crossed out of `context_data` — a free-form JSON
            # column with no constraint on what a crafted request could put in
            # it — or out of a row's numeric columns. `test_xss_static.py`
            # requires anything reaching `unsafe_allow_html` to be escaped or
            # justified by name, and the gate reads names, not provenance. So
            # each is rendered here, through `esc()`, and the assembled strings
            # (`_spread`, `_tags_html`) are interpolated as whole values.
            counts = Counter(item["evidence"])
            total_flags = int(sum(counts.values())) or 1
            top_share = int(round(max(counts.values()) / total_flags * 100))
            tag_html = "".join(
                f'<span style="background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.2);'
                f'border-radius:6px;padding:.12rem .5rem;font-size:.7rem;font-weight:600;'
                f'color:#3b82f6;margin:.15rem .2rem;display:inline-block;">{esc(t)}'
                f'<span style="opacity:.65;font-weight:700;">&nbsp;'
                f'{esc(item["evidence"].get(t, 0))}</span></span>'
                for t in item["top_items"]
            )
            # Built already-escaped. Escaping the *joined* string on top would double-encode
            # the ampersands inside a label like "Labs & equipment", so each part
            # is escaped and the result is used whole — which is also what the
            # static gate can see.
            spread = ", ".join(
                f"{esc(str(label))} ({esc(n)})"
                for label, n in counts.most_common()
            )
            ctx_insight_html = (
                f'<div style="margin-top:.9rem;padding:.8rem 1rem;background:rgba(139,92,246,.04);'
                f'border:1px solid rgba(139,92,246,.15);border-radius:8px;">'
                f'<div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;'
                f'color:#7c3aed;font-weight:700;margin-bottom:.5rem;">'
                f'{i("microscope", 12, "#7c3aed")} {CTX_REC_TEMPLATES.get(item["cat"], "Key findings")}</div>'
                f"{tag_html}"
                f'<div style="font-size:.7rem;color:var(--text-3);margin-top:.55rem;'
                f'line-height:1.5;">{spread}</div>'
                f'<div style="font-size:.7rem;color:var(--text-3);margin-top:.35rem;">'
                f'The most-flagged item accounts for <strong>{esc(top_share)}%</strong> of '
                f'{esc(total_flags)} flag(s) in this category.'
                f'</div></div>'
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
            # The counts behind that percentage, so the label and the figure can
            # be checked against each other without going back to the database.
            # These three numbers are what the label is actually derived from.
            f'<div class="insight-split">'
            f'<span class="insight-split-pill" style="background:rgba(16,185,129,.08);'
            f'border:1px solid rgba(16,185,129,.22);color:#059669;">'
            f'{i("smile", 12, "#059669")} Positive <strong>{esc(item["pos"])}</strong></span>'
            f'<span class="insight-split-pill" style="background:rgba(245,158,11,.08);'
            f'border:1px solid rgba(245,158,11,.22);color:#d97706;">'
            f'{i("meh", 12, "#d97706")} Neutral <strong>{esc(item["neu"])}</strong></span>'
            f'<span class="insight-split-pill" style="background:rgba(239,68,68,.08);'
            f'border:1px solid rgba(239,68,68,.22);color:#dc2626;">'
            f'{i("frown", 12, "#dc2626")} Negative <strong>{esc(item["neg"])}</strong></span>'
            f"</div>"
            f"{spread_note}"
            f'<div class="insight-rec">{i("lightbulb", 16)}<span>{cfg["rec"]}</span></div>'
            f'<ul class="playbook-list">'
            + "".join(
                f'<li>{esc(step)}</li>'
                for step in _PLAYBOOK[item["priority"]][:3]
            )
            + "</ul>"
            f'<div class="insight-metrics" style="margin-top:.85rem;">'
            f'<div class="insight-metric"><div class="insight-metric-value" '
            f'style="font-size:1rem;color:var(--text-2);">{esc(item["students"])}</div>'
            f'<div class="insight-metric-label">Students</div></div>'
            f'<div class="insight-metric"><div class="insight-metric-value" '
            f'style="font-size:1rem;color:var(--text-2);">{esc(item["levels"])}</div>'
            f'<div class="insight-metric-label">Levels reached</div></div>'
            f'<div class="insight-metric"><div class="insight-metric-value" '
            f'style="font-size:1rem;color:var(--text-2);">{item["count"]}</div>'
            f'<div class="insight-metric-label">Submissions</div></div>'
            f"</div>"
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

    section_header("clipboard-list", "Departmental Action Plan Matrix")
    matrix_rows = []
    for item in items:
        c_name = item["cat"]
        c_note_obj = notes.get(c_name, {})
        c_note_text = c_note_obj.get("note", "").strip()
        c_prio = item["priority"]
        cfg = PRIORITY_CONFIG[c_prio]

        if c_prio == "good":
            st_class = "is-resolved"
            st_text = "Benchmark"
        elif c_note_text:
            st_class = "is-progress"
            st_text = "In Progress"
        else:
            st_class = "is-pending"
            st_text = "Pending Directive"

        note_display = c_note_text if c_note_text else "No administrative directive logged yet. Open the note editor above to record action."
        meta_author = f"By {c_note_obj.get('updated_by', '—')}" if c_note_text else "Awaiting entry"
        meta_time = str(c_note_obj.get("updated_at", ""))[:16]

        matrix_rows.append(
            f'<div class="action-matrix-row">'
            f'<div class="action-matrix-cat">{i(CAT_META[c_name]["icon"], 16, "#3b82f6")} {esc(c_name)}</div>'
            f'<div><span class="action-matrix-badge" style="background:{cfg["bg"]};color:{cfg["color"]};border:1px solid {cfg["border"]};">'
            f'{i(cfg["label_icon"], 11, cfg["color"])} {esc(cfg["label"])}</span></div>'
            f'<div class="action-matrix-note">{esc(note_display)}</div>'
            f'<div>'
            f'<div class="action-matrix-status {esc(st_class)}">{esc(st_text)}</div>'
            f'<div class="action-matrix-meta">{esc(meta_author)}<br>{esc(meta_time)}</div>'
            f'</div>'
            f'</div>'
        )

    matrix_html = "".join(matrix_rows)
    st.markdown(
        f'<div class="action-matrix-card">'
        f'<div class="action-matrix-header">'
        f'<div class="action-matrix-title">{i("clipboard-list", 16, "#2563eb")} Active Departmental Interventions & Directives</div>'
        f'<div class="action-matrix-subtitle">Consolidated action status for HOD and academic committees ({esc(active_sess)})</div>'
        f'</div>'
        f'{matrix_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Executive Briefing Document Generator ──
    # PDF when reportlab is installed (a declared dependency), Markdown when
    # it is not — the button below always names the format it will actually
    # deliver, so a stale install degrades to .md instead of a dead click.
    _brief_kw = dict(session_label=active_sess,
                     generated_on=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     health=health, avg_all=avg_all, total=total,
                     neg_pct_total=neg_pct_total, items=items, notes=notes)
    briefing_pdf = _build_briefing_pdf(**_brief_kw)
    if briefing_pdf is not None:
        _brief_label = "Download Executive Briefing (.pdf)"
        _brief_data = briefing_pdf
        _brief_file = f"FUTO_IFT_Executive_Briefing_{active_sess.replace('/', '_')}.pdf"
        _brief_mime = "application/pdf"
    else:
        briefing_md = _build_briefing_md(**_brief_kw)
        _brief_label = "Download Executive Briefing (.md)"
        _brief_data = briefing_md.encode("utf-8")
        _brief_file = f"FUTO_IFT_Executive_Briefing_{active_sess.replace('/', '_')}.md"
        _brief_mime = "text/markdown"

    st.markdown(
        f'<div class="exec-briefing-card">'
        f'<div class="exec-briefing-info">'
        f'<div class="exec-briefing-title">{i("file-text", 18, "#2563eb")} Official Departmental Board Briefing</div>'
        f'<div class="exec-briefing-desc">Export a print-ready executive summary (PDF) for presentation at the IFT Departmental Board or Faculty Academic Board.</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st_compat.download_button(
        _brief_label,
        data=_brief_data,
        file_name=_brief_file,
        mime=_brief_mime,
        icon=":material/download:",
        use_container_width=True,
        type="primary",
    )

    trend_text = ("Positive Trend" if neg_pct_total < _NEG_ANY_PCT and avg_all >= _POSITIVE_AT
                else "Stable" if neg_pct_total < _NEG_CRITICAL_PCT
                else "Declining")
    trend_icon = ("trending-up" if trend_text == "Positive Trend"
                  else "circle-dot" if trend_text == "Stable" else "trending-down")
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
