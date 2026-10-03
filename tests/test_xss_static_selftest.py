"""Self-test for test_xss_static.py.

A static gate that reports "everything is safe" is worthless unless you have
watched it fail on a real hole. A broken version — one whose site detection
finds nothing, or whose allowlist accidentally matches everything — looks
*exactly* like a working version passing on a clean tree.

This builds a scratch package containing one real bug and several innocent
patterns, points the gate at it, and asserts the verdict for each. It also
runs a mutation check: it re-runs the gate with each general rule disabled in
turn and requires the result to get worse, which is what proves the rules are
load-bearing rather than decorative.

Run:  .venv\\Scripts\\python.exe tests\\test_xss_static_selftest.py
"""
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRATCH = tempfile.mkdtemp(prefix="futo_xsstest_")

# ── The cases ───────────────────────────────────────────────────────────
# Each is (filename, source, must_be_flagged, why)
CASES = [
    (
        "bug_loop_var.py",
        # The exact shape that was live in decision_insights.py: a loop
        # variable over context_data — the one free-text column in the
        # schema — interpolated into a render call with no esc().
        "for _, row in sub.iterrows():\n"
        "    ctx = parse_context(row.get('context_data'))\n"
        "    all_items.extend(ctx.get('challenges', []))\n"
        "\n"
        "tag_html = ''.join(\n"
        "    f'<span class=\"chip\">{t}</span>'\n"
        "    for t in all_items\n"
        ")\n"
        "st.markdown(\n"
        "    f'<div class=\"row\">{tag_html}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "loop variable over free text — the bug this gate exists for",
    ),
    (
        "bug_bare_comment.py",
        "st.markdown(\n"
        "    f'<div class=\"q\">{row[\"comment\"]}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "a raw DB string interpolated with no esc()",
    ),
    (
        "bug_attribute_only.py",
        "st.markdown(\n"
        "    f'<div title=\"{full_name}\">x</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "unescaped inside an attribute value, not element text",
    ),
    (
        "bug_multi_line.py",
        "st.markdown(\n"
        "    f'<div class=\"card\">'\n"
        "    f'<h3>{esc(heading)}</h3>'\n"
        "    f'<p>{body}</p>'\n"
        "    f'</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "one unescaped name inside a multi-line f-string block",
    ),
    (
        "ok_escaped.py",
        "st.markdown(\n"
        "    f'<div class=\"q\">{esc(row[\"comment\"])}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "escaped at the placeholder",
    ),
    (
        "ok_helper.py",
        # Mirrors user_management.py: the field is passed to _preview_row,
        # which escapes it. Note the variable is named `preview` because
        # that allowlist entry is name-specific — a deliberate coupling, and
        # worth being explicit about rather than hiding.
        "from components import esc\n"
        "\n"
        "def _preview_row(key, value):\n"
        "    return f'<div>{esc(key)}<span>{esc(value)}</span></div>'\n"
        "\n"
        "st.markdown(\n"
        "    '<div class=\"s\">'\n"
        "    + _preview_row('Account', f'{preview[\"username\"]}')\n"
        "    + '</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "built by a helper that escapes internally",
    ),
    (
        "bug_triple_quoted.py",
        "st.markdown(f\"\"\"\n"
        "<div class=\"card\">\n"
        "  <p>{lecturer_name}</p>\n"
        "</div>\"\"\", unsafe_allow_html=True)\n",
        True,
        "a triple-quoted f-string block",
    ),
    (
        "bug_render_tag.py",
        "from components import render_tag_list\n"
        "\n"
        "tags = render_tag_list(ctx.get('challenges'))\n"
        "st.markdown(\n"
        "    f'<div class=\"row\">{tags}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "render_tag_list escapes each element — SAFE_NAMES documents this",
    ),
    (
        "bug_nested_quote.py",
        "st.markdown(\n"
        "    f'<div>{esc(cfg[\"name\"])} · {cfg[\"label\"]}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "cfg is the module-level PRIORITY_CONFIG dict — SAFE_NAMES",
    ),
    (
        "ok_numeric.py",
        "st.markdown(\n"
        "    f'<div>{total} of {count} — {pct:.1f}% — "
        "{\"s\" if count != 1 else \"\"}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "numbers, a format spec, and a literal-only conditional",
    ),
    (
        "ok_calls.py",
        "from icons import i\n"
        "\n"
        "st.markdown(\n"
        "    f'<div>{i(\"star\", 12)}<span>{len(items)}</span></div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "in-repo SVG and len()",
    ),
    (
        "ok_unrelated.py",
        # An f-string with a '<' in it that never becomes markup.
        "body = f'<html><body>{name}</body></html>'\n"
        "send_email(to, body)\n",
        False,
        "an email body, not a browser",
    ),
    (
        "bug_allowlist_scope.py",
        # The exact flaw that the file-scoped allowlist exists to prevent:
        # `body` is escaped inside components.html_alert, and the first
        # version of SAFE_NAMES was one global list — so that justification
        # silenced a bare `{body}` here, in a page that escapes nothing.
        "st.markdown(\n"
        "    f'<div class=\"card\">'\n"
        "    f'<h3>{esc(heading)}</h3>'\n"
        "    f'<p>{body}</p>'\n"
        "    f'</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "a components.py-scoped entry must not apply to a page",
    ),
    (
        "bug_scoped_name_elsewhere.py",
        # The converse: `size` is only safe in icons.py, where it is
        # reassigned from _safe_attr() against a regex. Elsewhere it is just
        # a bare name with no guarantee attached.
        "st.markdown(\n"
        "    f'<div style=\"width:{size}px\">{label}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "an icons.py-scoped entry must not apply to a page",
    ),

    # ── One fixture per general rule ──────────────────────────────────────
    # The mutation check below can only prove a rule load-bearing if some
    # case exercises it. Its first run reported CONTAINS_ESCAPE,
    # ARITHMETIC_CHARS/OP, KEY_VALUE_LITERAL and GET_WITH_LITERAL_DEFAULT as
    # dead — which was true, of the fixtures, not of the rules. These four
    # cases give each rule something to be load-bearing *for*.
    (
        "ok_partial_escape.py",
        "st.markdown(\n"
        "    f'<div class=\"r\">{esc(prefix)} · "
        "{esc(detail) if detail else \"—\"}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "CONTAINS_ESCAPE: a conditional whose only free part is esc()'d",
    ),
    (
        "bug_partial_escape.py",
        "st.markdown(\n"
        "    f'<div class=\"r\">{prefix} · {detail if detail else \"—\"}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "the same shape with the esc() removed",
    ),
    (
        "ok_two_operators.py",
        "st.markdown(\n"
        "    f'<div class=\"p\">{total - positive - neutral} left</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "ARITHMETIC: two operators, no string literal anywhere",
    ),
    (
        "ok_kv_literal.py",
        "st.markdown(\n"
        "    f'<div class=\"c\">{layout | {\"displayModeBar\": False}}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "KEY_VALUE_LITERAL: a container built from literals",
    ),
    (
        "bug_kv_literal.py",
        "st.markdown(\n"
        "    f'<div class=\"c\">{layout | {\"displayModeBar\": mode}}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        True,
        "the same shape with a bare name as the value",
    ),
    (
        "ok_get_default.py",
        "st.markdown(\n"
        "    f'<div class=\"h\">{cfg.get(\"heading\", \"Key findings\")}</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "GET_WITH_LITERAL_DEFAULT: a literal default, but cfg itself is free",
    ),
    (
        "ok_fmt_spec.py",
        "st.markdown(\n"
        "    f'<div class=\"s\">score {result.score:+.3f} · {pct:.1f}%</div>',\n"
        "    unsafe_allow_html=True,\n"
        ")\n",
        False,
        "FMT_SPEC: format specifiers, so the value is a number",
    ),
]

# ── Load the gate without running its main() ────────────────────────────
import importlib.util

spec = importlib.util.spec_from_file_location("_xss_gate",
                                              HERE / "test_xss_static.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


# ── The module paths the allowlist is scoped to ─────────────────────────
# Scoped entries only apply where their justification holds, so a fixture
# that exercises one has to live at that path. Writing the fixture to a temp
# dir and calling it "ok_helper.py" is how a scoped rule looks like a
# false positive when it is really an inapplicable name.
PAGE = "app_pages/user_management.py"
HELPER_MODULE = "components.py"
ICONS_MODULE = "icons.py"


# Which module path each fixture is audited under. Fixtures that exercise a
# file-scoped allowlist entry MUST use the real path of the module that entry
# was justified in, because that scoping is the behaviour under test.
MODULE_OF = {
    "ok_helper.py": PAGE,            # _preview_row is user_management's
    "bug_render_tag.py": HELPER_MODULE,  # render_tag_list is components'
    "bug_nested_quote.py": "app_pages/decision_insights.py",  # PRIORITY_CONFIG
    "bug_allowlist_scope.py": PAGE,   # NOT components.py — that is the point
    "bug_scoped_name_elsewhere.py": PAGE,  # NOT icons.py — that is the point
}


def run_gate_on(path, rel=None):
    """Return the set of flagged placeholders for one file."""
    return {(ph, reason)
            for _ln, ph, reason, _r in gate.scan(path, (rel or path).replace("\\", "/"))}


def audit(fname, src):
    """Write a fixture and return what the gate says about it."""
    path = os.path.join(SCRATCH, fname)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)
    return run_gate_on(path, MODULE_OF.get(fname, fname))


def main():
    print("=" * 76)
    print("  test_xss_static.py self-test — does it detect the bug class it")
    print("  claims to, without false-flagging legal code?")
    print("=" * 76)
    print()

    ok = True
    try:
        for fname, src, must_flag, why in CASES:
            flagged = audit(fname, src)
            if must_flag:
                passed = len(flagged) > 0
                detail = f"flagged {sorted(p for p, _ in flagged)}"
            else:
                passed = not flagged
                detail = "clean" if passed else \
                    f"FALSE POSITIVE: {sorted(p for p, _ in flagged)}"
            print(f"  [{'PASS' if passed else 'FAIL'}] {fname:<22} {detail}")
            print(f"         ({why})")
            if not passed:
                ok = False
                print()
                print("".join(f"    {n+1:>4}| {ln}\n"
                              for n, ln in enumerate(src.split("\n"))))

        # ── Mutation check ────────────────────────────────────────────
        # Disable each general rule in turn and require the gate to get
        # WORSE. If a rule is decorative, removing it changes nothing and
        # the rule is dead weight pretending to be a safeguard.
        print()
        print("=" * 76)
        print("  Mutation check — is each general rule load-bearing?")
        print("=" * 76)
        MUTANTS = [
            ("CONTAINS_ESCAPE", r"\b(?:esc|html\.escape|_esc)\s*\("),
            ("SAFE_CALL", r"^\s*(quote|urlencode|i|icon|"
                          r"icon_badge|format|iif|_safe_attr|len|int|float|"
                          r"str|bool|abs|max|min|sum|round|sorted)\s*\("),
            ("ARITHMETIC_CHARS", r"^[\s\w\.\(\)\[\]\+\-\*/%<>=!:]+$"),
            ("ARITHMETIC_OP", r"[-+*/%<>=!]"),
            ("KEY_VALUE_LITERAL", r"^\s*[\"'][\w \-]+[\"']\s*:\s*"
                                   r"(?:True|False|None|\d+(?:\.\d+)?|"
                                   r"(?:\"[^\"]*\"|'[^']*'))\s*$"),
            ("FMT_SPEC", r"^[^{}]+:[^{}]*$"),
            ("LITERAL_ONLY", r"""^\s*["'].*["']\s*(if|else).*["']\s*$"""),
            ("GET_WITH_LITERAL_DEFAULT",
             r""".get\([^,]+,\s*["'][^"']*["']\s*\)$"""),
        ]
        # Baseline: every legal case clean, every buggy case flagged.
        baseline_bad = 0
        for fname, src, must_flag, _ in CASES:
            if bool(audit(fname, src)) != must_flag:
                baseline_bad += 1
        if baseline_bad:
            print(f"  [FAIL] baseline is wrong on {baseline_bad} case(s); "
                  f"the mutation check would be meaningless")
            ok = False
        else:
            print(f"  [PASS] baseline correct on all {len(CASES)} case(s)")

        for attr, pattern in MUTANTS:
            original = getattr(gate, attr)
            # Replace the rule with something that can never match.
            setattr(gate, attr, re.compile(r"(?!x)x"))
            became_worse = 0
            for fname, src, must_flag, _ in CASES:
                if bool(audit(fname, src)) != must_flag:
                    became_worse += 1
            setattr(gate, attr, original)
            if became_worse:
                print(f"  [PASS] {attr:<26} load-bearing "
                      f"({became_worse} case(s) change)")
            else:
                print(f"  [FAIL] {attr:<26} DEAD RULE — disabling it changes "
                      f"nothing")
                ok = False
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    print()
    print("=" * 76)
    print("  SELFTEST PASSED" if ok
          else "  SELFTEST FAILED — the gate is not trustworthy")
    print("=" * 76)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
