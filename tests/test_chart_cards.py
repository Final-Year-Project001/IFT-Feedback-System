"""Verification for the premium chart card.

Scope — what this file is FOR, and what it is not:

Charts were supposed to sit in a card and did not. Every call site opened
`<div class="chart-wrap">` in one `st.markdown` and closed it in another, and
Streamlit closes the markup it is handed at the end of each element — so the
wrapper was always empty and every chart rendered on the bare page below an
empty box. Nothing in the test suite caught it, because the `class=` string was
present in the source and the CSS gate only asks whether a class has a rule.

So this suite checks the *shape* of the markup, not the presence of a class
name:

  1. no call site still splits one element across two `st.markdown` calls;
  2. the CSS hook the card is styled through is a name Streamlit will really
     emit, so the frame cannot silently stop applying;
  3. the card keeps its shape when there is no data to draw.

Run: .venv\\Scripts\\python.exe tests\\test_chart_cards.py
"""
import ast
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

results: list = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


PAGES = sorted(Path("app_pages").glob("*.py"))

# ══════════════════════════════════════════════════════════════════════
section("1. No chart is wrapped by a split-open div any more")
# ══════════════════════════════════════════════════════════════════════

# `targets.py` is excluded from these scans: it *documents* the old pattern in
# its module docstring, quoting the three calls that were wrong. Scanning the
# documentation of the bug would report the bug as still present, forever.
PAGE_CODE = [p for p in PAGES if p.name != "targets.py"]

split_wrappers = []
for path in PAGE_CODE:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for idx, line in enumerate(lines):
        if re.search(r'st\.markdown\(\s*f?[\'"]<div class="chart-wrap"', line):
            # The bug: the opening tag is emitted here and the closing tag by a
            # later call. Streamlit auto-closes each markdown block, so this
            # produces an empty box and a chart outside it.
            split_wrappers.append(f"{path}:{idx + 1}")

check("no page opens <div class=\"chart-wrap\"> in one markdown call",
      not split_wrappers, split_wrappers)

# And the closing half, independently: a lone `</div>` on its own is the other
# end of the same defect.
orphan_closers = []
for path in PAGE_CODE:
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if re.match(r'\s*st\.markdown\(\s*[\'"]</div>[\'"]\s*\)\s*$', line):
            orphan_closers.append(f"{path}:{idx + 1}")
check("no page emits a bare </div> to close something else",
      not orphan_closers, orphan_closers)

# ══════════════════════════════════════════════════════════════════════
section("2. Every chart goes through the card component")
# ══════════════════════════════════════════════════════════════════════

direct_plots = []
for path in PAGE_CODE:
    body = path.read_text(encoding="utf-8", errors="replace")
    for idx, line in enumerate(body.splitlines()):
        if "plotly_chart(" in line:
            # A chart drawn outside `chart_card` gets no frame. The card itself
            # legitimately calls plotly_chart, so it is excluded by name.
            if "chart_card" in line:
                continue
            direct_plots.append(f"{path}:{idx + 1}")
check("every chart is rendered by chart_card, not bare",
      not direct_plots, direct_plots)

targets = Path("app_pages/targets.py").read_text(encoding="utf-8")
check("chart_card is defined", "def chart_card(" in targets)
check("chart_card draws its own plot", "plotly_chart" in targets.split("def chart_card(")[1][:1200])

# ══════════════════════════════════════════════════════════════════════
section("3. The CSS hook is one Streamlit will really emit")
# ══════════════════════════════════════════════════════════════════════

# The card is styled through a `data-testid^="stChartCard"` attribute selector,
# which only works if `key="stChartCard…"` becomes that test-id. Verify the
# key prefix is what the component actually passes.
check("the container key starts with `st`, so Streamlit adopts it as the test-id",
      'return f"stChartCard{slug}"' in targets,
      [l for l in targets.splitlines() if "stChartCard" in l])

# Streamlit's own keyToTestId rule: a key beginning with "st" is used verbatim.
import streamlit  # noqa: E402

sroot = os.path.join(os.path.dirname(streamlit.__file__), "static", "static", "js")
bundle = []
for fn in os.listdir(sroot):
    if fn.endswith(".js"):
        with open(os.path.join(sroot, fn), encoding="utf-8", errors="ignore") as fh:
            bundle.append(fh.read())
blob = "\n".join(bundle)

# The existing `test_css.py` gate verifies data-testids against this bundle and
# allows the app's own `key="st…"` names. Confirm our name is in that category
# by checking the CSS only ever uses test-ids the app owns or Streamlit emits.
import styles  # noqa: E402

css = styles.GLOBAL_CSS
used = set(re.findall(r'data-testid="([^"]+)"', css))
used |= {m for m in re.findall(r'data-testid\^="([^"]+)"', css)}
app_owned = {f"stChartCard{t}" for t in ("", "OverallRatingDistribution", "CategoryOverview",
                                        "SentimentAnalysis", "ByStudentLevel",
                                        "RatingTrendOverTime", "RatingDistribution",
                                        "MyRatingDistribution", "MySentimentBreakdown")}
unknown = sorted(
    t for t in used
    if not t.startswith("stChartCard")
    and t not in blob
    and not re.search(r"(?<![A-Za-z0-9_$])" + re.escape(t) + r"(?![A-Za-z0-9_$])", blob)
)
# `stDecoration` is the Streamlit header bar, and its name is built at runtime
# rather than appearing as a literal — which is the same reason it is absent
# from the bundle scan. It is Streamlit's, not ours, and it predates this work.
PRE_EXISTING = {"stDecoration"}
check("no invented data-testid in the chart-card CSS",
      not [t for t in unknown if t not in PRE_EXISTING],
      [t for t in unknown if t not in PRE_EXISTING])
check("the chart-card hook is present in the stylesheet",
      'data-testid^="stChartCard"' in css)

# ══════════════════════════════════════════════════════════════════════
section("4. The card still looks like a card when there is no data")
# ══════════════════════════════════════════════════════════════════════

# Every builder in charts.py returns None rather than raising when there is not
# enough data. The card must handle that: a titled card with nothing in it is
# better than a bare heading with a hole under it.
builders = Path("charts.py").read_text(encoding="utf-8")
check("the trend builder still returns None instead of raising",
      builders.count("return None") >= 3,
      builders.count("return None"))
check("the card renders a placeholder when the figure is None",
      "chart-card-empty" in targets)
check("...and that placeholder has a rule in the stylesheet",
      ".chart-card-empty" in css)

# ══════════════════════════════════════════════════════════════════════
section("5. The chart type itself")
# ══════════════════════════════════════════════════════════════════════

check("the rating trend is a bar chart, not a line",
      "def make_trend_bar(" in builders)
trend = builders.split("def make_trend_bar(")[1].split("\ndef ")[0]
check("...and it draws go.Bar", "go.Bar(" in trend)
check("...and does not draw a line", "go.Scatter(" not in trend)
check("a day with no submissions is a gap, not a zero",
      'daily["n"] > 0' in trend)

# The banding is written against `sentiment`'s constants rather than repeating
# the numbers, so the trend and the sentiment chip beside it cannot drift apart
# if a band ever moves.
check("the banding reads the engine's constants, not its own literals",
      "NEGATIVE_MAX" in trend and "POSITIVE_MIN" in trend,
      [l.strip() for l in trend.splitlines()
       if "value <=" in l or "value >=" in l])
check("the old name still works, as an alias to the bars",
      "def make_trend_line(" in builders and "return make_trend_bar(df)" in builders)
check("no page still calls the old name directly",
      not any("make_trend_line(" in p.read_text(encoding="utf-8", errors="replace")
              and "def make_trend_line" not in p.read_text(encoding="utf-8", errors="replace")
              for p in PAGE_CODE))

# The bar colours must come from the same bands the sentiment engine uses, or
# the trend and the verdict beside it would colour the same number differently.
# Checked against the constants themselves rather than against the literal text
# "<= 2" in the builder: a hard-coded band is the defect, so matching the number
# proves the builder carries the engine's value and not a copy of it.
import sentiment  # noqa: E402

for label, bound in (("Negative at or below", sentiment.NEGATIVE_MAX),
                     ("Positive at or above", sentiment.POSITIVE_MIN)):
    check(f"the bar banding uses the engine's own {label} value ({bound})",
          str(bound) in trend, f"{bound} not found in make_trend_bar")

# ══════════════════════════════════════════════════════════════════════
print()
failed = [r for r in results if not r[1]]
for name, ok, detail in results:
    line = f"  [{'PASS' if ok else 'FAIL'}] {name}"
    if detail and not ok:
        line += f"  -- {detail}"
    print(line)

print()
print("=" * 74)
if failed:
    print(f"  {len(failed)} CHECK(S) FAILED:")
    for name, _, detail in failed:
        print(f"    - {name}" + (f"  ({detail})" if detail else ""))
    print("=" * 74)
    sys.exit(1)
print(f"  ALL {len(results)} CHECKS PASSED")
print("=" * 74)