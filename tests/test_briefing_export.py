"""Verification for the Executive Briefing export (PDF first, Markdown fallback).

Scope — what this file is FOR:

The Decision Insights page offers a board briefing download. It must be a
real PDF (that is what a board prints), byte-valid, with every dynamic value
escaped — admin directives and course names are free text, and an unescaped
`&` or `<` in either corrupts a reportlab paragraph or smuggles markup into
a file the board will open. And when reportlab is absent (a stale install),
the button must still deliver the Markdown instead of dying.

These are pure-function checks over `_build_briefing_md` /
`_build_briefing_pdf` / `_briefing_rows`, so they run in seconds with no
AppTest harness: hostile strings (`<b>`, `&`, quotes) go in, and the PDF is
re-parsed to prove they arrive as visible text.

Run: .venv\\Scripts\\python.exe tests\\test_briefing_export.py
"""
import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), str(detail)))


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


from app_pages.decision_insights import (  # noqa: E402
    _briefing_rows,
    _build_briefing_md,
    _build_briefing_pdf,
)

ITEMS = [
    {"cat": "Course Content", "priority": "warning", "avg": 3.2, "count": 5,
     "students": 4, "levels": 2, "pos": 1, "neu": 2, "neg": 2, "neg_pct": 40.0,
     "top_items": ["More <labs> & \"practicals\""]},
    {"cat": "Facilities", "priority": "good", "avg": 4.6, "count": 3,
     "students": 3, "levels": 1, "pos": 3, "neu": 0, "neg": 0, "neg_pct": 0.0,
     "top_items": []},
]
NOTES = {"Course Content": {"note": "Buy <b>projectors</b> & fix wiring",
                            "updated_by": "admin001",
                            "updated_at": "2026-01-01 10:00:00"}}

KW = dict(session_label="2025/2026", generated_on="2026-01-01 00:00:00",
          health="Good", avg_all=3.8, total=8, neg_pct_total=25.0,
          items=ITEMS, notes=NOTES)

section("1. The two exporters agree with each other")

md = _build_briefing_md(**KW)
check("the Markdown builds", isinstance(md, str) and len(md) > 200, len(md))
check("...carrying the headline numbers",
      "3.8 / 5.0" in md and "25.0%" in md and "2025/2026" in md)
check("...both categories with directives",
      "Course Content" in md and "Facilities" in md
      and "No action directive recorded." in md)

pdf = _build_briefing_pdf(**KW)
check("reportlab is installed in this environment",
      pdf is not None, "pip install -r requirements.txt")
if pdf is not None:
    check("the PDF is real PDF bytes", pdf[:8] == b"%PDF-1.4", pdf[:8])
    check("...of substance, not an empty shell", len(pdf) > 1500, len(pdf))

    from pypdf import PdfReader  # noqa: E402

    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
    check("the PDF holds the same headline numbers as the Markdown",
          "2025/2026" in text and "3.8" in text and "25.0%" in text)
    check("...both categories", "Course Content" in text and "Facilities" in text)
    check("hostile markup arrives as visible text, not formatting",
          "<b>projectors</b>" in text and "More <labs>" in text, text[:200])
    check("...and the ampersand survives too", "A & B" in text or "& fix wiring" in text)

section("2. Degenerate inputs degrade, never raise")

empty_md = _build_briefing_md(**{**KW, "items": [], "notes": {}})
check("empty categories still produce a document", len(empty_md) > 100)
empty_pdf = _build_briefing_pdf(**{**KW, "items": [], "notes": {}})
check("...in PDF too", empty_pdf is not None and empty_pdf[:5] == b"%PDF-")
rows = _briefing_rows([{"cat": "X"}], {})
check("a ragged item row fills safe defaults, never KeyErrors", rows and rows[0]["cat"] == "X",
      rows[0] if rows else None)
rows2 = _briefing_rows(None, None)
check("None in gives empty out", rows2 == [], rows2)

section("3. The page offers the PDF it promises")

src = Path("app_pages/decision_insights.py").read_text(encoding="utf-8")
check("the download button labels the PDF format",
      "Download Executive Briefing (.pdf)" in src)
check("...with the PDF mime and filename to match",
      '"application/pdf"' in src and "_Briefing_" in src and src.count(".pdf") >= 2)
check("the Markdown survives as the no-reportlab fallback",
      "_build_briefing_md(" in src and "text/markdown" in src)

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
    raise SystemExit(1)
print(f"  ALL {len(results)} CHECKS PASSED")
print("=" * 74)
