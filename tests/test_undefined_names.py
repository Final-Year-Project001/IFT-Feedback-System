"""Static check for names that are *used* but never defined or imported.

`py_compile` only proves a file parses. It does not catch the single most
common runtime break in a refactor like the C-05/C-06 one: replacing a
string literal with a constant and forgetting to add it to the file's
import list. The app then fails at module scope with a bare

    NameError: name 'ALL_SESSIONS_LABEL' is not defined

and every page is dead — while every syntax check is green.

This walks each module's `symtable` (stdlib, so no new dependency) and for
every scope resolves which identifiers are referenced as globals. A name is
a bug if it is not:

  * assigned or imported at module level,
  * a builtin,
  * a module-level dunder / `__name__`-style attribute,
  * declared `global` inside the scope that uses it, or
  * an injected name (Streamlit's bare-mode globals, pytest's, etc.).

Run: .venv\\Scripts\\python.exe test_undefined_names.py
"""
import ast
import builtins
import io
import os
import symtable
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)

failures = []

# ── Names injected by Streamlit's bare-mode script runner ────────────────
INJECTED = {
    "st",                      # the running script module (not used here, but cheap)
}

BUILTINS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "__debug__", "WindowsError",
}


def collect_module_names(path):
    """Module-level bindings: assignments, imports, defs, classes, globals.

    `symtable` alone is not enough for a `from x import (a, b, c)` written
    across several lines. `sym.is_imported()` is False for every name in a
    parenthesised `from` import, so a multi-line import of a perfectly ordinary
    name reads as undefined — and adding the name to a second single-line import
    "fixes" the report without fixing anything.

    So the AST is consulted as well, and the two are unioned. Either alone has a
    blind spot; together they cover plain and parenthesised imports, and a name
    that really is undefined is still reported by neither.
    """
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    top = symtable.symtable(src, os.path.basename(path), "exec")
    names = set()
    for sym in top.get_symbols():
        if sym.is_assigned() or sym.is_imported() or sym.is_namespace():
            names.add(sym.get_name())

    try:
        tree = ast.parse(src, os.path.basename(path))
    except SyntaxError:
        return src, top, names

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                # A star import binds nothing we can name; skip it rather than
                # recording a literal "*" that would mask a real miss.
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)

    return src, top, names


def used_globals(top):
    """Names referenced from inside a nested scope but not bound there.

    `symtable` already resolves lexical binding, so a name that IS assigned
    anywhere in an enclosing function scope is reported as a *local* symbol
    of that function, not as a global reference. What shows up here is
    genuinely a free/global reference from a nested scope, plus the
    top-level module's own unresolved references.
    """
    out = []

    def walk(table, scope_chain):
        for sym in table.get_symbols():
            n = sym.get_name()
            if n in scope_chain:          # bound somewhere on the way out
                continue
            if sym.is_global() or (not sym.is_assigned() and not sym.is_imported()
                                   and not sym.is_parameter() and not sym.is_local()):
                # A top-level module symbol is global by definition; a nested
                # one only counts if it was never assigned in this scope.
                if sym.is_referenced() and (sym.is_global() or table.get_type() == "module"):
                    out.append((table.get_name(), n))
        for child in table.get_children():
            # Names bound by THIS table are visible to its children.
            inherited = set(scope_chain)
            for sym in table.get_symbols():
                if sym.is_assigned() or sym.is_imported() or sym.is_parameter():
                    inherited.add(sym.get_name())
            walk(child, inherited)

    walk(top, set())
    return out


def check_module(rel):
    path = os.path.join(ROOT, rel)
    try:
        src, top, mod_names = collect_module_names(path)
    except SyntaxError as exc:
        print(f"  [FAIL] {rel}: does not parse — {exc}")
        failures.append(f"{rel} (syntax)")
        return

    known = set(mod_names) | BUILTINS | INJECTED
    missing = {}
    for scope, name in used_globals(top):
        if name in known or name.startswith("__"):
            continue
        # A `global x` declared in the scope that uses it.
        if re_global(src, name):
            continue
        missing.setdefault(name, []).append(scope)

    if missing:
        for name, scopes in sorted(missing.items()):
            where = ", ".join(sorted(set(scopes))[:3])
            print(f"  [FAIL] {rel}: '{name}' is used in [{where}] "
                  f"but never defined or imported at module level")
            failures.append(f"{rel}: {name}")
    else:
        print(f"  [PASS] {rel}  ({len(mod_names)} module binding(s), no undefined names)")


def re_global(src, name):
    """True if any `global <name>` declaration exists in the file."""
    import re
    return re.search(r"^\s*global\s+[^#\n]*\b" + re.escape(name) + r"\b", src, re.M) is not None


def main():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # "tests" is skipped on purpose: these scripts are not the app, and
        # test_undefined_names_selftest.py deliberately contains undefined
        # names as fixtures. Scanning them would report the fixtures as bugs.
        #
        # ".kilo" holds agent worktrees -- a stale duplicate of this same app
        # inside the repo. Every finding in a copy is a finding in a file that
        # does not ship, so it is skipped alongside .venv.
        dirnames[:] = [d for d in dirnames
                       if d not in ("tests", ".venv", "__pycache__", "backup",
                                    "model", ".git", ".streamlit", ".kilo")]
        for fn in sorted(filenames):
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            files.append(rel)

    files.sort()
    print("=" * 74)
    print(f"  Undefined-name scan — {len(files)} module(s)")
    print("=" * 74)
    for rel in files:
        check_module(rel)

    print()
    print("=" * 74)
    if failures:
        print(f"  {len(failures)} UNDEFINED NAME(S):")
        for f in failures:
            print(f"    - {f}")
        raise SystemExit(1)
    print("  NO UNDEFINED NAMES")


if __name__ == "__main__":
    main()
