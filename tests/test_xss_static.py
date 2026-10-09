"""Static XSS gate — plan items B-14 / B-15, T-11.

Every `st.markdown(..., unsafe_allow_html=True)` in this app is a place where
a student-typed string can become live HTML. The fix applied across the
codebase is `components.esc()` on interpolation, plus `html_alert()`, which
escapes by default.

WHAT THIS CHECKS
----------------
Two kinds of site, both found by matching the call that owns them:

  1. A render call — `st.markdown(`, `st.html(`, `html_alert(`, `html_metric(`,
     `page_header(`, `section_header(`, `empty_state(` — whose source spans
     back to its own opening line and forward to the `unsafe_allow_html=True`
     keyword.

  2. An HTML *builder* — a statement of the form `x = f'...<tag>...'` or
     `x += f'...<tag>...'` whose value is later interpolated into a render
     call. The placeholder in the render call (`{rows_html}`) is opaque, so
     the escaping decision is audited at the point the markup is built.

A placeholder inside either site FAILS unless it is:

  * wrapped in a known-safe call — `esc(`, `i(` (returns in-repo SVG), or a
    numeric/string coercion;
  * a literal, a format specifier, or an expression over those; or
  * on `SAFE_NAMES`, each entry carrying a one-line justification.

WHY A WHITELIST AND NOT A BLOCKLIST
-----------------------------------
The first version of this file used a blocklist of "suspicious" names. It
reported a clean tree while `decision_insights.py` interpolated `{t}` — a loop
variable over `context_data`, the one column in this schema that really is
free text — straight into an admin page. `full_dashboard.py` had the identical
block and *had* been fixed; this page was simply missed. A blocklist can only
catch names somebody remembered to add. A whitelist catches every name
nobody did.

KNOWN LIMITS, STATED PLAINLY
---------------------------
This reads variable *names*, not values, so it cannot see that `engine_label`
was escaped three lines above its assignment, nor that `rows_html` is built
only from `esc()`'d parts. Those are on `SAFE_NAMES` because a human read
them. The complementary check is a runtime one: submit
`<script>alert(1)</script>` as a comment, a lecturer name, a course name and
a location, then view Overview, Full Dashboard, Decision Insights, My
Statistics and User Management as both roles. This file cannot replace that;
It can only stop the next hole being added unnoticed.

Run:  .venv\\Scripts\\python.exe tests\\test_xss_static.py
"""
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)

# ── Site detection ─────────────────────────────────────────────────────
# A render call that may receive raw HTML. The scan starts at the line that
# opens the call and stops at the `unsafe_allow_html=True` keyword, so the
# window is the block itself and nothing else.
RENDER_OPEN = re.compile(
    r"^\s*(?:st\.(?:markdown|html)\s*\(|"
    r"(?:html_alert|html_metric|page_header|section_header|empty_state|"
    r"progress_bar)\s*\()"
)
# `st.markdown(f"""...` with no paren-break — same idea, looser anchor.
RENDER_OPEN_INLINE = re.compile(
    r"\b(?:st\.markdown|st\.html|html_alert|html_metric|page_header|"
    r"section_header|empty_state|progress_bar)\s*\("
)
UNSAFE_KW = re.compile(r"unsafe_allow_html\s*=\s*True")

# An f-string literal — single, double or triple quoted, possibly spanning
# lines. `\\.` consumes an escape so an escaped quote does not end the match
# early. This is the primary unit of analysis: scanning string literals
# rather than statements means `''.join(f'…{t}…' for t in items)` is caught
# exactly as reliably as `x = f'…{t}…'`, which is the shape the live
# decision_insights.py bug had and which a statement matcher missed.
FSTRING = re.compile(r"""f(['"]{1,3})(?:\\.|(?!\1)[\s\S])*?\1""")
# What makes a string "markup" rather than an ordinary message.
HAS_TAG = re.compile(r"<\s*/?[a-zA-Z][a-zA-Z0-9]*[\s>/]")

# ── Placeholder classification ─────────────────────────────────────────
PLACEHOLDER = re.compile(r"\{([^{}\n]{1,160})\}")
# A format specifier — `{x:.2f}`, `{x:+,.0f}` — the value is a number.
FMT_SPEC = re.compile(r"^[^{}]+:[^{}]*$")
# Wrappers whose return value cannot contain a raw `<` from user input.
# `i`/`icon`/`icon_badge` return SVG inlined from icons.py, never fetched.
# `_safe_attr` is icons.py's own sanitiser: it returns "" unless the whole
# value matches the passed pattern, so it is the escape hatch *for
# attributes*, and treat it as one.
#
# ANCHORED at the start. The escape wrappers in the first group are
# deliberately not in this list — they are handled by CONTAINS_ESCAPE, which
# matches an escape anywhere in the expression and so also covers
# `{' · ' + esc(x) if x else ''}`. Listing `esc` here as well made the two
# rules exact duplicates: the self-test's mutation check showed that disabling
# CONTAINS_ESCAPE changed no verdict, because every case this branch caught,
# that branch caught too.
SAFE_CALL = re.compile(
    r"^\s*(quote|urlencode|i|icon|icon_badge|format|iif|"
    r"_safe_attr|len|int|float|str|bool|abs|max|min|sum|round|sorted)\s*\("
)
# A conditional whose branches are all string literals, and a `.get()` whose
# default is a literal — both are developer-authored by construction.
LITERAL_ONLY = re.compile(r"""^\s*["'].*["']\s*(if|else).*["'].*["']\s*$""")
GET_WITH_LITERAL_DEFAULT = re.compile(r""".get\([^,]+,\s*["'][^"']*["']\s*\)$""")
# A container built entirely from literals — `{"displayModeBar": False}`.
# PLACEHOLDER has already stripped the outer braces, so this matches the
# *body*: a quoted key, a colon, and a literal value.
KEY_VALUE_LITERAL = re.compile(
    r"""^\s*["'][\w \-]+["']\s*:\s*(?:True|False|None|\d+(?:\.\d+)?|"""
    r"""(?:"[^"]*"|'[^']*'))\s*$"""
)
# Arithmetic or comparison over bare names — `{total - pos - neg}`, `{n - 1}`.
# No string literal in sight, so whatever it evaluates to cannot open a tag.
#
# Two separate conditions, and the second one is the important one.
#
# The first version of this rule was a single charset match with no operator
# required, which a bare identifier like `full_name` satisfies. The gate then
# reported a clean tree for `f'<div title="{full_name}">'` — an unescaped
# user-supplied name inside an HTML attribute, and precisely the thing it
# was written to catch. A "probably a number" heuristic has to require
# positive evidence of being a number.
#
# The rewrite then required the operator, but placed it only in the middle of
# the pattern, so `{total - total_pos - total_neg}` — two operators — stopped
# matching and was reported as unproven. Hence: allowed charset everywhere,
# and at least one operator somewhere in it.
ARITHMETIC_CHARS = re.compile(r"^[\s\w\.\(\)\[\]\+\-\*/%<>=!:]+$")
ARITHMETIC_OP = re.compile(r"[-+*/%<>=!]")
# An escape anywhere inside the placeholder, not just at the start:
# `{' · ' + esc(x) if x else ''}`, `{esc(a)}/{esc(b)}`. SAFE_CALL only matches
# when the escape is the *outermost* call, so this covers the composite forms.
#
# There was a moment when this rule and SAFE_CALL's `esc` branch were both
# required, and the self-test's mutation check proved it: disabling
# CONTAINS_ESCAPE changed no verdict, because every fixture SAFE_CALL was
# already catching was the same fixture. Two rules covering one case is one
# rule plus a maintenance trap, so CONTAINS_ESCAPE was folded into SAFE_CALL
# by widening SAFE_CALL to "contains an escape" and dropping the anchor.
CONTAINS_ESCAPE = re.compile(r"\b(?:esc|html\.escape|_esc)\s*\(")

# ── Audited safe names ─────────────────────────────────────────────────
#
# Keys are `"<module path>|<regex>"`, with the module path relative to ROOT
# and `/`-separated. An empty path before the bar applies to every file.
#
# WHY SCOPED, AND WHEN TO LEAVE THE PATH EMPTY
# --------------------------------------------
# An earlier version of this file had one global list. It was wrong in a way
# that hid a bug: `{body}` is safe in `components.html_alert`, which esc()s it,
# and the self-test showed that entry was also silencing a bare `{body}` in a
# page where nothing escaped it. An allowlist entry is only valid where its
# justification holds, so entries whose safety depends on the *call site* must
# name the file. Entries whose safety depends on the *value* — `cat` is a
# config constant no matter where it is used — may stay global.
#
# Every entry below was written after reading the line it covers. An entry
# with no reason is not an entry.
#
# SEPARATOR splits a file-scoped key. It is not `|` because regexes here use
# `|` for alternation.
SEPARATOR = " :: "
SAFE_NAMES = {
    # ═══ Global: the value is safe wherever it appears ═════════════════
    # (keys with no SEPARATOR in them)

    # Category names. Every call site in every page loops `for cat in
    # CATEGORIES`, so the value is a config.py constant and can never be a
    # DB string. feedback.category is never interpolated without one of
    # these variables holding it first.
    r"^cat$": "config.CATEGORIES member — every call site loops CATEGORIES",
    r"^category$": "the page's CATEGORIES key, chosen by the sidebar radio",
    r"^CAT_META\[cat\]\[\"desc\"\]\[:\d+\]$": "config.CAT_META constant",
    r"^meta\[\"desc\"\]$": "config.CAT_META constant",

    # Closed-set sentiment labels and confidence tiers. sentiment.py emits
    # exactly {Positive, Neutral, Negative} and five tier names, and the
    # admin correction selectbox offers only the first three — so
    # effective_sentiment cannot hold anything else either.
    r"^top_s$": "a value_counts().idxmax() over the closed sentiment set",
    r"^result\.label$": "sentiment.py label — one of three",
    r"^conf_label$": "sentiment.confidence_tier() — one of five",
    r"^sent$": "a closed-set sentiment label",
    r"^tier$": "sentiment.confidence_tier() — one of five",

    # Counts and aggregates. All are len(), nunique(), .sum() or
    # round(mean(), n) — a number cannot open a tag.
    r"^total$": "len(df) — an int",
    r"^total_pos$": "an .eq('Positive').sum() — an int",
    r"^total_neg$": "an .eq('Negative').sum() — an int",
    r"^pos_total$": "an .eq('Positive').sum() — an int",
    r"^neutral_total$": "an .eq('Neutral').sum() — an int",
    r"^neg_total$": "an .eq('Negative').sum() — an int",
    r"^neg_pct$": "round(neg / total * 100, 1) — a float",
    r"^neg_pct_total$": "round(neg / total * 100, 1) — a float",
    r"^avg_all$": "round(df['rating'].mean(), 1) — a float",
    r"^avg$": "round(sub['rating'].mean(), 1) — a float",
    r"^avg_val$": "int(row['rating']), round(mean(), 1), or the literal '—'",
    r"^cnt$": "len(sub) — an int",
    r"^count$": "len(sub) — an int",
    r"^n$": "len(sub) — an int",
    r"^idx$": "enumerate's index — an int",
    r"^remaining$": "len(CATEGORIES) - mine — an int",
    r"^pct$": "a rounded percentage — an int",
    r"^pct_complete$": "round(done / total * 100) — an int",
    r"^completion$": "a rounded percentage — an int",
    r"^conf_pct$": "f'{p:.0%}' — a float",
    r"^count_label$": "a literal, or f'{len(sub)} responses · {pct}% …'",
    r"^respondents$": "nunique() — an int",
    r"^users$": "nunique() — an int",
    r"^categories_active$": "a count of categories with responses — an int",
    r"^cats_monitored$": "len(items) — an int",
    r"^corrected_count$": "a count — an int",
    r"^n_fb$": "len() — an int",
    r"^n_corr$": "len() — an int",
    r"^n_samp$": "len(labeled) — an int, esc()'d at assignment",
    r"^total_feedback$": "a get_session_stats() int",
    r"^avg_rating$": "a get_session_stats() float",
    r"^unique_students$": "a get_session_stats() int",
    r'^s_stat\["(total_feedback|unique_students|avg_rating)"\]$':
        "get_session_stats() aggregates — a float/int from pandas",
    r"^df\[\"category\"\]\.nunique\(\)$": "an int",
    r"^item\[\"count\"\]$": "len(sub) — an int",
    r"^item\[\"avg\"\]$": "round(mean(), 2) — a float",
    r"^item\[\"neg_pct\"\]$": "round(x, 1) — a float",
    r"^item\[\"cat\"\]$": "config.CATEGORIES member — items are built by looping CATEGORIES",
    r"^item\['cat'\]$": "config.CATEGORIES member, in st.toast (Streamlit-escaped)",
    r"^cfg\[\"[a-z_]+\"\]$": "the module-level PRIORITY_CONFIG dict — colours and "
                            "literal copy",
    r"^sentiment_color\(sent\)$": "icons.sentiment_color maps the closed "
                                 "sentiment set onto a hex literal",
    r"^trend_text$": "one of two string literals",
    r"^level_label$": "a literal in config.LEVELS",
    r"^semester$": "a literal in config.SEMESTERS",
    r"^level$": "a literal in config.LEVELS, chosen by a selectbox",
    r"^labels\[rating\]$": "a local list of string literals in feedback_form.py",
    r"^colors\[rating\]$": "a local list of hex literals in feedback_form.py",

    # Colours and other values chosen by a comparison against a literal, or
    # looked up in a module-level palette. No user text is involved in
    # reaching any of them.
    r"^(rating_clr|sent_clr|neg_clr|clr|clr2|accent|tint|fill_style|color)$":
        "a hex literal or keyword chosen by a numeric comparison, or from a "
        "module-level palette",
    r"^(bg|bdr|lbr|lc|lb|engine_color|engine_dot|engine_bg|engine_border)$":
        "a hex literal from a module-level palette, assigned in the same function",
    r"^(pos_w|neu_w|neg_w)$": "floats from the sentiment split, format-literal",
    r"^trend_icon$": "a literal icon name",
    r"^health$": "a literal, or a config.py string",
    r"^kind$": "a literal alert kind — one of six keywords",
    r"^badge$": "a literal 'Submitted'/'Pending' span built in home.py",
    r"^title$|^desc$|^icon_name$": "a literal in login.py's FEATURES list",
    r"^displayModeBar$": "a Plotly layout literal",
    r"^effective_sentiment$": "a DataFrame column rename — a literal",
    r"^datetime\.now\(\)\.year$": "an int",
    r"^ADMIN_DELETE_PHRASE$": "a module-level constant in user_management.py",

    # A value escaped at the point of construction, so escaping again at the
    # placeholder would be pointless. Each of these was read and confirmed.
    r"^sess_hint$": "feedback_form.py: f'…<strong>{esc(session_name)}</strong>…'",
    r"^ctx_hint$": "my_stats.py: all 4 branches wrap in esc()",
    r"^top_ctx$": "full_dashboard.py: esc(most_common[0][0]) in its only assignment",
    r"^pos_cues_html$": "full_dashboard.py: every tag inside is esc(c)",
    r"^neg_cues_html$": "full_dashboard.py: every tag inside is esc(c)",
    r"^trained_meta_html$": "full_dashboard.py: acc/f1 are floats, dates are esc()'d",
    r"^acc_txt$|^f1_txt$": "full_dashboard.py: _as_float() then esc()",
    r"^trained_at$": "full_dashboard.py: esc()'d at its only assignment",
    r"^contrast_html$": "full_dashboard.py: floats and literals only",
    r"^badge_html$": "built from counts, colours and literals only",
    r"^conf_badge$": "_confidence_pill: a tier name and a hex literal",
    r"^status_html$": "my_stats.py: a rating int, a closed-set label, "
                        "_confidence_pill and i()",
    r"^rows_html$": "feedback_form.py: every field goes through esc() or "
                      "render_tag_list(), which escapes each element",
    r"^tags$": "render_tag_list(), which escapes every element",
    r"^ctx_insight_html$": "decision_insights.py: esc(t) per tag, plus a "
                             "literal from CTX_REC_TEMPLATES",
    r"^tag_html$": "decision_insights.py: esc(t) per tag",
    r"^spread$": "decision_insights.py: built by joining esc()'d label and count "
                   "pairs, then interpolated whole",
    r"^spread_note$": "decision_insights.py: every interpolated part is esc()'d "
                      "at the point it is built, then inserted whole — escaping "
                      "it again would double-encode the &ndash; entities",
    r"^sent_safe$": "feedback_form.py: esc()'d at its only assignment",
    r"^sent_colour$": "sentiment.label_color() — one of three hex literals, "
                         "returned from a fixed dict keyed by the closed label set",
    r"^tag_html$": "targets.py: esc(t) per tag via _tags()",
    r"^feature_cards$": "login.py: a comprehension over the FEATURES literal list",
    r"^engine_label$": "full_dashboard.py: esc()'d or a literal in all 3 branches",
    
    r"^conf_range$": "sentiment.engine_status()['confidence_range'], esc()'d",
    r"^_thresholds$": "full_dashboard.py: sentiment.engine_status()"
                        "['rating_thresholds'], esc()'d at assignment",
    r"^_badge_style\(" : "targets.py: a helper that returns a finished style "
                          "string built only from _hex()'d literals",
    r"^_stars\(" : "targets.py: builds SVG from two literals and an int; "
                     "no value from a row reaches it but avg_rating, as int()",
    r"^_icon_wrap\(": "targets.py: a helper returning finished markup; both "
                      "arguments are literals or i() calls",
    r"^_card_open\(": "targets.py: a helper returning finished markup; both "
                      "arguments pass through _hex()",
    r"^_hex\(" : "targets.py: strips every character that is not #0-9a-fA-F, "
                   "so nothing else can reach a style attribute",
    # Scoped to targets.py on purpose. A global `^t$` / `^c$` would be swallowed
    # by every other module's use of those names — and `t` is the loop variable
    # in the exact historical bug this gate exists for
    # (`test_xss_static_selftest.py::bug_loop_var.py`). A generic local name is
    # never safe to allowlist globally; the selftest proves it by failing the
    # moment one is.
    r"app_pages/targets.py :: ^safe_colour$": "_hex()'d — the only value that reaches a "
                                     "style attribute",
    r"app_pages/targets.py :: ^safe_tint$": "_hex()'d, same as safe_colour",
    r"app_pages/targets.py :: ^inner$": "an i() call — an inline SVG from icons.py, "
                              "with its colour already _hex()'d by the caller",
    r"^_count_of\(" : "targets.py: returns esc(value) — the single place a "
                       "count is rendered",
    r"^_star_badge\(" : "targets.py: returns finished markup; its two "
                          "arguments are esc()'d inside it",
    r"^_tags\(" : "targets.py: returns finished markup; each label goes "
                    "through esc() inside it",
    r"^unknown$": "targets.py: one of two literal strings, chosen by a boolean — "
                  "no value from a row reaches it",
    r"^suffix$": "targets.py: f' · {int(count)}' — an int or the empty string",
    r"^_align_top$": "a label from _ALIGN_SCALE, or the literal '—'",
    r"^_align_top_n$": "a count — an int",
    r"^_align_idx$": "an int index into _ALIGN_SCALE",
    r"^_ALIGN_SCALE\[[^\]]+\]$": "a module-level tuple of literal labels",
    r"^star_row\(.*\)$": "components.star_row: in-repo SVG only",

    # ═══ File-scoped: safe only because of what this file does with it ══

    "app.py :: ^label$": "an ADMIN_NAV/STUDENT_NAV entry, both built from "
                       "string literals, or a CATEGORIES member",
    "app.py :: ^engine_dot_color$": "one of two hard-coded hex colours",
    "app.py :: ^sess$": "esc()'d — the session dropdown row",
    "app.py :: ^active_sess$": "esc()'d at the interpolation site",
    r"app.py :: ^user\['email'\]$": "esc()'d",
    "app.py :: ^msg$": "an html_alert() argument, which escapes by default",

    "app_pages/admin_overview.py :: ^active_sess$":
        "esc()'d — page_header/section_header escape their subtitle argument",
    "app_pages/admin_overview.py :: ^sess$": "esc()'d at the interpolation site",

    r"app_pages/home.py :: ^user\['name'\]\.split\(\)\[0\]$":
        "esc()'d at the interpolation site",
    "app_pages/home.py :: ^msg$": "an html_alert() argument, which escapes by default",

    "app_pages/full_dashboard.py :: ^sess$": "esc()'d at the interpolation site",
    "app_pages/full_dashboard.py :: ^active_sess$":
        "esc()'d at the interpolation site",
    "app_pages/full_dashboard.py :: ^msg$":
        "an html_alert() argument, which escapes by default",

    r"app_pages/login.py :: ^user\['email'\]$": "esc()'d",
    "app_pages/login.py :: ^msg$": "an html_alert() argument, which escapes by default",

    # user_management._preview_row(key, value) returns
    #   <div class="confirm-row"><span …>{esc(key)}</span>
    #   <span …>{esc(value)}</span></div>
    # so any value interpolated into one of its f-string arguments is
    # escaped one call later. The call sites are the deletion preview and
    # the confirm dialog, both of which route preview fields, the operator's
    # typed reason and the acting admin's username through it.
    r"app_pages/user_management.py :: ^preview\[.[a-z_]+.\]$":
        "an argument to _preview_row(), which esc()s both key and value",

    # _render_model_training's engine card. Three locals, each read before
    # being recorded here:
    #
    #   dist_cells    every placeholder is esc()'d, class names included —
    #                 the values are a per-class int and a hex literal.
    #   problem_html  each entry is esc(str(p)[:160]); the icon is i(),
    #                 which returns in-repo SVG.
    #   state_line    the has-model branch esc()s all three pickle fields,
    #                 the other branch is a developer-authored literal.
    #
    # The card's other placeholders need no entry: the colour locals are
    # named engine_bg/engine_border/engine_color and are already covered by
    # the global palette entry, and `usable`/`required` are esc()'d inline.
    r"app_pages/user_management.py :: ^dist_cells$":
        "built from esc()'d ints, esc()'d class names and a hex literal",
    r"app_pages/user_management.py :: ^problem_html$":
        "built from i() and esc(str(p)[:160]) per engine problem",
    r"app_pages/user_management.py :: ^state_line$":
        "esc()'d pickle metadata, or a developer-authored literal",

    "components.py :: ^body$": "html_alert: esc()'d unless raw=True, and the only "
                             "raw=True callers pass literals",
    "components.py :: ^_alert$": "html_alert's own markup: esc()'d unless raw=True",
    "components.py :: ^style_class$": "a CSS class name, always a caller-supplied "
                                   "literal, not a user value",
    "components.py :: ^stars$": "star_row's in-repo SVG, i() per star",
    "components.py :: ^root$": "a CSS variable name from a literal selector",
    "components.py :: ^msg$": "an html_alert() argument, which escapes by default",

    # result dialog (components._show_result_dialog). Both are esc()'d into
    # locals a few lines ABOVE the st.markdown call, then interpolated here:
    #   message       = esc(payload["message"])       line 131
    #   details_html  = f'...{esc(payload["details"])}...'  line 133
    # The gate is right to flag them — `message`/`details_html` are ordinary
    # locals, so nothing about the NAME proves they were escaped, and the
    # escaping is the only thing making them safe. If either esc() call is
    # removed these two entries become the only thing standing between a
    # student-controlled string and an HTML sink, which is exactly why they
    # are recorded here rather than worked around.
    "components.py :: ^message$": "_show_result_dialog: assigned from "
                                  "esc(payload['message']) directly above",
    "components.py :: ^details_html$": "_show_result_dialog: built from "
                                       "esc(payload['details']) above",

    "icons.py :: ^size$": "reassigned from _safe_attr(size, _SIZE_RE, '18') "
                         "two lines above — regex-validated",
    "icons.py :: ^color$": "reassigned from _safe_attr(color, _COLOR_RE, …)",
    "icons.py :: ^style_attr$": "built from _safe_attr(style, _STYLE_RE, '')",
    "icons.py :: ^inner$": "a path from the in-repo _SVG_PATHS table, or a literal "
                        "fallback — no user text reaches it",
}


def _build_allowlist_index():
    """Group the allowlist by module, so an entry applies only where its
    justification holds.

    A key is either a bare `<regex>` (applies everywhere) or
    `"<module path> <NUL-free separator> <regex>"`. The separator is
    `SEPARATOR`, not `|`, because several patterns contain `|` as a regex
    alternation — `(bg|bdr|lcr|...)` — and splitting on the first `|` shredded
    those into fragments like `bdr|lcr|…)$`, which fail to compile.

    Every entry is compiled at import time, so a malformed pattern is an
    immediate, loud failure rather than a rule that silently never matches.
    A pattern that matches the empty string is rejected for the same reason:
    It would allowlist every placeholder in the file, which is exactly the
    failure the self-test exists to catch.
    """
    per_file = {}
    glob = []
    for key, why in SAFE_NAMES.items():
        if SEPARATOR in key:
            module, _, pattern = key.partition(SEPARATOR)
            module = module.strip()
        else:
            module, pattern = "", key
        if not pattern:
            raise ValueError(f"empty allowlist pattern in key {key!r}")
        entry = re.compile(pattern)
        if entry.search(""):
            raise ValueError(
                f"allowlist pattern {pattern!r} matches the empty string, so it "
                f"would allowlist every placeholder: {why}"
            )
        if module:
            per_file.setdefault(module, []).append(entry)
        else:
            glob.append(entry)
    index = {"": tuple(glob)}
    for module, entries in per_file.items():
        index[module] = tuple(entries) + tuple(glob)
    return index


SAFE_NAME_RES = _build_allowlist_index()

SKIP = {"tests", "__pycache__", ".venv", "backup", "model", ".git", ".streamlit",
        "nltk_data", ".kilo"}

# Modules that build markup for a browser without ever calling
# `st.markdown(..., unsafe_allow_html=True)` themselves. They are still
# audited, because everything they return is interpolated into a page.
HTML_HELPERS = {"components.py", "icons.py"}


def produces_html(path, src):
    """True if this module ever hands raw markup to a browser.

    Everything else — `email_service.py` builds plain-text MIME bodies,
    `train_model.py` prints a table, `sentiment.py` builds log lines — uses
    f-strings and `.format()` with `<` in them for entirely innocent reasons
    (an `<html>` tag in an email, a `{'Macro F1':<12}` column header). Auditing
    them would mean allowlisting text that never reaches a browser, which is
    how a 100-entry allowlist stops meaning anything.
    """
    return UNSAFE_KW.search(src) is not None or os.path.basename(path) in HTML_HELPERS


def classify(ph, norm_file=""):
    """Return None if provably safe, else a short reason.

    `norm_file` is the module's path relative to ROOT, `/`-separated, and
    selects which audited allowlist entries apply. See SAFE_NAMES.
    """
    ph = ph.strip()
    if not ph:
        return "empty placeholder — st.markdown('…{}…') is a no-op or a crash"
    if CONTAINS_ESCAPE.search(ph):
        return None
    if FMT_SPEC.match(ph) and not ph.startswith(("'", '"')):
        return None
    if SAFE_CALL.match(ph):
        return None
    if LITERAL_ONLY.match(ph):
        return None
    if KEY_VALUE_LITERAL.match(ph):
        return None
    if GET_WITH_LITERAL_DEFAULT.search(ph):
        return None
    if ARITHMETIC_CHARS.match(ph) and ARITHMETIC_OP.search(ph) \
            and '"' not in ph and "'" not in ph:
        return None
    for rx in SAFE_NAME_RES.get(norm_file, SAFE_NAME_RES[""]):
        if rx.search(ph):
            return None
    return "no justification on SAFE_NAMES"


def site_windows(src):
    """Yield (line_no, text) for every span of markup to audit.

    Two independent passes, because markup reaches a browser two ways:

    1. **An f-string literal containing a tag.** This is the primary pass and
       the one that matters. Scanning the *string literals* rather than the
       statement that contains them means `tag_html = ''.join(f'…{t}…' for
       t in items)` is caught just as reliably as `x = f'…{t}…'`, which a
       statement-shape matcher missed — and that is precisely the shape the
       live `decision_insights.py` bug had.

    2. **A render call ending in `unsafe_allow_html=True`.** This catches
       markup built with `.format()` or `%` instead of an f-string, where
       there is no `f'` prefix to find.

    Returns the text of each span so the caller can classify placeholders
    without re-slicing.
    """
    lines = src.split("\n")
    line_of = _LineIndex(src)

    # ── Pass 1: f-string literals containing markup ─────────────────────
    for m in FSTRING.finditer(src):
        text = m.group(0)
        if not HAS_TAG.search(text):
            continue
        yield line_of.at(m.start()), text

    # ── Pass 2: unsafe_allow_html blocks ────────────────────────────────
    for n, line in enumerate(lines):
        if not UNSAFE_KW.search(line):
            continue
        start = n
        for j in range(n, max(-1, n - 80), -1):
            if RENDER_OPEN.match(lines[j]):
                start = j
                break
        else:
            for j in range(n, max(-1, n - 80), -1):
                s = lines[j].rstrip()
                if s.endswith(("f'", 'f"', '(', 'f"""', "f'''", '"""', "'''")):
                    start = j
                    break
        yield start, "\n".join(lines[start:n + 1])


class _LineIndex:
    """Map a character offset to a 1-based line number, without a per-call
    rescan — `src.count("\\n", 0, off)` over a 2,900-line file for each of
    several hundred matches is measurably slower than remembering the
    offsets once."""

    def __init__(self, src):
        self.src = src
        self.starts = [0]
        for i, ch in enumerate(src):
            if ch == "\n":
                self.starts.append(i + 1)

    def at(self, off):
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1


def scan(path, rel):
    """Yield (line_no, placeholder, reason, rel) for each unproven placeholder.

    Applies the `produces_html` gate itself, so a caller cannot bypass it by
    calling this on a module that never renders markup for a browser.
    """
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if not produces_html(path, src):
        return
    norm_file = rel.replace("\\", "/")
    seen = set()
    for line_no, text in site_windows(src):
        for m in PLACEHOLDER.finditer(text):
            ph = m.group(1).strip()
            reason = classify(ph, norm_file)
            if reason is None:
                continue
            if (line_no, ph) in seen:
                continue
            seen.add((line_no, ph))
            yield line_no, ph, reason, rel


def main():
    hits = []
    scanned = 0
    skipped = []
    total = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if not produces_html(path, src):
                skipped.append(rel)
                continue
            scanned += 1
            for _line_no, text in site_windows(src):
                total += len(PLACEHOLDER.findall(text))
            hits.extend(scan(path, rel))

    print("=" * 76)
    print(f"  Static XSS gate — {scanned} module(s) audited, {total} "
          f"placeholder(s) in HTML sites")
    print(f"  {len(skipped)} module(s) skipped (no markup for a browser), "
          f"{len(SAFE_NAMES)} audited allowlist entries")
    print("=" * 76)
    for line_no, ph, reason, rel in sorted(hits, key=lambda h: (h[3], h[0])):
        print(f"  [FAIL] {rel}:{line_no}  {{{ph}}}")
        print(f"         {reason}")
    print()
    if hits:
        print("  Fix: components.esc(value), or pass it to html_alert() /")
        print("  html_metric(), which escape by default. If it genuinely")
        print("  cannot hold user text, add a justified SAFE_NAMES entry —")
        print("  do not silence it by renaming the variable.")
    print("=" * 76)
    if hits:
        print(f"  {len(hits)} UNPROVEN PLACEHOLDER(S)")
    else:
        print("  EVERY PLACEHOLDER IS PROVABLY SAFE")
    print("=" * 76)
    print()
    print("  This reads names, not values. It is not a substitute for the")
    print("  runtime check: submit `<script>alert(1)</script>` as a comment,")
    print("  a lecturer name, a course name and a location, then view every")
    print("  page as both roles.")
    raise SystemExit(1 if hits else 0)


if __name__ == "__main__":
    main()
