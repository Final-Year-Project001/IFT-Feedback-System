"""Sanity-check for test_undefined_names.py: does it actually catch the bug
class it claims to?

A static check that reports "no undefined names" is worthless unless you have
seen it fail on a real one — otherwise a silently broken version of the check
that always returns clean looks identical to a working one. This injects six
shapes of module (three real bugs, three things that must NOT be flagged) into
a temporary directory, runs the checker over each, and asserts the verdict.

Run:  .venv\\Scripts\\python.exe tests\\test_undefined_names_selftest.py
"""
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# Reconfigure in place rather than wrapping: a `TextIOWrapper` replacement
# drops the last reference to the old wrapper, its dealloc closes the
# underlying buffer, and the next print raises "I/O operation on closed
# file". The other scripts get away with it because `sys.__stdout__` still
# holds a reference; this one does not.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = str(Path(__file__).resolve().parent.parent)
# A real temp directory, not a folder inside the repo: the previous version
# wrote `_nameselftest/` into the project root and relied on the caller to
# delete it, which left an untracked directory sitting in `git status`.
SCRATCH = tempfile.mkdtemp(prefix="futo_nameselftest_")

CASES = {
    # The exact shape that broke app.py: a constant used inside a function
    # body with no import.
    "plain.py": "import os\n\n\ndef show(session):\n    return [ALL_SESSIONS_LABEL] + session\n",
    # Used at module scope directly (the other app.py failure mode).
    "toplevel.py": "X = MISSING_THING\n",
    # Used inside a class body's method.
    "inclass.py": "class C:\n    def m(self):\n        return OTHER_NAME\n",
    # A legitimate `global` declaration must NOT be flagged.
    "declared.py": (
        "TOTAL = 0\n\n\ndef add(n):\n    global TOTAL\n    TOTAL += n\n    return TOTAL\n"
    ),
    # A name that IS imported must not be flagged.
    "imported.py": (
        "from config import ALL_SESSIONS_LABEL\n\n\ndef f():\n"
        "    return ALL_SESSIONS_LABEL\n"
    ),
    # The same, written as a PARENTHESISED multi-line import. `symtable` does
    # not mark these names as imported, so the checker needed an AST pass to
    # see them at all — and that blind spot is invisible until a real page
    # imports something that way and gets reported as undefined.
    "imported_multiline.py": (
        "from config import (\n    ALL_SESSIONS_LABEL,\n    CURRENT_SESSION,\n)\n"
        "\n\ndef f():\n    return ALL_SESSIONS_LABEL + CURRENT_SESSION\n"
    ),
    # And with an alias, which is a third spelling of the same import.
    "imported_alias.py": (
        "from config import CAT_META as META\n\n\ndef f():\n    return META\n"
    ),
    # A closure variable (bound in the enclosing function) must not be flagged.
    "closure.py": (
        "def outer(a):\n    total = 0\n\n    def inner(b):\n"
        "        nonlocal total\n        total += a + b\n        return total\n\n"
        "    return inner\n"
    ),
}

EXPECT = {
    "plain.py": "ALL_SESSIONS_LABEL",
    "toplevel.py": "MISSING_THING",
    "inclass.py": "OTHER_NAME",
    "declared.py": None,
    "imported.py": None,
    "imported_multiline.py": None,
    "imported_alias.py": None,
    "closure.py": None,
}

# Load the checker without running its __main__ block.
import importlib.util

checker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "test_undefined_names.py")
spec = importlib.util.spec_from_file_location("_undefined_names_checker",
                                              checker_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.ROOT = SCRATCH

print("=" * 74)
print("  test_undefined_names.py self-test — does it detect the bug class")
print("  it claims to, without false-flagging legal code?")
print("=" * 74)

ok = True
try:
    for fname, want in EXPECT.items():
        with open(os.path.join(SCRATCH, fname), "w", encoding="utf-8") as fh:
            fh.write(CASES[fname])
        mod.failures = []
        buf = io.StringIO()
        real, sys.stdout = sys.stdout, buf
        try:
            mod.check_module(fname)
        finally:
            sys.stdout = real
        out = buf.getvalue()
        flagged = "[FAIL]" in out
        found = re.findall(r"'([^']+)' is used", out)

        if want is None:
            passed = not flagged
            detail = "correctly NOT flagged"
            if flagged:
                detail += f"  (false positive: {found})"
        else:
            passed = flagged and want in found
            detail = f"flagged {found}"
        print(f"  [{'PASS' if passed else 'FAIL'}] {fname:<14} {detail}")
        if not passed:
            ok = False
            print(out)
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)

print()
print("=" * 74)
print("  SELFTEST PASSED" if ok else "  SELFTEST FAILED — the checker is not trustworthy")
print("=" * 74)
raise SystemExit(0 if ok else 1)
