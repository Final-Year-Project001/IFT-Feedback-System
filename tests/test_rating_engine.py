"""Verification for the rating-driven sentiment engine.

Scope — what this file is FOR:

The engine was rewritten because it disagreed with the rating the student had
given: a 4/5 submission displayed next to a "Negative" sentiment chip. Two
things have to hold for that to stay fixed, and neither is visible from reading
the code alone:

  1. **The rating decides.** One rule, in one function, applied everywhere —
     the form, `db.save_data`, and the read path in `db.load_data` that covers
     rows written before the rule existed.
  2. **There is nothing left to disagree.** VADER and the NLTK dependency are
     gone, and the free-text comment box is gone with them, so there is no
     second opinion for a reader to find contradicting the first.

These checks are cheap, so they run first in `run_all.py`: if the rating rule
ever breaks, everything downstream is measuring the wrong thing.

Run: .venv\\Scripts\\python.exe tests\\test_rating_engine.py
"""
import ast
import inspect
import io
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import sentiment  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok, detail: str = "") -> None:
    results.append((name, bool(ok), str(detail)))


def section(title: str) -> None:
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


# ══════════════════════════════════════════════════════════════════════
section("1. The rating -> band rule")
# ══════════════════════════════════════════════════════════════════════

EXPECTED = {1: "Negative", 2: "Negative", 3: "Neutral", 4: "Positive", 5: "Positive"}
for rating, want in EXPECTED.items():
    got = sentiment.label_from_rating(rating)
    check(f"rating {rating} -> {want}", got == want, f"got {got!r}")

# The whole point of the change: no rating may produce a band that a reader
# would call wrong. The bands are exactly the ones the UI's own captions state.
check(
    "the three bands named in the UI are the only three the engine emits",
    set(sentiment.RATING_LABELS) == set(range(1, 6))
    and {sentiment.label_from_rating(r) for r in EXPECTED}
    == {"Negative", "Neutral", "Positive"},
    sorted({sentiment.label_from_rating(r) for r in EXPECTED}),
)

# ══════════════════════════════════════════════════════════════════════
section("2. The rule cannot be contradicted by a second input")
# ══════════════════════════════════════════════════════════════════════

# `analyze_sentiment` keeps `text` as its first parameter for call-site
# compatibility, but the argument must be inert. Feeding it the most strongly
# negative sentence possible must not move a 5-star rating off "Positive".
HOSTILE_TEXTS = [
    "terrible, useless, the worst lecturer in this department, waste of time",
    "horrible broken broken broken nothing works ever, appalling",
    "!!! DISASTER !!! everything failed, catastrophic, rubbish",
]
for rating in (5, 4, 1):
    for text in HOSTILE_TEXTS:
        got = sentiment.analyze_sentiment(text, rating=rating).label
        check(
            f"rating {rating} survives {text[:32]!r}",
            got == sentiment.label_from_rating(rating),
            f"got {got!r}",
        )

# And the signature itself: `text` must be optional and must not be required
# by any caller. A default of None is what makes "the comment cannot change
# the answer" true rather than merely observed.
sig = inspect.signature(sentiment.analyze_sentiment)
check(
    "analyze_sentiment(text, rating) — both optional",
    all(p.default is not inspect.Parameter.empty for p in sig.parameters.values()),
    list(sig.parameters),
)

# ══════════════════════════════════════════════════════════════════════
section("3. Nothing external can fail to load")
# ══════════════════════════════════════════════════════════════════════

def _active_requirements() -> list[str]:
    """Only the lines pip would install — comments are ignored on purpose.

    The removal note left in `requirements.txt` names NLTK and VADER in prose.
    Checking the raw text therefore reports the explanatory comment as though it
    were still a dependency, which is exactly the false positive that would make
    this check worthless.
    """
    lines = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines
            if l.strip() and not l.strip().startswith("#")]


src = Path("sentiment.py").read_text(encoding="utf-8")

# VADER and the NLTK dependency, gone from the module.
# The module docstring deliberately explains what was removed and why, so it
# names VADER in prose. What must not survive is *code* that calls it.
check("no SentimentIntensityAnalyzer anywhere in sentiment.py",
      "SentimentIntensityAnalyzer" not in src)
check("no `import nltk` in sentiment.py",
      not any(line.strip().startswith(("import nltk", "from nltk"))
              for line in src.splitlines()))

# The module must import nothing outside the standard library. `config` is a
# sibling module of this project, not a package, and is no longer imported.
imports = []
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports += [a.name.split(".")[0] for a in node.names]
    elif isinstance(node, ast.ImportFrom) and node.module:
        imports.append(node.module.split(".")[0])
STDLIB_OK = {"__future__", "typing", "re", "json", "math", "os", "string",
             "collections", "pickle", "dataclasses", "itertools"}
third_party = sorted({m for m in imports if m not in STDLIB_OK})
check("sentiment.py imports only the standard library", not third_party, third_party)

# requirements must not still be installing what we removed.
installed = _active_requirements()
check("nltk is no longer installed", not any(l.lower().startswith("nltk") for l in installed),
      [l for l in installed if "nltk" in l.lower()])
check("scikit-learn is no longer installed",
      not any("scikit-learn" in l.lower() or l.lower().startswith("sklearn")
              for l in installed),
      [l for l in installed if "scikit" in l.lower() or l.lower().startswith("sklearn")])
check("vader is not fetched by any install step",
      not any("vader" in l.lower() for l in installed),
      [l for l in installed if "vader" in l.lower()])

# The downloader existed only to fetch the VADER corpus.
check("download_nltk_data.py is gone",
      not Path("download_nltk_data.py").exists())

# ══════════════════════════════════════════════════════════════════════
section("4. The trainer is gone, and nothing still calls it")
# ══════════════════════════════════════════════════════════════════════

check("train_model.py is gone", not Path("train_model.py").exists())

# A dangling import would only surface when somebody pressed the button that
# no longer exists, which is the worst time to find out.
dangling = []
for path in sorted(Path(".").glob("*.py")) + sorted(Path("app_pages").glob("*.py")):
    body = path.read_text(encoding="utf-8", errors="replace")
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import train_model", "from train_model")):
            dangling.append(f"{path}: {stripped}")
check("no module imports train_model", not dangling, dangling)

# With the comment box gone there is nothing to train a text classifier on.
check(
    "no feedback form still offers a free-text comment box",
    not any(
        "ta_" in line and "text_area" in line
        for path in sorted(Path("app_pages").glob("*.py"))
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
    ),
    "a text_area survived in a feedback form",
)

# ══════════════════════════════════════════════════════════════════════
section("5. The stored value and the read path agree")
# ══════════════════════════════════════════════════════════════════════

db_src = Path("db.py").read_text(encoding="utf-8")

# `save_data` must derive the label, not accept one from the page. If the caller
# could pass a label, there would be a second opinion again.
save_body = db_src.split("def save_data", 1)[1].split("\ndef ", 1)[0]
check("save_data derives the sentiment from the rating itself",
      "label_from_rating" in save_body and
      "d.get(\"sentiment\"" not in save_body,
      "save_data still takes a caller-supplied label")

# Historical rows were written by the old engine and can contradict their own
# rating. `load_data` re-applies the rule at read time.
load_body = db_src.split("def load_data", 1)[1].split("\ndef ", 1)[0]
check("load_data re-derives sentiment from the rating for stored rows",
      "label_from_rating" in load_body and "effective_sentiment" in load_body)
check("load_data preserves the old engine's verdict instead of discarding it",
      "text_sentiment" in load_body,
      "the pre-existing sentiment is overwritten with nothing kept")

# An administrator's correction must still win, or the one deliberate override
# in the system is silently ignored.
check("an admin correction still overrides the rating band",
      "admin_corrected_sentiment" in load_body and
      "effective_sentiment" in load_body)

# ══════════════════════════════════════════════════════════════════════
section("6. Nothing broke at the edges")
# ══════════════════════════════════════════════════════════════════════

check("an unusable rating falls back to Neutral, not a confident guess",
      sentiment.analyze_sentiment(rating=None).label == "Neutral" and
      sentiment.analyze_sentiment(rating="nonsense").label == "Neutral")
check("a legacy row's stored score still yields a valid confidence band",
      sentiment.estimate_confidence_from_score(0.8) >= sentiment.CONFIDENCE_FLOOR)
check("normalize_rating clamps out-of-range input",
      sentiment.normalize_rating(0) == 1 and sentiment.normalize_rating(9) == 5)
check("engine_status reports no problems and names the new engine",
      sentiment.engine_status()["engine_problems"] == [] and
      "rating" in sentiment.engine_status()["engine_name"])
check("the 3-tuple unpacking call sites rely on still works",
      (lambda r: (r[0], r[1], r[2]))(sentiment.analyze_sentiment(rating=4))
      == ("Positive", 0.5, sentiment.ENGINE_NAME))

# The five-band label ladder each page rendered from its own literal.
check("rating_label names all five bands",
      [sentiment.rating_label(n) for n in range(1, 6)]
      == ["Poor", "Fair", "Good", "Very Good", "Excellent"])

section("7. The stored name stays put; the screen name has no underscores")
# ══════════════════════════════════════════════════════════════════════

# `ENGINE_NAME` is a storage contract — rows on disk carry it — so the card
# shows a mapped display name instead of a renamed constant. Both halves are
# pinned: the constant must not drift (history would split), and the display
# must not contain underscores.
check("the stored engine name is unchanged",
      sentiment.ENGINE_NAME == "rating_threshold_engine", sentiment.ENGINE_NAME)
check("the display name has no underscores",
      "_" not in sentiment.ENGINE_DISPLAY_NAME
      and sentiment.ENGINE_DISPLAY_NAME == "rating threshold engine",
      sentiment.ENGINE_DISPLAY_NAME)
check("display_engine_name maps the stored constant",
      sentiment.display_engine_name(sentiment.ENGINE_NAME)
      == sentiment.ENGINE_DISPLAY_NAME)
check("...and degrades anything else instead of printing it raw",
      sentiment.display_engine_name(None) == sentiment.ENGINE_DISPLAY_NAME
      and sentiment.display_engine_name("") == sentiment.ENGINE_DISPLAY_NAME
      and "_" not in sentiment.display_engine_name("some_future_engine"))
check("the dashboard renders the display name, not the constant",
      "display_engine_name(" in Path("app_pages/full_dashboard.py").read_text(encoding="utf-8"))


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