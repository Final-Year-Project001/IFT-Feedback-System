"""The category card's label must agree with the numbers printed beside it.

Scope — what this file is FOR:

Two cards contradicted themselves, and in opposite directions:

    Curriculum     avg 3.0   0.0% negative   ->  "Needs Urgent Action"
    Course Content avg 3.5  50.0% negative   ->  "Needs Attention"

The label came from the *mean* and the percentage from the *distribution*, so
the two were free to disagree. The first declared an emergency with no negative
responses behind it — and rating 3 is Neutral by the engine's own definition,
so "urgent action" was being claimed over a category nobody was unhappy with.
The second averaged one angry student together with one delighted one; 3.5
belongs to neither of them.

This pins the properties that fix it, using the cases from both screenshots:

  1. The label is a function of the negative share, not the mean.
  2. A category with no negative ratings is never "urgent", at any average.
  3. "Urgent" needs a real sample, unless every response is negative.
  4. `steady` exists, for no-negatives-but-no-praise.
  5. The distribution that produced the label is actually rendered, so a reader
     can check the claim rather than trust it.
  6. An average spanning opposed ratings is called out as meaningless rather
     than left to be read at face value.

Run: .venv\\Scripts\\python.exe tests\\test_decision_band.py
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


import sentiment  # noqa: E402
import app_pages.decision_insights as di  # noqa: E402

SRC = Path("app_pages/decision_insights.py").read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════
section("1. The label comes from the negative share, not the mean")
# ══════════════════════════════════════════════════════════════════════

check("the band function takes the negative share",
      "neg_pct" in di._band.__code__.co_varnames,
      di._band.__code__.co_varnames)

# The decisive pair: identical average, opposite verdict. If any average-based
# rule creeps back, these two collapse to the same answer and this fails.
same_avg_diff_band = [
    (0.0, 3.5), (50.0, 3.5), (100.0, 3.5),
]
# Two distinct bands, not three: 50% and 100% negative are both "urgent", and
# asserting they differed would be asserting a bug. The property that matters is
# that zero negatives is not one of them.
bands = {di._band(n, a, 8) for n, a in same_avg_diff_band}
check("the same average can now yield different bands",
      len(bands) > 1, bands)
zero_case = di._band(0.0, 3.5, 8)
others = {di._band(n, 3.5, 8) for n in (50.0, 100.0)}
check("...and it does: at avg 3.5, 0% negative is a different band from 50%/100%",
      zero_case not in others,
      {n: di._band(n, 3.5, 8) for n in (0.0, 50.0, 100.0)})

check("no average-only threshold remains in the band function",
      "_MIXED_AT" not in SRC,
      "_MIXED_AT still present — the old 3.3 mean cut is still in the file")

# ══════════════════════════════════════════════════════════════════════
section("2. Image 2: 0% negative can never be 'urgent'")
# ══════════════════════════════════════════════════════════════════════

# Every average from 1.0 to 3.2, at zero negatives. Under the old rule anything
# below 3.3 was "Needs Urgent Action" — including the 3.0 in the screenshot.
zero_neg = {avg: di._band(0.0, avg, 12) for avg in (1.0, 1.5, 2.0, 2.5, 3.0, 3.2)}
check("no average produces 'critical' when nothing is negative",
      "critical" not in zero_neg.values(), zero_neg)

check("a single rating of 3 is 'steady', not urgent",
      di._band(0.0, 3.0, 1) == "steady", di._band(0.0, 3.0, 1))

# The scale agrees: a rating of 3 is Neutral, so a category of them is neutral.
three_is_neutral = sentiment.label_from_rating(3) == "Neutral"
check("and that matches the engine: rating 3 is Neutral",
      three_is_neutral, sentiment.label_from_rating(3))

check("the Neutral label is worded as neutral, not as a problem",
      di.PRIORITY_CONFIG["steady"]["label"] == "Neutral",
      di.PRIORITY_CONFIG["steady"]["label"])
check("...with no alarming wording in its recommendation",
      not re.search(r"urgent|intervention|systemic|critical",
                    di.PRIORITY_CONFIG["steady"]["rec"], re.I),
      di.PRIORITY_CONFIG["steady"]["rec"])

# ══════════════════════════════════════════════════════════════════════
section("3. Image 3: 50% negative is surfaced, and the mean is not trusted")
# ══════════════════════════════════════════════════════════════════════

check("50% negative is at least 'warning'",
      di._band(50.0, 3.5, 2) in ("warning", "critical"), di._band(50.0, 3.5, 2))
check("...and is 'critical' once there is a real sample behind it",
      di._band(50.0, 3.5, 4) == "critical", di._band(50.0, 3.5, 4))
check("a category that is genuinely unhappy is never 'steady' or 'good'",
      all(di._band(50.0, 3.5, n) not in ("steady", "good") for n in (2, 4, 20)))

# ══════════════════════════════════════════════════════════════════════
section("4. 'Urgent' needs a sample, except when unanimous")
# ══════════════════════════════════════════════════════════════════════

check("one negative out of two is not a departmental emergency",
      di._band(50.0, 3.5, 2) != "critical", di._band(50.0, 3.5, 2))
check("...but every response negative is, even at n=2",
      di._band(100.0, 1.5, 2) == "critical", di._band(100.0, 1.5, 2))
check("...and at n=1, where one rating of 1 is the only evidence there is",
      di._band(100.0, 1.0, 1) == "critical", di._band(100.0, 1.0, 1))
check("...but one negative out of three is still only a warning",
      di._band(33.0, 2.5, 3) != "critical", di._band(33.0, 2.5, 3))

# The floor can only ever soften a verdict, never invent one.
monotone = all(
    di._band(50.0, 3.5, n) in ("warning", "critical")
    for n in range(1, 30)
)
check("the sample floor never invents a band the share would not allow",
      monotone)

# ══════════════════════════════════════════════════════════════════════
section("5. The band and the figure beside it come from one number")
# ══════════════════════════════════════════════════════════════════════

# Rendered card: the label, the percentage, and the three counts. If they are
# computed from different sources they can drift apart again.
check("the card renders the Positive count",
      "Positive <strong>" in SRC or 'Positive <strong>' in SRC)
check("the card renders the Neutral count",
      "Neutral <strong>" in SRC)
check("the card renders the Negative count",
      "Negative <strong>" in SRC)
check("...all three inside one split row",
      'class="insight-split"' in SRC)
check("...and the row has a CSS rule",
      ".insight-split" in Path("styles.py").read_text(encoding="utf-8"))

# The counts must be derived from the same frame as the percentage.
counts_block = SRC.split("items.append({")[0].rsplit("for cat in CATEGORIES:", 1)[-1]
check("pos/neu/neg are all computed in the same loop as neg_pct",
      all(k in counts_block for k in ("neg =", "pos =", "neu =", "neg_pct")))
check("...and neu is the remainder, so the three always sum to the total",
      "neu = int(len(sub) - neg - pos)" in SRC)

# `effective_sentiment`, not `rating`: an admin correction must be counted, or
# the label would disagree with the label column on every other page.
check("the counts read effective_sentiment, so corrections are included",
      'sentiments = sub["effective_sentiment"]' in SRC)
check("...and not the raw rating",
      'sentiments = sub["rating"]' not in SRC)

# ══════════════════════════════════════════════════════════════════════
section("6. An average spanning opposed ratings is called out")
# ══════════════════════════════════════════════════════════════════════

check("the card detects a split between negative and positive responses",
      "spread_note" in SRC and 'item["neg"] > 0' in SRC and 'item["pos"] > 0' in SRC)
check("...and it needs at least two responses to mean anything",
      re.search(r'item\["count"\]\s*>=\s*2', SRC) is not None)
check("...the note has a CSS rule",
      ".insight-split-note" in Path("styles.py").read_text(encoding="utf-8"))
check("...and it tells the reader to read the split, not the mean",
      "Read the split, not the mean" in SRC)

# ══════════════════════════════════════════════════════════════════════
section("7. The system-wide verdict uses the same thresholds")
# ══════════════════════════════════════════════════════════════════════

check("the header no longer calls a session 'Good' on the average alone",
      re.search(r'health = .*_NEG_CRITICAL_PCT', SRC, re.S) is not None
      or "neg_pct_total" in SRC.split("health =")[1].split("\n\n")[0])
check("every band named in _band has a PRIORITY_CONFIG entry",
      set(("critical", "warning", "steady", "good")) == set(di.PRIORITY_CONFIG),
      sorted(di.PRIORITY_CONFIG))
check("every band has playbook steps",
      set(di.PRIORITY_CONFIG) <= set(di._PLAYBOOK),
      sorted(set(di.PRIORITY_CONFIG) - set(di._PLAYBOOK)))

# ══════════════════════════════════════════════════════════════════════
section("8. The icons the new bands ask for actually exist")
# ══════════════════════════════════════════════════════════════════════

import icons  # noqa: E402

wanted = set()
for cfg in di.PRIORITY_CONFIG.values():
    wanted.add(cfg["label_icon"])
wanted |= set(re.findall(r'i\("([a-z-]+)"', SRC))
missing = sorted(w for w in wanted if w not in icons.ICN)
check("every icon named on this page is registered", not missing, missing)

# ══════════════════════════════════════════════════════════════════════
section("9. Chart captions are gone")
# ══════════════════════════════════════════════════════════════════════

# Matched on the signature, not the word: `chart_card`'s docstring explains
# why the caption parameter was removed, so a substring search finds the word
# it is documenting away.
card_src = Path("app_pages/targets.py").read_text(encoding="utf-8")
signature = re.search(r"def chart_card\(([^)]*)\)", card_src).group(1)
check("chart_card no longer takes a caption parameter",
      "caption" not in signature, signature.strip())
check("...and it still takes the arguments the call sites pass",
      all(a in signature for a in ("title", "icon", "figure")), signature.strip())
check("...so no call site can pass one",
      not any("caption=" in p.read_text(encoding="utf-8")
              for p in Path("app_pages").glob("*.py")))
check("the caption CSS is removed too",
      "chart-card-caption" not in Path("styles.py").read_text(encoding="utf-8"))

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