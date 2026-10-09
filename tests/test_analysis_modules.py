"""Verification for the per-lecturer, per-course and per-facility rollups.

Scope — what this file is FOR:

The administrative breakdowns behind three requirements:

  * Lecturer Teaching Style — every lecturer, with the challenges flagged
    against them, aggregated across all levels (one person can be rated by
    200-level and 400-level students, and must be shown as one row).
  * Course Content — the top courses per level, and the emphasis areas
    requested for each.
  * Facilities — the top infrastructure items across all levels.

The aggregation lives in `db.py` so the numbers on screen and the numbers in a
CSV export come from one implementation. What is easy to get wrong, and what
these checks pin, is:

  * grouping by level for courses (a 200-level course is a different question
    from a 500-level one), and *not* grouping by level for lecturers or
    facilities (both are genuinely department-wide);
  * a lecturer's rows being counted once even though several students rated
    them, so the "responses" figure is students, not checkboxes;
  * the two EzEs staying apart, which is what `lecturer_group_key` exists for.

Run: .venv\\Scripts\\python.exe tests\\test_analysis_modules.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_analysis_")
COPY = snapshot_live_db(TMP)

import db  # noqa: E402
import sentiment  # noqa: E402
from config import lecturer_group_key, lecturer_display_for, TEACHING_STAFF  # noqa: E402

db.DB_PATH = COPY

results: list[tuple[str, bool, str]] = []


def check(name, ok, detail="") -> None:
    results.append((name, bool(ok), str(detail)))


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


SESS = "ZZ_ANALYSIS_SESSION"

# Which category each block of fixtures belongs to. The rollups are per-category,
# so the fixture rows state their category once instead of on every row.
_CATEGORIES = {
    "otuonye": "Lecturer Teaching Style",
    "ezes": "Lecturer Teaching Style",
    "edge": "Lecturer Teaching Style",
    "courses": "Course Content",
    "facilities": "Facilities",
}
_CURRENT_CATEGORY = "Lecturer Teaching Style"


def using(category: str):
    """Sets the category for the fixtures that follow, until changed."""
    global _CURRENT_CATEGORY
    _CURRENT_CATEGORY = category


def seed(rows):
    """Insert feedback rows directly into the isolated test database copy.

    Sentiment is derived from the rating exactly the way `save_data` does it,
    rather than being written in. A fixture that hard-coded its own label would
    pass even if the rating rule were broken, which is the one thing this file
    exists to catch.
    """
    conn = db.get_db()
    for r in rows:
        rating = sentiment.normalize_rating(r.get("rating", 3))
        conn.execute(
            """INSERT INTO feedback
               (username, category, student_level, rating, comment, timestamp,
                additional_info, sentiment, sentiment_score, sentiment_engine,
                sentiment_confidence, sentiment_cues, context_data, session)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.get("username", "ZZseed"),
                _CURRENT_CATEGORY,
                r.get("level", "200"),
                rating,
                "",
                r.get("ts", "2026-10-09 09:00:00"),
                "",
                sentiment.label_from_rating(rating) or "Neutral",
                sentiment.rating_to_score(rating),
                sentiment.ENGINE_NAME,
                sentiment.rating_confidence(rating),
                "{}",
                db.json.dumps(r.get("ctx", {})),
                SESS,
            ),
        )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════
section("1. Lecturers — across every level, one row per person")
# ══════════════════════════════════════════════════════════════════════

seed([
    # Dr. Otuonye rated by three students at two different levels
    {"username": "ZZa", "level": "200", "rating": 2,
     "ctx": {"lecturer_name": "Dr. A. I. Otuonye",
             "challenges": ["Pace of lecture delivery (too fast / slow)"],
             "effective_methods": ["Use of infographics & visual aids"]}},
    {"username": "ZZb", "level": "200", "rating": 1,
     "ctx": {"lecturer_name": "Dr. A. I. Otuonye",
             "challenges": ["Pace of lecture delivery (too fast / slow)"],
             "effective_methods": []}},
    {"username": "ZZc", "level": "400", "rating": 3,
     "ctx": {"lecturer_name": "Otuonye",
             "challenges": ["Unclear explanations of complex topics"],
             "effective_methods": []}},
    # Dr. Okonkwo, clean
    {"username": "ZZd", "level": "300", "rating": 5,
     "ctx": {"lecturer_name": "Dr. O. T. Okonkwo", "challenges": [],
             "effective_methods": ["Quiz-based & gamified assessments"]}},
    # A hand-typed name that is not on the handbook list
    {"username": "ZZe", "level": "100", "rating": 4,
     "ctx": {"lecturer_name": "Dr. Smith (visiting)",
             "challenges": ["Poor slide/visual quality"], "effective_methods": []}},
])

lect = db.lecturer_summary(session=SESS)

by_key = {row["key"]: row for row in lect}
check("a lecturer rated at two levels is one row, not two",
      len([r for r in lect if r["key"].endswith("otuonye")]) == 1,
      [r["key"] for r in lect])
otu = by_key.get("otuonye")
check("their three student responses are counted once each",
      otu and otu["responses"] == 3, otu and otu["responses"])
check("their average rating is across all levels",
      otu and abs(otu["avg_rating"] - 2.0) < 0.01, otu and otu["avg_rating"])
check("their top challenge is the one two students flagged",
      otu and otu["top_challenges"]
      and otu["top_challenges"][0][0] == "Pace of lecture delivery (too fast / slow)",
      otu and otu["top_challenges"])
check("the second challenge is ranked below it",
      otu and len(otu["top_challenges"]) == 2
      and otu["top_challenges"][1][0] == "Unclear explanations of complex topics",
      otu and otu["top_challenges"])
check("Otuonye appears before Okonkwo (worst average first)",
      [r["key"] for r in lect].index("otuonye") < [r["key"] for r in lect].index("okonkwo"))
check("a hand-typed name is kept, labelled, and flagged as unknown",
      by_key.get("smith", {}).get("known") is False,
      by_key.get("smith"))
check("every lecturer row carries a display name for the dashboard",
      all(r.get("display") for r in lect), [r.get("key") for r in lect])

# Levels are recorded per lecturer, but only to show the spread.
check("a lecturer's levels are listed so an admin can see the spread",
      otu and set(otu["levels"]) == {"200", "400"}, otu and otu.get("levels"))

# ══════════════════════════════════════════════════════════════════════
section("2. The two EzEs must not be merged")
# ══════════════════════════════════════════════════════════════════════

check("the handbook really does list two EzEs",
      sum(1 for s in TEACHING_STAFF if s["key"] == "eze") == 2)
check("their full names produce different keys",
      lecturer_group_key("Prof. Mrs. U. F. Eze")
      != lecturer_group_key("Engr. Dr. (Mrs.) G. N. Eze"),
      (lecturer_group_key("Prof. Mrs. U. F. Eze"),
       lecturer_group_key("Engr. Dr. (Mrs.) G. N. Eze")))
check("a bare 'Eze' gets its own ambiguous key rather than being merged",
      lecturer_group_key("Eze") not in (
          lecturer_group_key("Prof. Mrs. U. F. Eze"),
          lecturer_group_key("Engr. Dr. (Mrs.) G. N. Eze")),
      lecturer_group_key("Eze"))
check("and it renders as un-identified rather than as one of them",
      "not identified" in lecturer_display_for(lecturer_group_key("Eze")).lower(),
      lecturer_display_for(lecturer_group_key("Eze")))

using(_CATEGORIES["ezes"])
seed([
    {"username": "ZZf", "level": "200", "rating": 5,
     "ctx": {"lecturer_name": "Prof. Mrs. U. F. Eze", "challenges": [], "effective_methods": []}},
    {"username": "ZZg", "level": "200", "rating": 1,
     "ctx": {"lecturer_name": "Engr. Dr. (Mrs.) G. N. Eze",
             "challenges": ["No issues – delivery is effective"], "effective_methods": []}},
])
lect2 = {r["key"]: r for r in db.lecturer_summary(session=SESS)}
e1 = lecturer_group_key("Prof. Mrs. U. F. Eze")
e2 = lecturer_group_key("Engr. Dr. (Mrs.) G. N. Eze")
check("the two EzEs appear as separate rows",
      e1 in lect2 and e2 in lect2 and e1 != e2, sorted(k for k in lect2 if k.startswith("eze")))
check("the praised Eze averages 5 and the flagged one 1",
      abs(lect2[e1]["avg_rating"] - 5.0) < 0.01 and abs(lect2[e2]["avg_rating"] - 1.0) < 0.01,
      (lect2.get(e1, {}).get("avg_rating"), lect2.get(e2, {}).get("avg_rating")))

# ══════════════════════════════════════════════════════════════════════
section("3. Courses — top three per level, with their emphasis areas")
# ══════════════════════════════════════════════════════════════════════

using(_CATEGORIES["courses"])
seed([
    {"username": "ZZh", "level": "100", "rating": 2,
     "ctx": {"course_rated": "COS 101 – Introduction to Computing Sciences",
             "emphasis_areas": ["Practical coding exercises & lab sessions",
                                "Up-to-date tools & modern technologies"]}},
    {"username": "ZZi", "level": "100", "rating": 2,
     "ctx": {"course_rated": "COS 101 – Introduction to Computing Sciences",
             "emphasis_areas": ["Practical coding exercises & lab sessions"]}},
    {"username": "ZZj", "level": "100", "rating": 4,
     "ctx": {"course_rated": "MTH 101 – Elementary Mathematics I",
             "emphasis_areas": ["Real-world case studies & industry examples"]}},
    {"username": "ZZk", "level": "400", "rating": 1,
     "ctx": {"course_rated": "IFT 403 – Mobile and Pervasive Computing",
             "emphasis_areas": ["Practical coding exercises & lab sessions"]}},
])

courses = db.course_summary(session=SESS, top_n=3)
lvls = {r["level"] for r in courses}
check("courses are grouped per level", lvls == {"100", "400"}, sorted(lvls))

top100 = [r for r in courses if r["level"] == "100"]
check("within 100 level, the most-rated course is first",
      top100 and top100[0]["course"].startswith("COS 101"),
      [r["course"] for r in top100])
check("its emphasis areas are counted, not just listed",
      top100 and dict(top100[0]["emphasis_areas"]).get(
          "Practical coding exercises & lab sessions") == 2,
      top100 and top100[0]["emphasis_areas"])
check("a course rated only once at 400 is not merged with the 100-level one",
      all(r["level"] == "400" for r in courses if r["course"].startswith("IFT 403")))

# ══════════════════════════════════════════════════════════════════════
section("4. Facilities — top five across all levels")
# ══════════════════════════════════════════════════════════════════════

using(_CATEGORIES["facilities"])
# Six flags of the same projector from six different levels, each with an
# urgency recorded. The urgency belongs INSIDE `ctx` — the rollup reads
# `context_data`, not a column of its own, and an earlier draft put it beside
# `facilities_flagged` where nothing read it, so the urgency counts came back
# empty while every other assertion passed.
for n in range(6):
    seed([{"username": f"ZZf{n}", "level": str(100 + n * 100), "rating": 2,
           "ctx": {"facilities_flagged": ["Projectors & display screens"],
                   "urgency": "High — Seriously disrupts studies",
                   "location": f"Block C Room {n + 1}"}}])
seed([
    {"username": "ZZz1", "level": "500", "rating": 1,
     "ctx": {"facilities_flagged": ["Backup power (generators / UPS)"]}},
    {"username": "ZZz2", "level": "100", "rating": 1,
     "ctx": {"facilities_flagged": ["Laboratory computers & workstations"]}},
])

fac = db.facility_summary(session=SESS, top_n=5)
check("at most five facilities are returned", len(fac) <= 5, len(fac))
check("the most-flagged item is first",
      fac and fac[0]["facility"] == "Projectors & display screens",
      fac and [f["facility"] for f in fac])
check("it counted every level it was flagged from",
      fac and fac[0]["reports"] == 6, fac and fac[0]["reports"])
check("facilities are not split by level",
      fac and fac[0]["levels"] and len(fac[0]["levels"]) == 6, fac and fac[0].get("levels"))
check("the urgent ones carry their urgency counts",
      fac and fac[0]["urgency_counts"].get("High — Seriously disrupts studies") == 6,
      fac and fac[0].get("urgency_counts"))
check("the rooms it was reported from are listed, worst first",
      fac and fac[0]["top_locations"] and len(fac[0]["top_locations"]) == 3,
      fac and fac[0].get("top_locations"))

# ══════════════════════════════════════════════════════════════════════
section("5. Nothing crashes on the awkward inputs")
# ══════════════════════════════════════════════════════════════════════

using(_CATEGORIES["edge"])
seed([
    {"username": "ZZedge1", "level": "200", "rating": 3,
     "ctx": {"lecturer_name": "", "challenges": [], "effective_methods": []}},
    {"username": "ZZedge2", "level": "200", "rating": 3,
     "ctx": {"lecturer_name": "!!!<img src=x onerror=alert(1)>",
             "challenges": ["<script>alert(2)</script>"], "effective_methods": []}},
])
edge = db.lecturer_summary(session=SESS)
check("a row with no lecturer is skipped rather than crashing",
      all(r["key"] for r in edge))
# The payload's *display* is stripped down to a grouping key, so the onerror
# text cannot survive into it. What matters is that the row is still grouped
# and still rendered — the escaping itself is `esc()`'s job at render time and
# is covered by the XSS suites. Before the current key scheme, "alert" was a
# surname of its own and the markup was being carried as a name.
check("a hostile lecturer name is grouped under a harmless key, not markup",
      "onerror" not in " ".join(r["key"] for r in edge),
      [r["key"] for r in edge])
check("...and the row still appears, so the feedback is not silently lost",
      any(r["key"] == "alert" for r in edge),
      [r["key"] for r in edge])
check("...marked as not from the handbook list",
      next((r["known"] for r in edge if r["key"] == "alert"), None) is False)

check("an empty session returns empty lists, not an error",
      db.lecturer_summary(session="ZZ_NO_SUCH_SESSION") == []
      and db.course_summary(session="ZZ_NO_SUCH_SESSION") == []
      and db.facility_summary(session="ZZ_NO_SUCH_SESSION") == [])

check("asking for more items than exist is not an error",
      len(db.facility_summary(session=SESS, top_n=500)) >= len(fac))

shutil.rmtree(TMP, ignore_errors=True)

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