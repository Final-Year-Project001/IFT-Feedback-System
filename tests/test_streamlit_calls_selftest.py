"""Self-test for the icon sweep inside test_streamlit_calls.py (Check 4).

A name check that is silently broken — a regex that stopped matching, a table
that came back empty, an exception swallowed into "cannot check" — reports a
clean tree, which is indistinguishable from a clean tree. This points the real
`scan_icons` at fixtures and asserts it flags the two names that actually took
pages down during development (`:material/neural_network:` and the Lucide
`shield-alert`), leaves the real replacements alone, and still ignores comment
lines and the definitions inside `icons.py` itself.

It also mutates each matching regex in turn and requires the result to get
*worse*, which is what proves the regexes are load-bearing rather than
decorative.

Run:  .venv\\Scripts\\python.exe tests\\test_streamlit_calls_selftest.py
"""
import importlib.util
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
SCRATCH = tempfile.mkdtemp(prefix="futo_iconselftest_")

# ── Load the checker without running its main() ─────────────────────────
# NOT `spec.loader.exec_module` under a replaced sys.stdout: importing the
# checker must not close the stream this script is printing to.
spec = importlib.util.spec_from_file_location("_streamlit_calls",
                                              HERE / "test_streamlit_calls.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

# Drive the real Streamlit validator and the real icons.py table, so the test
# fails if either drifts — but keep them injectable so a machine without
# Streamlit still exercises the wiring rather than skipping it.
REAL_MATERIAL_OK = checker._material_ok
REAL_ICON_NAMES = checker.known_icon_names(str(ROOT))

# Each case: (filename, source, must_flag, why)
CASES = [
    # A name that is genuinely not in Streamlit's Material set. This is the
    # exact string that was shipped and that raised StreamlitAPIException
    # from inside st.button(), taking the whole page down.
    ("bug_material.py",
     'st.button("Train", icon=":material/neural_network:")\n',
     True, "the Material name that was actually shipped and crashed a page"),
    ("ok_material.py",
     'st.button("Train", icon=":material/model_training:")\n',
     False, "its real replacement"),
    # Lucide names come from this repo's icons.py, and a miss renders a
    # placeholder circle silently — no exception, so only this check sees it.
    ("bug_lucide.py",
     'html = i("shield-alert", 13, "#dc2626")\n',
     True, "a Lucide slug icons.py does not define"),
    ("ok_lucide.py",
     'html = i("star", 12)\n',
     False, "a Lucide slug icons.py does define"),
    # Commented-out code must not be audited.
    ("ok_comment.py",
     '# example only: st.button("x", icon=":material/neural_network:")\n'
     'x = 1\n',
     False, "the bad name appears only in a comment"),
    # icons.py defines the table; its own `i(...)`-looking lines are mappings,
    # not call sites, so it is skipped for Lucide lookups.
    ("icons.py",
     'def i(name, size=16):\n'
     '    return PATHS.get(name, "<svg></svg>")\n'
     'x = i("a-slug-that-does-not-exist", 12)\n',
     False, "icons.py is skipped for Lucide lookups"),
]

failures = []


def audit(fname, src):
    path = os.path.join(SCRATCH, fname)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)
    problems, materials, lucides = checker.scan_icons(
        [path], icon_names=REAL_ICON_NAMES, material_ok=REAL_MATERIAL_OK,
        root=SCRATCH)
    return problems, materials, lucides


print("=" * 76)
print("  test_streamlit_calls.py self-test — does the icon sweep still catch")
print("  the names that crash a page, without false-flagging good ones?")
print("=" * 76)

ok = True
try:
    for fname, src, must_flag, why in CASES:
        problems, materials, lucides = audit(fname, src)
        if must_flag:
            passed = len(problems) > 0
            detail = f"flagged ({len(problems)})"
        else:
            passed = not problems
            detail = "clean" if passed else f"FALSE POSITIVE: {problems}"
        print(f"  [{'PASS' if passed else 'FAIL'}] {fname:<20} {detail}")
        print(f"         ({why})")
        if not passed:
            ok = False

    # The validator must be able to say no at all. If `_material_ok` returned
    # None for everything the cases above would all pass as "clean".
    print()
    print("=" * 76)
    print("  Validator liveness")
    print("=" * 76)
    live = (REAL_MATERIAL_OK("model_training") is True
            and REAL_MATERIAL_OK("neural_network") is False)
    print(f"  [{'PASS' if live else 'FAIL'}] Streamlit rejects a fake Material "
          f"name and accepts a real one")
    if not live:
        ok = False
        print("         the cases above proved nothing: the validator is inert")
    if not REAL_ICON_NAMES:
        print("  [FAIL] icons.py yielded no slugs — the table parse is broken")
        ok = False
    else:
        print(f"  [PASS] icons.py parsed ({len(REAL_ICON_NAMES)} slugs)")

    # ── Mutation check ────────────────────────────────────────────────
    # Disable each matching regex and require at least one bug case to stop
    # being flagged. A regex that is never reachable changes nothing when
    # removed, and is pretending to be a safeguard.
    print()
    print("=" * 76)
    print("  Mutation check — is each matcher load-bearing?")
    print("=" * 76)
    baseline_bad = sum(
        1 for fname, src, must_flag, _ in CASES
        if bool(audit(fname, src)[0]) != must_flag
    )
    if baseline_bad:
        print(f"  [FAIL] baseline wrong on {baseline_bad} case(s)")
        ok = False
    else:
        print(f"  [PASS] baseline correct on all {len(CASES)} case(s)")

    for attr in ("MATERIAL_RE", "LUCIDE_RE"):
        original = getattr(checker, attr)
        setattr(checker, attr, re.compile(r"(?!x)x"))
        worse = sum(
            1 for fname, src, must_flag, _ in CASES
            if bool(audit(fname, src)[0]) != must_flag
        )
        setattr(checker, attr, original)
        if worse:
            print(f"  [PASS] {attr:<12} load-bearing ({worse} case(s) change)")
        else:
            print(f"  [FAIL] {attr:<12} DEAD — disabling it changes nothing")
            ok = False
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)

print()
print("=" * 76)
print("  SELFTEST PASSED" if ok
      else "  SELFTEST FAILED — the icon sweep is not trustworthy")
print("=" * 76)
raise SystemExit(0 if ok else 1)
