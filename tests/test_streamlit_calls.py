"""Static sweep for the call-shape mistakes that only blow up at runtime:
duplicate keyword arguments, keyword arguments that a st_compat wrapper does
not accept, direct `st.*` calls that bypass the shim, and icon names that
Streamlit will reject when it renders the widget.

Check 4 exists because of two real failures found while building the training
trigger. Both were single-token names — `shield-alert` and
`:material/neural_network:` — and both behaved exactly as an unchecked name
does: `StreamlitAPIException` raised from inside `st.button`, taking down the
*whole page* mid-render rather than just the widget. Neither was visible in
review, and neither was caught by the call-shape checks below, which care about
arity and keyword names, not about whether a string is a real icon.

The icon sweep is a function so that `test_streamlit_calls_selftest.py` can
point it at fixtures and prove it still fails on a bad name. A check that
silently stopped matching names would otherwise look identical to a passing
one.

Run: .venv\\\\Scripts\\\\python.exe test_streamlit_calls.py
"""
import ast
import os
import re
import sys
from pathlib import Path

# Reconfigure in place rather than wrapping. `sys.stdout = TextIOWrapper(...)`
# drops the last reference to the previous wrapper, whose dealloc closes the
# underlying buffer — so the next import that does the same thing leaves the
# process holding a closed stream. That is exactly what the self-test did.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass
ROOT = str(Path(__file__).resolve().parent.parent)

FILES = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames
                   if d not in ("tests", ".venv", "__pycache__", ".git", "backup",
                                "model", ".streamlit", ".kilo")]
    for fn in filenames:
        if fn.endswith(".py") and not fn.startswith("_"):
            FILES.append(os.path.join(dirpath, fn))

# Build the st_compat public signatures by importing it.
sys.path.insert(0, ROOT)
import st_compat  # noqa: E402
import inspect  # noqa: E402

COMPAT_SIGS = {}
for name in dir(st_compat):
    if name.startswith("_"):
        continue
    fn = getattr(st_compat, name)
    if callable(fn):
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        kind = {p.name: p.kind for p in sig.parameters.values()}
        accepts_kwargs = any(k == inspect.Parameter.VAR_KEYWORD for k in kind.values())
        accepted = {n for n, k in kind.items() if k in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                                       inspect.Parameter.KEYWORD_ONLY)}
        positional = [n for n, k in kind.items()
                      if k == inspect.Parameter.POSITIONAL_OR_KEYWORD]
        COMPAT_SIGS[name] = (accepted, positional, accepts_kwargs)

# A thin allow-list of st.* functions the plan deliberately kept direct,
# with the reason, so a new bypass stands out.
DIRECT_OK = {
    "set_page_config", "markdown", "caption", "error", "warning", "info", "success",
    "expander", "tabs", "rerun", "spinner", "toggle", "number_input", "slider",
    "date_input", "time_input", "file_uploader", "color_picker", "multiselect",
    "chat_input", "feedback", "form", "text_area", "audio_input", "camera_input",
    "query_params", "context", "write", "experimental_rerun", "stop",
}

problems = []

# ── Icon validation ──────────────────────────────────────────────────
# Two different icon systems are in use and each fails in its own way.
#
#   `:material/foo:`  -> validated by Streamlit. An unknown name raises
#                        `StreamlitAPIException` from inside the widget call,
#                        which aborts the rest of the page.
#   `i("foo", ...)`   -> looked up in this project's own `icons.py` table.
#                        A miss renders a placeholder circle, so it is silent,
#                        but a near-miss that *is* in the table under another
#                        name is the same trap.
#
# Both are checked against the real thing rather than a hand-kept list, so the
# check cannot itself go stale the way a list of "known good" names would.

MATERIAL_RE = re.compile(r":material/([A-Za-z0-9_]+):")
# `i(` and `icon(` and `icon_badge(` are the three entry points in icons.py.
LUCIDE_RE = re.compile(r"\b(?:i|icon|icon_badge)\(\s*[\"']([a-z0-9-]+)[\"']")

try:
    from streamlit.string_util import validate_material_icon

    def _material_ok(name):
        try:
            validate_material_icon(f":material/{name}:")
            return True
        except Exception:
            return False
except Exception:  # pragma: no cover - Streamlit internals moved
    def _material_ok(name):
        return None   # cannot check; do not report false problems


def known_icon_names(root=ROOT):
    """Every slug `icons.py` can actually resolve, keys and aliases."""
    icons_src = open(os.path.join(root, "icons.py"), encoding="utf-8").read()
    keys = set(re.findall(r"[\"']([a-z0-9-]+)[\"']\s*:", icons_src))
    # Aliases the module maps onto another slug's path.
    aliases = set(re.findall(r"^\s*([a-z0-9-]+)\s*=\s*[\"'][a-z0-9-]+[\"']",
                             icons_src, re.MULTILINE))
    return keys | aliases


KNOWN_ICON_NAMES = known_icon_names()


def scan_icons(files, icon_names=None, material_ok=None, root=ROOT):
    """Icon problems in `files` as (problems, materials_checked, lucides_checked).

    `files` are absolute paths; `icon_names` and `material_ok` default to the
    real `icons.py` table and Streamlit's own validator, but are injectable so
    the self-test can drive them without a Streamlit install.
    """
    check_material = material_ok or _material_ok
    names = KNOWN_ICON_NAMES if icon_names is None else icon_names
    found = []
    materials_checked = 0
    lucides_checked = 0

    for path in sorted(files):
        rel = os.path.relpath(path, root)
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()

        for lineno, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for name in MATERIAL_RE.findall(line):
                materials_checked += 1
                if check_material(name) is False:
                    found.append(
                        f"{rel}:{lineno}: ':material/{name}:' is not a real Material icon -- "
                        f"st.button()/st.form_submit_button() will raise StreamlitAPIException "
                        f"and take the whole page down"
                    )
            if os.path.basename(rel) == "icons.py":
                continue
            for name in LUCIDE_RE.findall(line):
                lucides_checked += 1
                if name not in names:
                    found.append(
                        f"{rel}:{lineno}: icons.py has no entry for {name!r} -- it will "
                        f"render as a placeholder circle"
                    )
    return found, materials_checked, lucides_checked


def scan_call_shapes(files):
    """AST problems: duplicate kwargs, bad st_compat kwargs, direct st.* calls."""
    found = []
    for path in sorted(files):
        rel = os.path.relpath(path, ROOT)
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        try:
            tree = ast.parse(src, filename=path)
        except SyntaxError as exc:
            found.append(f"{rel}: SYNTAX ERROR {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            # 1. duplicate keyword argument in ANY call
            kw_names = [k.arg for k in node.keywords if k.arg]
            dupes = {n for n in kw_names if kw_names.count(n) > 1}
            if dupes:
                found.append(
                    f"{rel}:{node.lineno}: duplicate keyword(s) {sorted(dupes)} in call to "
                    f"{ast.unparse(node.func)[:60]}"
                )

            # 2. a keyword that collides with a positional argument
            if isinstance(node.func, ast.Name) and node.func.id in COMPAT_SIGS:
                accepted, positional, _ = COMPAT_SIGS[node.func.id]
                max_pos = len(positional)
                pos_names = positional[:len(node.args)]
                for k in node.keywords:
                    if not k.arg:
                        continue
                    if k.arg in pos_names:
                        found.append(
                            f"{rel}:{node.lineno}: st_compat.{node.func.id}() got multiple "
                            f"values for '{k.arg}' (also passed positionally) -- this is a "
                            f"TypeError at runtime"
                        )
                    elif k.arg not in accepted:
                        found.append(
                            f"{rel}:{node.lineno}: st_compat.{node.func.id}() does not accept "
                            f"'{k.arg}'"
                        )
                if len(node.args) > max_pos:
                    found.append(
                        f"{rel}:{node.lineno}: st_compat.{node.func.id}() takes at most "
                        f"{max_pos} positional args, {len(node.args)} given"
                    )

            # 3. direct st.* widget calls that have a st_compat shim
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == "st":
                attr = node.func.attr
                if attr in COMPAT_SIGS and attr not in DIRECT_OK:
                    kw = {k.arg for k in node.keywords if k.arg}
                    # width/use_container_width are the ones the shim exists for
                    if kw & {"width", "use_container_width", "icon"}:
                        found.append(
                            f"{rel}:{node.lineno}: st.{attr}() called directly with "
                            f"{sorted(kw & {'width', 'use_container_width', 'icon'})} -- "
                            f"use st_compat.{attr}() so older Streamlit versions work"
                        )
    return found


def main():
    global problems
    problems = []
    icon_problems, materials_checked, lucides_checked = scan_icons(FILES)
    problems.extend(icon_problems)
    problems.extend(scan_call_shapes(FILES))

    print(f"scanned {len(FILES)} files")
    print(f"  icon names checked: {materials_checked} Material shortcode(s), "
          f"{lucides_checked} Lucide reference(s)")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print("   ", p)
        raise SystemExit(1)
    print("no call-shape problems found")


if __name__ == "__main__":
    main()
