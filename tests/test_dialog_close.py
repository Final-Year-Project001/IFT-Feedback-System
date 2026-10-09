"""Verification for the dialogs closing when they are dismissed.

Scope — what this file is FOR:

"Start using the system" did nothing. The result dialog's dismiss button had
its return value discarded:

    st_compat.button(payload["button_label"] or "Continue", ...)

No `if`, no `st.rerun()`. A Streamlit dialog only closes when the run that
opened it is abandoned — the documented way to do that is `st.rerun()` inside
the dialog body — so the button reran the script, the dialog was opened again by
`render_parked_dialog()` on that new run, and it sat there until the user
clicked outside it.

This covers the shape of every dismiss path, because the two confirmation
dialogs in user management *did* call `st.rerun()` and the result dialog did
not. That inconsistency is exactly what a user notices and nobody reports as a
bug, so it is pinned here.

Run: .venv\\Scripts\\python.exe tests\\test_dialog_close.py
"""
import ast
import re
import textwrap
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

results: list = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


# ══════════════════════════════════════════════════════════════════════
section("1. Every button inside a dialog has a handler")
# ══════════════════════════════════════════════════════════════════════


def dialog_bodies(path: Path):
    """The source of every function used as a `st.dialog` body."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # A dialog body is a function decorated with @st_compat.dialog (or
        # @st.dialog), which is what the real call sites use.
        deco_names = []
        for d in node.decorator_list:
            dsrc = ast.dump(d)
            if "dialog" in dsrc:
                deco_names.append(ast.unparse(d))
        if not deco_names:
            continue
        # `textwrap.dedent` on the whole slice. A nested `def` carries its original
        # indentation, and `ast.parse` rejects that as an unexpected indent —
        # which would report every dialog as unparseable rather than as correct.
        body = textwrap.dedent("\n".join(lines[node.lineno - 1: node.end_lineno]))
        out.append((node.name, deco_names, body))
    return out


PAGES = sorted(Path("app_pages").glob("*.py")) + [Path("components.py")]

found_any = 0
bare_buttons = []
for path in PAGES:
    for fname, decos, body in dialog_bodies(path):
        found_any += 1
        tree = ast.parse(body)
        for node in ast.walk(tree):
            # st.button(...) or st_compat.button(...)
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "button"):
                continue
            # Two ways a button is legitimately handled, and both must count:
            #   1. `if st.button(...)`  — the Call is an If's test
            #   2. `x = st.button(...)` then `if x:` — the value is bound and
            #      read later. This is what the two confirmation dialogs do, and
            #      treating it as unhandled reported both of them as broken.
            handled = set()
            for sub in ast.walk(tree):
                if isinstance(sub, ast.If) and isinstance(sub.test, ast.Call):
                    handled.add(id(sub.test))
            if id(node) in handled:
                continue
            # Bound to a name?
            bound_to = None
            for stmt in ast.walk(tree):
                targets = []
                if isinstance(stmt, ast.Assign):
                    targets = [t.id for t in stmt.targets
                               if isinstance(t, ast.Name)]
                elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    targets = [stmt.target.id]
                if any(t.value is node for t in targets if hasattr(t, "value")):
                    bound_to = targets
                elif targets and stmt.value is node:
                    bound_to = targets
            if bound_to:
                # ...and that name is actually tested somewhere afterwards.
                tested = any(
                    isinstance(sub, ast.If)
                    and any(isinstance(c, ast.Name) and c.id in bound_to
                            for c in ast.walk(sub.test))
                    for sub in ast.walk(tree)
                )
                if tested:
                    continue
                bare_buttons.append(
                    f"{path}:{fname}() — button bound to {bound_to} but never tested")
                continue
            bare_buttons.append(f"{path}:{fname}() — button result discarded")

check("at least one dialog body was found to inspect", found_any > 0)
check("no button inside a dialog is called without an `if` around it",
      not bare_buttons, bare_buttons)

# ══════════════════════════════════════════════════════════════════════
section("2. Handling a button means the dialog closes")
# ══════════════════════════════════════════════════════════════════════

# The dismiss must `st.rerun()`, which abandons the run that opened the modal
# so the decorator cannot re-open it. Calling something else — `st.success`,
# clearing session state, setting a flag — leaves the dialog on screen.
no_rerun = []
for path in PAGES:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        has_dialog_decorator = any("dialog" in ast.dump(d)
                                   for d in node.decorator_list)
        if not has_dialog_decorator:
            continue
        fn_src = ast.unparse(node)
        if ".button(" not in fn_src:
            continue
        # A dialog that offers only Cancel and Confirm is fine as long as at
        # least one branch reruns. Count them.
        reruns = fn_src.count(".rerun()")
        if reruns == 0:
            no_rerun.append(f"{path}:{node.name}")
check("every dialog with a button has a st.rerun() path", not no_rerun, no_rerun)

# ══════════════════════════════════════════════════════════════════════
section("3. The specific case that was reported")
# ══════════════════════════════════════════════════════════════════════

comp = Path("components.py").read_text(encoding="utf-8")
# The dialog is now a top-level function `_render_result_dialog` (not nested
# inside another function), so Streamlit can reliably register it.
body = comp.split("def _render_result_dialog")[1]

check("the result dialog exists", "def _render_result_dialog" in comp)
check("its dismiss button is now guarded by an `if`",
      re.search(r"if\s+st_compat\.button\(", body) is not None
      or re.search(r"if\s+st\.button\(", body) is not None,
      "the button result is still discarded")
check("...and the guarded branch calls st.rerun()",
      "st.rerun()" in body.split("button(")[1][:400],
      body.split("button(")[1][:200])
check("the button result is not assigned to an unused name",
      "_ = st_compat.button(" not in body)

# The bug's other half: a dialog parked on a previous run is re-opened by
# `render_parked_dialog()` on every rerun. That is correct — but only while the
# dialog is actually meant to be there, so the payload must be popped, or a
# dismissed dialog comes straight back.
check("the parked payload is popped before it is shown",
      "pop(_RESULT_DIALOG_KEY" in comp)
check("...so a dismissed dialog does not return on the next run",
      comp.split("def render_parked_dialog")[1].split("\ndef ")[0].count("pop(") >= 1)

# ══════════════════════════════════════════════════════════════════════
section("4. Parking is still correct")
# ══════════════════════════════════════════════════════════════════════

check("park_result_dialog writes to session state, not to the DOM",
      "_RESULT_DIALOG_KEY] = {" in comp)
check("result_dialog exists for the no-rerun case", "def result_dialog(" in comp)
check("the dialog decorator goes through st_compat, not st directly",
      "@st_compat.dialog(" in comp)
check("the fallback path still exists for old Streamlit",
      "def dialog(" in Path("st_compat.py").read_text(encoding="utf-8"))

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