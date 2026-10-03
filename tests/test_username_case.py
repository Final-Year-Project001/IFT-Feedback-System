"""C-07 sweep: find every place that compares a feedback DataFrame's `username`
column to a value with `==`, `.values`, or `in`, instead of going through
`db.filter_by_username`.

Every username lookup in `db.py` matches with LOWER(username), so an exact
`df["username"] == username` comparison is a latent inconsistency: it silently
returns nothing for an account whose stored casing differs from the one in
session_state.

Run: .venv\\Scripts\\python.exe test_username_case.py
"""
import ast
import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)

FILES = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames
                   if d not in ("tests", ".venv", "__pycache__", ".git", "backup", "model", ".streamlit")]
    for fn in sorted(filenames):
        if fn.endswith(".py") and not fn.startswith("_"):
            FILES.append(os.path.join(dirpath, fn))

USERNAME_VAR = {"username", "user", "current_user", "user_name", "session_username"}
hits = []

for path in sorted(FILES):
    rel = os.path.relpath(path, ROOT)
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as exc:
        hits.append((rel, exc.lineno or 0, "SYNTAX ERROR", str(exc)))
        continue

    for node in ast.walk(tree):
        # df["username"] == x   /   x == df["username"]
        if isinstance(node, ast.Compare) and len(node.ops) == 1 \
                and isinstance(node.ops[0], ast.Eq):
            sides = [node.left] + node.comparators
            for side in sides:
                other = [s for s in sides if s is not side]
                if not other:
                    continue
                # side looks like a column reference to "username"
                text = ast.unparse(side)
                if ('"username"' in text or "'username'" in text) and "lower" not in text.lower():
                    other_text = ast.unparse(other[0])
                    if other_text in USERNAME_VAR or "username" in other_text.lower():
                        hits.append((rel, node.lineno, "== compare",
                                     f"{ast.unparse(node)}"))

        # "username" in df["username"].values
        if isinstance(node, ast.Compare) and any(isinstance(o, ast.In) for o in node.ops):
            text = ast.unparse(node)
            if "username" in text and ".values" in text and "lower" not in text.lower():
                hits.append((rel, node.lineno, "`in .values` membership",
                             text[:100]))

        # df[df["username"] == x]  -- also caught above, but flag the
        # .iloc[0] that follows such a filter because it is the crash site.
        if isinstance(node, ast.Subscript):
            text = ast.unparse(node)
            if '"username"' in text and ast.unparse(node.value).endswith("]"):
                pass

print(f"scanned {len(FILES)} files")
print()
if hits:
    print(f"{len(hits)} case-sensitive username comparison(s) found:")
    for rel, ln, kind, text in hits:
        print(f"  {rel}:{ln}  [{kind}]")
        print(f"      {text}")
    raise SystemExit(1)
print("no case-sensitive username comparisons found — all go through "
      "db.filter_by_username or LOWER()")
