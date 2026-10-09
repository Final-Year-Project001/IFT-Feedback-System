"""Run the whole verification suite.

    .venv\\Scripts\\python.exe tests\\run_all.py

Each script is executed in its own subprocess so that one crashing or calling
`sys.exit()` cannot take the rest of the run down with it — several of these
deliberately exercise failure paths.

    0 = every suite passed
    1 = at least one suite failed

`report_*.py` scripts are informational: they print a snapshot of the
sentiment engine and the lexicon gap and are always counted as passing, since
there is nothing in them to assert.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# SAFETY FENCE — the test suite must never write to a live database.
#
# These suites create, update and DELETE rows. If `FUTO_POSTGRES_URL` is set —
# including by a copy sitting in `.streamlit/secrets.toml`, which is how the
# deployed app is configured — the tests would happily do all of that to
# production. That is not hypothetical: a run inserted real rows into a live
# Neon database before this fence existed.
#
# `db_backend._url()` checks this before any other source, so it wins over both
# the environment and Streamlit's secrets.
os.environ["FUTO_DISABLE_POSTGRES"] = "1"

# The interpreter running this script, so the suite uses the same
# environment rather than whatever `python` happens to resolve to.
PYTHON = sys.executable

# Fast first, so a syntax error surfaces in the first second rather than
# after the slow end-to-end suites.
SUITES = [
    # The self-tests come first and sit next to the checker they verify. A
    # gate that reports "clean" is only worth anything if you have watched it
    # fail on a real hole, and each of these found a defect in its own
    # checker on first run.
    "test_undefined_names_selftest.py",   # is the checker itself trustworthy?
    "test_undefined_names.py",
    "test_xss_static_selftest.py",        # does the XSS gate catch real holes?
    "test_xss_static.py",
    "test_username_case.py",
    "test_streamlit_calls_selftest.py",   # does the icon sweep still bite?
    "test_streamlit_calls.py",
    "test_css.py",
    "test_dept_name_integrity.py",      # did the IT -> IFT rename eat any "it"?
    "test_consistency.py",
    "test_schema.py",
    "test_postgres_backend.py",         # SQL translation + backup file safety
    "test_dashboard_math.py",
    # test_model_roundtrip / test_model_training_trigger were removed with
    # train_model.py. There is no trained classifier to round-trip and nothing
    # to train from: the free-text comment box is gone, so a correction is no
    # longer a labelled sentence but an override of a rating band.
    "test_rating_engine.py",            # the rating -> band rule, in one place
    "test_session_binding.py",      # a copied link must not sign anyone in
    "test_session_persist.py",        # registration persists; a missed persist is healed; round-trip works
    "test_semester_gate.py",        # active semester: schema, admin control, student gate
    "test_analysis_modules.py",      # per-lecturer / course / facility rollups
    "test_chart_cards.py",           # charts sit in a card, and the trend is bars
    "test_dialog_close.py",          # every dismiss button must close its dialog
    "test_decision_band.py",        # a card label must match the numbers beside it
    "test_user_management.py",
    "test_result_dialogs.py",
    "test_password_migration.py",    # do legacy hashes actually get upgraded?
    "test_submission_flow.py",
    "test_xss_runtime.py",           # does a real payload reach any page raw?
    "test_app_render.py",
]

# The two `report_sentiment_engine.py` / `report_lexicon_gap.py` scripts went
# with the lexicon they were reporting on.
REPORTS = []

# Streamlit's bare-mode warning is noise; the real errors still print.
NOISE = re.compile(
    r"missing ScriptRunContext|Uncaught app execution|^\s*File \"|^\s{4}"
    r"|^\s*\^+\s*$|^\s*Traceback|^\s*\w+Error|^\s*assert|^\s*at ",
)

PASS_RE = re.compile(r"\[PASS\]")
FAIL_RE = re.compile(r"\[FAIL\]")


def run(name, quiet):
    path = HERE / name
    started = time.time()
    try:
        proc = subprocess.run(
            [PYTHON, str(path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return name, None, 0, 0, time.time() - started, ["timed out after 30 min"]

    out = (proc.stdout or "") + (proc.stderr or "")
    npass = len(PASS_RE.findall(out))
    nfail = len(FAIL_RE.findall(out))

    lines = out.splitlines()
    if quiet:
        # Keep only lines that carry a verdict or an outright crash.
        lines = [ln for ln in lines
                 if not NOISE.search(ln) and ln.strip()
                 and ("[PASS]" in ln or "[FAIL]" in ln
                      or "Traceback" in ln or "Error" in ln
                      or "All checks" in ln or "CHECKS" in ln
                      or "NO UNDEFINED" in ln or "UNESCAPED" in ln
                      or "FAILED" in ln or "Passed" in ln)]
    return name, proc.returncode, npass, nfail, time.time() - started, lines


def main():
    quiet = "-v" not in sys.argv and "--verbose" not in sys.argv

    print("=" * 78)
    print(f"  FUTO IFT Feedback System — verification suite")
    print(f"  {len(SUITES)} suite(s) + {len(REPORTS)} report(s)   "
          f"(use -v for full output)")
    print("=" * 78)
    print()

    failures = []
    total_pass = total_fail = 0

    for name in SUITES:
        name, rc, npass, nfail, secs, lines = run(name, quiet)
        total_pass += npass
        total_fail += nfail
        ok = rc == 0 and nfail == 0
        if not ok:
            failures.append(name)
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name:<36} {npass:>4} passed  "
              f"{nfail:>3} failed  {secs:6.1f}s")
        if not ok or not quiet:
            for ln in lines:
                print(f"         {ln[:110]}")
        if not ok:
            print(f"         exit code: {rc}")

    print()
    print("-" * 78)
    for name in REPORTS:
        name, rc, npass, nfail, secs, lines = run(name, True)
        status = "ran" if rc == 0 else f"exit {rc}"
        print(f"  [ ---- ] {name:<36} informational ({status}, {secs:5.1f}s)")
        print()
        for ln in lines[:6]:
            print(f"         {ln[:110]}")
        print(f"         ... run `.venv\\Scripts\\python.exe tests\\{name}` for the rest")
    print("-" * 78)

    print()
    print("=" * 78)
    print(f"  {total_pass} check(s) passed, {total_fail} failed, "
          f"{len(failures)} suite(s) failed")
    if failures:
        for f in failures:
            print(f"    FAILED: {f}")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
