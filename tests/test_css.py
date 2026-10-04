"""Validate GLOBAL_CSS: brace balance, empty rule bodies, and — the important
one — that every selector that claims to style a Streamlit widget actually
names an attribute the installed Streamlit really emits.

The role-switcher CSS was 86 lines of dead rules for exactly this reason: it
selected on a wrapper class the app no longer emitted. This check compares
every `[data-testid="..."]` and `[data-variant="..."]` selector in styles.py
against the strings found in the shipped frontend bundle, so a typo or a
selector for a test-id that does not exist is caught before deploy.

Run: .venv\\Scripts\\python.exe test_css.py
"""
import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


from styles import GLOBAL_CSS  # noqa: E402

print(f"GLOBAL_CSS: {len(GLOBAL_CSS)} bytes")

# ── 1. Structural sanity ──
section("1. CSS structure")
stripped = re.sub(r"/\*.*?\*/", "", GLOBAL_CSS, flags=re.S)
check("braces balance", stripped.count("{") == stripped.count("}"),
      f"{stripped.count('{')} open vs {stripped.count('}')} close")
check("braces are balanced at every prefix (never negative)",
      all(stripped.count("{", 0, k) - stripped.count("}", 0, k) >= 0
          for k in range(0, len(stripped), 500)))
check("no empty rule body", not re.search(r"\{\s*\}", stripped),
      re.findall(r"[^{}]+\{\s*\}", stripped)[:3])
check("no leftover .role-switch-container selector",
      "role-switch-container" not in stripped)
check("no emotion target: hash leaked into a selector",
      not re.search(r"eqzt73c\d+", stripped),
      set(re.findall(r"eqzt73c\d+", stripped)))

# A crude declaration check: every `prop: value` inside a block.
BADS = re.compile(r"^\s*[-a-zA-Z]+\s*:\s*[^;{}]*$")
bad_props = []
for m in re.finditer(r"\{([^{}]*)\}", stripped):
    for decl in m.group(1).split(";"):
        d = decl.strip()
        if not d:
            continue
        if ":" not in d:
            bad_props.append(d[:70])
check("every declaration has a property and a colon", not bad_props, bad_props[:5])

# ── 2. Selectors that name Streamlit's own attributes ──
section("2. Selectors vs. the real Streamlit frontend")
import streamlit  # noqa: E402

sroot = os.path.join(os.path.dirname(streamlit.__file__), "static", "static", "js")
bundle = []
for fn in os.listdir(sroot):
    if fn.endswith(".js"):
        try:
            with open(os.path.join(sroot, fn), encoding="utf-8", errors="ignore") as fh:
                bundle.append(fh.read())
        except OSError:
            pass
blob = "\n".join(bundle)
print(f"     frontend bundle: {len(bundle)} js file(s), {len(blob)} bytes")

# Every data-testid Streamlit can emit.
emitted_testids = set(re.findall(r'data-testid[":=\s]{1,6}`?"?(st[A-Za-z]+)', blob))
emitted_testids |= set(re.findall(r'"(st[A-Z][A-Za-z]*)"', blob))
# Every data-variant value used by widgets.
emitted_variants = set(re.findall(r"data-variant[=:][`'\"]{1,2}([a-z_]+)", blob))

print(f"     discovered {len(emitted_testids)} st* test-id(s), "
      f"{len(emitted_variants)} data-variant value(s)")

used_testids = set(re.findall(r'data-testid="([^"]+)"', stripped))
used_variants = set(re.findall(r'data-variant="([^"]+)"', stripped))

# The app's OWN test-ids (from key=) are not in the bundle; they are fine.
app_testids = set()
for dirpath, dirnames, filenames in os.walk(ROOT):
    # ".kilo" holds agent worktrees: a full but STALE copy of this same app
    # living inside the repository. Scanning it reported the removed login
    # badges as unstyled classes, because the copy predates their removal.
    dirnames[:] = [d for d in dirnames
                   if d not in ("tests", ".venv", "__pycache__", "backup",
                                "model", ".git", ".kilo")]
    for fn in filenames:
        if fn.endswith(".py") and not fn.startswith("_"):
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                    app_testids |= set(re.findall(r'key="(st[A-Za-z]+)"', fh.read()))
            except (OSError, UnicodeDecodeError):
                pass

unknown = sorted(t for t in used_testids
                 if t not in emitted_testids and t not in app_testids
                 and not re.search(r"(?<![A-Za-z0-9_$])" + re.escape(t)
                                   + r"(?![A-Za-z0-9_$])", blob))
check("every data-testid used in the CSS is a real one",
      not unknown, unknown)

unknown_variants = sorted(v for v in used_variants if v not in emitted_variants)
check("every data-variant used in the CSS is a real one",
      not unknown_variants, f"used={sorted(used_variants)} emitted={sorted(emitted_variants)}")

# ── 3. The role switcher specifically ──
section("3. The role switcher")
check("styles the segmented control container",
      re.search(r'\.stButtonGroup\b', stripped) is not None
      and 'data-testid="stWidgetLabel"' in stripped)
check("styles the segmented control items",
      'button[data-variant="segmented_control"]' in stripped)
check("styles the selected item",
      "[data-selected]" in stripped)
check("keeps a st.radio fallback for Streamlit < 1.40",
      'data-testid="stRadio"' in stripped)
check("the segmented control's own label is hidden",
      re.search(r'\.stButtonGroup \[data-testid="stWidgetLabel"\][^}]*display:\s*none',
                stripped) is not None)
check("forces white text onto the selected option's children",
      "[data-selected] *," in stripped)
check("hides the native radio input in the fallback",
      re.search(r'\[data-testid="stRadio"\](?::not\([^)]*\))? label input\s*\{[^}]*display:\s*none',
                stripped) is not None)
# Each state must be styled, or the toggle is invisible in that state.
check("an unselected hover state exists",
      'button[data-variant="segmented_control"]:not([data-selected]):hover' in stripped)
check("a selected state exists",
      'button[data-variant="segmented_control"][data-selected]' in stripped)

# ── 4. The other two classes the plan said are live ──
section("4. Classes the plan flagged as still live (must NOT be removed)")
for cls in ("chart-wrap", "logout-btn"):
    check(f"'.{cls}' is still present", f".{cls}" in stripped)

# ── 5. The sidebar navigation ─────────────────────────────────────────────
# The navigation is an st.radio, and the login page's portal switcher has a
# large block of st.radio CSS of its own. Those two blocks are the only
# things in the stylesheet that can target the same widget, and when they
# collided the nav rendered with a `border-radius: 999px` white pill and a
# drop shadow behind it (the "ugly transparent oval"), centred labels, and a
# `margin: .5rem auto 2.25rem auto` / `max-width: 420px` container — none of
# which the nav block ever asked for.
#
# These checks pin the two blocks apart. Section 5 is the load-bearing one:
# It fails the moment a bare `[data-testid="stRadio"]` selector comes back.
section("5. The sidebar navigation radio")
SIDEBAR_GUARD = ':not([data-testid="stSidebar"] [data-testid="stRadio"])'

st_radio_selectors = []
for m in re.finditer(r"([^{}]+)\{", stripped):
    for part in (s.strip() for s in m.group(1).split(",")):
        if "stRadio" in part:
            st_radio_selectors.append(part)

unscoped = [
    s for s in st_radio_selectors
    if '[data-testid="stSidebar"]' not in s
    and SIDEBAR_GUARD not in s
    and "stButtonGroup" not in s
]
check("no unscoped stRadio selector can reach the navigation", not unscoped,
      unscoped[:4])
check(f"the sidebar guard is actually used ({len(st_radio_selectors)} stRadio "
      f"selector(s))",
      sum(SIDEBAR_GUARD in s for s in st_radio_selectors) >= 10)

# The nav block must still style the label directly — a regression here
# made the whole navigation invisible.
check("the nav label is styled by the sidebar-scoped block",
      '[data-testid="stSidebar"] [data-testid="stRadio"] label' in stripped)
# The radiogroup selector is part of a comma-separated list, so we need to
# find the rule block that contains it and check for flex-direction within.
_radiogroup_rule = None
for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", stripped):
    if '[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]' in m.group(1):
        _radiogroup_rule = m.group(2)
        break
check("the nav group is a vertical flex column",
      _radiogroup_rule is not None and "flex-direction: column" in _radiogroup_rule,
      _radiogroup_rule[:80] if _radiogroup_rule else "rule not found")

# The nav's "current page" state and its radio circle are both styled against
# Streamlit's radio internals, which are unstyled emotion divs with hashed
# `target:` names. Those hashes are regenerated on every Streamlit build, so
# they cannot be written into the CSS — and if Streamlit ever restructures the
# radio, the rules below go quiet with no error anywhere. These checks read the
# installed bundle and assert the structure the CSS assumes is still there.
#
#   label[data-testid=stRadioOption] > span > input[type=radio]   (hidden input)
#   label[data-testid=stRadioOption] > div > div                 (the circle)
#   "data-selected"                                              (selection)

JS_DIR = ROOT + r"\.venv\Lib\site-packages\streamlit\static\static\js"
radio_src = ""
if os.path.isdir(JS_DIR):
    for name in sorted(os.listdir(JS_DIR)):
        if name.startswith("Radio.") and name.endswith(".js"):
            with open(os.path.join(JS_DIR, name), encoding="utf-8",
                      errors="replace") as fh:
                radio_src = fh.read()
            break
check("the installed Streamlit radio module was found to verify against",
      bool(radio_src), JS_DIR)

if radio_src:
    # The option label really does carry a selection attribute. Before this
    # check the CSS asked for `data-checked`, which appears nowhere in the
    # bundle — the selected-page styling was only ever firing by accident via
    # `:has(input:checked)`.
    check("Streamlit publishes radio selection as data-selected "
          "(not data-checked)",
          '"data-selected"' in radio_src and '"data-checked"' not in radio_src)

    # The real control is still a native <input type=radio>, wrapped in a
    # visually-hidden <span> that is the label's first child. Both matter: the
    # :has() fallback depends on the input, and the circle-hiding rule is
    # positional from the label's children, so a new wrapper before the row
    # would silently target the wrong element.
    check("each radio option still contains a native input[type=radio]",
          "inputProps" in radio_src and "type:`radio`" in radio_src)
    check("the hidden input is wrapped in a span, so it is not the "
          "row's first child",
          re.search(r"G\.createElement\(H,\{elementType:`span`\}", radio_src)
          is not None)

    # The circle is the row's first child: `div` (row) then `div` (ring) then
    # `div` (dot). If Streamlit stopped emitting that inner ring the rule
    # would hide the *text* instead, which is the failure mode worth guarding.
    check("the radio still renders a circle as the row's first child",
          re.search(r"borderRadius:`50%`,display:`flex`,alignItems:`center`,"
                    r"justifyContent:`center`", radio_src) is not None)

# And the CSS must actually express both behaviours.
_flat = re.sub(r"\s+", " ", stripped)

# The circle-hiding rule.
#
# Three versions of this rule have each broken the navigation visibly, and every
# one of them was written against a Streamlit DOM measured on the WRONG build.
# The app is run from `anaconda3\envs\futo-feedback` on Streamlit 1.61.1; these
# checks were being satisfied from `.venv` on 1.64.0. The two builds disagree
# about both the ring's position and the label wrapper's markup:
#
#   1.64.0  LABEL > DIV (row) > [ DIV (ring), DIV[stMarkdownContainer] > P ]
#   1.61.1  LABEL > DIV (row) > DIV (wrapper, NO data-testid)
#                                      > [ DIV (ring), DIV[stMarkdownContainer] > P ]
#
# Consequences, each of which shipped:
#   `> div > :first-child`      assumes the ring precedes the text. When it does
#                               not, it hides the label and the nav renders as
#                               empty boxes.
#   `> div > div:not([data-testid])`
#                               correct on 1.64.0. On 1.61.1 it matches the label
#                               WRAPPER, which carries no data-testid, and deletes
#                               the navigation text. Bisecting the whole
#                               stylesheet rule-by-rule showed this single rule
#                               takes the label paragraph from 22px to 0px.
#
# The rule now identifies the ring by what it is NOT — no test id, no text, no
# control — and is scoped to descendants of the row rather than its direct
# children, because the ring sits at a different depth on each build. `:has()`
# is therefore load-bearing, and that is accepted deliberately: a browser
# without it drops the list, leaving text and ring both visible, which is a
# plainer navigation rather than an invisible one.
check("the sidebar nav no longer hides the circle by DOM position",
      '[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > '
      ':first-child' not in _flat)
check("the ring-hiding rule spares anything carrying text or a control, which "
      "is what protects the label on 1.61.1",
      re.search(
          r'\[data-testid="stRadioOption"\] > div div:not\(\[data-testid\]\)'
          r':not\(:has\(p\)\):not\(:has\(input\)\)\s*\{[^}]*display:\s*none', _flat)
      is not None)
check("the ring-hiding rule reaches the ring at both depths, so it cannot be a "
      "direct-child selector again",
      re.search(r'\[data-testid="stRadioOption"\] > div div:not\(', _flat)
      is not None)
check("the nav hides the native radio input as well as the ring",
      re.search(r'\[data-testid="stSidebar"\] \[data-testid="stRadioOption"\]\s*'
                r'input\[type="radio"\]\s*\{[^}]*display:\s*none', _flat)
      is not None)
check("the option text is pinned visible, so an unexpected DOM degrades to an "
      "unstyled radio rather than an invisible one",
      re.search(r'\[data-testid="stRadioOption"\]\s*p,[^}]*\{[^}]*'
                r'visibility:\s*visible[^}]*opacity:\s*1', _flat) is not None)

# Alignment. The row is `flex-direction: column` on 1.61.1 and `row` on 1.64.0,
# so `align-items: center` on the row aligns the label VERTICALLY on one build
# and HORIZONTALLY on the other. On 1.61.1 that centred every nav item by its own
# text length — the reported "scattered" look, with the six labels starting at
# x = 66, 93, 104, 110, 118 and 128 instead of a common 45.
#
# The row must therefore say `flex-start`, and the option must keep `center` so
# its single row still sits vertically centred in the pill. Asserting both is the
# point: asserting only that *some* alignment is declared is what let the wrong
# one through three times.
check("the option keeps align-items:center so its row sits vertically centred "
      "in the pill",
      re.search(r'\[data-testid="stRadioOption"\]\s*\{[^}]*'
                r'align-items:\s*center', _flat) is not None)
check("the option ROW uses align-items:flex-start, not center — on 1.61.1 the "
      "row is a column, so center there aligns the label horizontally and "
      "centres every item by its own text length",
      re.search(r'\[data-testid="stRadioOption"\] > div\s*\{[^}]*'
                r'align-items:\s*flex-start', _flat) is not None)
check("no rule sets align-items:center on the option row", not re.search(
      r'\[data-testid="stRadioOption"\] > div\s*\{[^}]*align-items:\s*center',
      _flat))
check("nav options are pinned left-aligned, so items do not sit at differing x",
      re.search(r'\[data-testid="stRadioOption"\]\s*\{[^}]*'
                r'justify-content:\s*flex-start[^}]*text-align:\s*left', _flat)
      is not None)
# A label long enough to wrap makes its pill taller than the rest; that is the
# other half of the unevenness. nowrap keeps every pill one line, and ellipsis
# is the safety valve for a genuinely narrowed sidebar.
check("nav labels cannot wrap, so every pill keeps the same height",
      re.search(r'\[data-testid="stRadioOption"\]\s*p,[^}]*\{[^}]*'
                r'white-space:\s*nowrap[^}]*text-overflow:\s*ellipsis', _flat)
      is not None)
check("the nav row is given width so the text still fills the pill",
      re.search(r'\[data-testid="stSidebar"\] \[data-testid="stRadioOption"\] '
                r'> div\s*\{[^}]*flex:\s*1 1 auto', stripped) is not None)
check("the current page is marked with data-selected, not data-checked",
      'label[data-selected]' in stripped and "data-checked" not in stripped)

# ══════════════════════════════════════════════════════════════════════════
# 6. Motion, type and contrast
#
# These four checks exist because each of the defects they guard against
# shipped: an infinite `cardFloat` that silently cancelled the metric card's
# hover lift, six looping animations with no `prefers-reduced-motion` opt-out,
# a font scale whose smallest step was 0.56rem (~9px), and four semantic
# colours that were fill colours being reused as the `color:` of 11px badges.
# All four are invisible to the checks above and all four are visible to a user.
# ══════════════════════════════════════════════════════════════════════════
section("6. Motion tokens")

# Split off the reduced-motion block: it deliberately sets literal 1ms values,
# and the `transition-duration` inside it is not a transition to be tokenised.
_rm_at = stripped.find("@media (prefers-reduced-motion: reduce)")
check("a prefers-reduced-motion block exists", _rm_at != -1)
motion_css = stripped[:_rm_at] if _rm_at != -1 else stripped
reduced = stripped[_rm_at:] if _rm_at != -1 else ""

DURATIONS = re.compile(r"transition\s*:\s*([^;}]+)")
raw_durations = []
for m in DURATIONS.finditer(motion_css):
    for part in m.group(1).split(","):
        p = " ".join(part.split())
        # A duration is a number followed by s/ms and not part of a token.
        for tok in re.findall(r"\b\d*\.?\d+(?:ms|s)\b", p):
            raw_durations.append((tok, p[:60]))
check("no raw s/ms duration in any transition — all use --dur-*",
      not raw_durations, raw_durations[:6])

transition_all = re.findall(r"transition\s*:\s*all\b", motion_css)
check("no `transition: all` — properties are enumerated", not transition_all,
      f"{len(transition_all)} occurrence(s)")

for d in ("--dur-1", "--dur-2", "--dur-3", "--dur-4"):
    check(f"{d} is defined and actually used",
          f"{d}:" in stripped and f"var({d})" in motion_css)
for e in ("--ease-standard", "--ease-emphasis"):
    check(f"{e} is defined", f"{e}:" in stripped)
check("at least one rule uses --ease-emphasis",
      "var(--ease-emphasis)" in stripped)

# Every @keyframes-based animation that loops forever must be cancelled in the
# reduced-motion block, or named in an exemption list with a reason.
looping = set()
for m in re.finditer(r"animation\s*:\s*([^;}]*)\binfinite\b", motion_css):
    for part in m.group(1).split(","):
        name = part.strip().split()[0] if part.strip() else ""
        if name and not name.startswith("var"):
            looping.add(name)
# Selectors carrying an infinite animation must appear in the reduced-motion
# block, so this checks the selectors rather than guessing from keyframe names.
inf_selectors = []
for m in re.finditer(r"([^{}]+)\{([^{}]*animation[^{}]*infinite[^{}]*)\}",
                     motion_css):
    inf_selectors.append(" ".join(m.group(1).split())[:70])
uncancelled = [
    s for s in inf_selectors
    for sel in (" ".join(s.split()).split(","))
    if sel.strip() and sel.strip().split()[-1] not in reduced
]
check("every selector with an infinite animation is covered by the "
      "reduced-motion block",
      not uncancelled, uncancelled[:4])
check("reduced motion collapses transitions as well as animations",
      "transition-duration: 1ms" in reduced and "animation-duration: 1ms" in reduced)
check("reduced motion names the header and wordmark loops explicitly",
      ".page-header h1" in reduced and ".login-title-gradient" in reduced)

section("7. Type scale and readability")

tiny = []
for m in re.finditer(r"font-size\s*:\s*(0?\.\d+)rem\b", stripped):
    value = float(m.group(1))
    if value < 0.7:
        tiny.append(f"font-size: {m.group(1)}rem")
check("no font-size below the 0.7rem (11.2px) floor", not tiny, tiny[:5])

for t in ("--fs-2xs", "--fs-xs", "--fs-sm", "--fs-md",
          "--fs-lg", "--fs-xl", "--fs-2xl", "--fs-3xl"):
    check(f"{t} is defined", f"{t}:" in stripped)

px_sizes = re.findall(r"font-size\s*:\s*\d+px", stripped)
# 16px on inputs is deliberate: anything smaller makes iOS Safari zoom on focus.
non_input_px = [
    m.group(0) for m in re.finditer(r"[^{}]+\{[^}]*font-size\s*:\s*1[0-5]px", stripped)
]
check("no px font-size below 16px (iOS zoom floor)", not non_input_px,
      non_input_px[:3])

section("8. Contrast")


def _srgb(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(rgb):
    r, g, b = (_srgb(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _ratio(fg, bg=(255, 255, 255)):
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _resolve(value):
    """Follow a single `var(--token)` hop, so token colours can be checked."""
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", value.strip())
    if not m:
        return None
    tok = re.search(re.escape(m.group(1)) + r"\s*:\s*(#[0-9a-fA-F]{3,6})", stripped)
    return _hex_rgb(tok.group(1)) if tok else None


# Colours allowed to sit below 4.5:1 as text, each with the reason it is safe.
CONTRAST_EXEMPT = {
    "#ffffff": "white text on a saturated fill (buttons, selected options)",
    "#fff": "white text on a saturated fill (avatars)",
    "#dcfce7": "pale chip background, not text",
    "#f3e8ff": "pale chip background, not text",
    "#e5e7eb": "control border, not text",
    "#e6eaf1": "hairline border, not text",
    "#d7deea": "hairline border, not text",
    "#f8fafc": "surface tint, not text",
    "#f6f8fb": "page tint, not text",
    "#00d2ff": "gradient stop, not text",
    "#34d399": "gradient stop, not text",
    "#06b6d4": "fill/border only — the text-safe step is --cyan-text",
    "#10b981": "dot and glow fill — the text-safe step is --green-text",
    "#94a3b8": "--text-4, documented as decorative only",
    "#ea580c": "decorative accent, never used for text",
    "#3b82f6": "control fill — the text-safe step is --blue-text",
    "#8b5cf6": "slider fill only, never text",
    "#db2777": "decorative accent, never used for text",
}
bad_text = []
for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", motion_css):
    sel = " ".join(m.group(1).split())
    if sel.startswith("@") or not sel:
        continue
    for decl in m.group(2).split(";"):
        d = decl.strip()
        if not d.startswith("color:"):
            continue
        val = d.split(":", 1)[1].strip()
        rgb = _resolve(val)
        if rgb is None and re.fullmatch(r"#[0-9a-fA-F]{3,6}", val):
            rgb = _hex_rgb(val)
        if rgb is None:
            continue
        h = "#" + val.lstrip("#").lower() if val.startswith("#") else None
        if h and h in CONTRAST_EXEMPT:
            continue
        r = _ratio(rgb)
        if r < 4.5:
            bad_text.append((h or val, round(r, 2), sel[:52]))
check(f"every text colour clears WCAG AA 4.5:1 on white ({len(CONTRAST_EXEMPT)} "
      f"documented exemptions)", not bad_text, bad_text[:6])

for t, floor in (("--green-text", 4.5), ("--cyan-text", 4.5),
                 ("--gold-text", 4.5), ("--blue-text", 4.5)):
    m = re.search(re.escape(t) + r"\s*:\s*(#[0-9a-fA-F]{3,6})", stripped)
    ok = m is not None and _ratio(_hex_rgb(m.group(1))) >= floor
    check(f"{t} exists and clears {floor}:1",
          ok, m.group(1) if m else "undefined")

check("--text-4 is still documented as decorative-only",
      "decorative only" in GLOBAL_CSS)

section("9. Responsive coverage")

media_conds = re.findall(r"@media[^{]*?max-width:\s*(\d+)px", stripped)
check("the 1024 / 768 / 576 breakpoints are all present",
      {"1024", "768", "576"}.issubset(set(media_conds)),
      sorted(set(media_conds)))

# The large cards that used to keep desktop padding all the way down to 576px.
TABLET_CARDS = ["glass-card", "insight-card", "context-panel",
                "engine-status-card", "cat-card", "metric-card",
                "submission-result-card", "live-preview-card"]
tablet_blocks = re.findall(
    r"@media screen and \(max-width: 768px\)\s*\{(.*?)\n\}", motion_css, re.S)
tablet_all = "\n".join(tablet_blocks)
missing_tablet = [c for c in TABLET_CARDS if f".{c}" not in tablet_all]
check(f"all {len(TABLET_CARDS)} large cards have a tablet padding step",
      not missing_tablet, missing_tablet)

# And they must be reduced further at phone width, or 768px is the floor.
phone_blocks = re.findall(
    r"@media screen and \(max-width: 576px\)\s*\{(.*?)\n\}", motion_css, re.S)
check("the phone breakpoint still exists and is not empty",
      any(len(b.strip()) > 40 for b in phone_blocks))

check("gradient headings have an @supports fallback so they can never "
      "render invisible",
      "@supports not" in stripped and "background-clip: text" in reduced + motion_css)

section("10. Every class used in Python is actually styled")

# This check exists because it would have caught a real defect that shipped.
# `_render_audit_log` on User Management emitted seven `audit-log-*` classes
# and `.confirm-instruction` — a tinted icon, a bolded username, an actor and
# timestamp, an indented reason, a stat chip, and the two "type this exactly"
# prompts above the confirmation inputs. Not one of them existed in this file.
# The deletion trail rendered as an unstyled stack of block divs, and the
# single most important instruction on the page looked like a caption.
#
# Nothing caught it: every other check here is about CSS that exists, and a
# selector that is missing from a stylesheet cannot fail a test about the
# stylesheet. So this walks the Python in the other direction.

CSS_DEFINED = set(re.findall(r"\.([a-zA-Z][\w-]*)", GLOBAL_CSS))

# Classes that legitimately have no rule here.
#   * none yet — if one is added it must say why.
CSS_EXEMPT_CLASSES: dict[str, str] = {}

# `class="..."` inside a Python string literal. The leading `(?<![\w])` stops
# this matching `multi_class="auto"` in a comment, which is what a naive
# version of this check reported as an unstyled class on the first run.
CLASS_ATTR = re.compile(r"(?<![\w-])class\s*=\s*[\"']([a-zA-Z][a-zA-Z0-9 _-]*)[\"']")

SKIP_DIRS = {".venv", "__pycache__", "backup", ".git", "model", "tests", ".kilo"}
used: dict[str, list[str]] = {}
for path in sorted(Path(ROOT).rglob("*.py")):
    rel = path.relative_to(ROOT).as_posix()
    if any(part in SKIP_DIRS for part in path.parts):
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in CLASS_ATTR.finditer(text):
        for name in m.group(1).split():
            used.setdefault(name, []).append(rel)

unstyled = {c: sorted(set(f)) for c, f in used.items()
            if c not in CSS_DEFINED and c not in CSS_EXEMPT_CLASSES}
check(f"every class={len(used)} written into HTML has a CSS rule "
      f"({len(CSS_EXEMPT_CLASSES)} exempt)",
      not unstyled, unstyled)

# ══════════════════════════════════════════════════════════════════════════
# 11. Two defects that shipped and that only a real browser could see
#
# Both of these passed every check above and were still wrong on screen. They
# are here because "the CSS is syntactically fine" and "the CSS does the
# intended thing" are different claims, and for these two the suite was only
# ever testing the first one.
#
# 11a. `background` shorthand silently resets `background-clip`.
#      The page title is gradient text: a `linear-gradient` background clipped
#      to the glyphs with `-webkit-text-fill-color: transparent`. Inside the
#      `prefers-reduced-motion` block that gradient was re-declared with the
#      `background` SHORTHAND, which resets `background-clip` to its initial
#      value, `border-box`. The gradient stopped being clipped and painted as a
#      solid navy rectangle, with dark text on top of it — an unreadable box
#      where the page title should be, for exactly the users who had asked
#      their OS to stop large surfaces moving. Visible only with reduced motion
#      on, which is why it reached a screenshot instead of a test.
#
# 11b. Streamlit puts `width: fit-content` on the `stElementContainer` that
#      wraps a radio. Measured on the live sidebar: twelve element containers,
#      eleven 239px, the nav's 158px — the width of its longest label. Every
#      `width: 100%` in the nav block resolved against that, so the pills
#      hugged their text. Combined with the native `<input type="radio">` that
#      the circle-hiding rule never targeted (react-aria puts it in the label as
#      a sibling of the row, not inside the circle), the nav read as a stack of
#      empty boxes.
# ══════════════════════════════════════════════════════════════════════════
section("11. Gradient-text clipping and the nav's real width")

RULES = [((" ".join(m.group(1).split())), m.group(2))
         for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", stripped)]

GRADIENT_TEXT = (".page-header h1", ".login-title-gradient")
shorthand_bugs = []
for sel, body in RULES:
    if not any(g in sel for g in GRADIENT_TEXT):
        continue
    flat = " ".join(body.split())
    # Only rules that actually paint a gradient can be unclipped. The
    # `@supports not (...)` fallback deliberately says `background: none`,
    # which is safe precisely because there is nothing to clip.
    if "linear-gradient" not in flat:
        continue
    bg = re.search(r"(?:^|;)\s*background\s*:", flat)
    if not bg:
        continue                      # `background-image:` is a longhand; safe
    clip = re.search(r"(?:-webkit-)?background-clip:\s*text", flat)
    if not clip:
        shorthand_bugs.append((sel[:52], "`background` shorthand and no "
                                            "`background-clip: text` — the "
                                            "gradient paints as a solid box"))
    elif clip.start() < bg.start():
        shorthand_bugs.append((sel[:52], "`background-clip: text` declared "
                                        "BEFORE the shorthand, so the "
                                        "shorthand overrides it"))
check("no gradient-text rule uses the `background` shorthand in a way that "
      "unclips it", not shorthand_bugs, shorthand_bugs[:4])

check("`.page-header h1` still re-declares background-clip after its gradient",
      any(".page-header h1" in s and "-webkit-background-clip: text" in b
          for s, b in RULES))
check("the reduced-motion page title keeps a solid-colour fallback, so it can "
      "never render invisible",
      re.search(r"@supports not \(\(background-clip: text\)", stripped) is not None
      and "background: none" in reduced)

# (the nav's radio-input rule and its text-visibility guard are checked in
#  section 5, where the DOM-order regression they protect against lives)

# Scan EVERY rule that names the radiogroup, not just the first one. The
# selector appears in two places: the comma-group that sets width/display/
# flex-direction, and the dedicated gap rule. Taking only the first match here
# reported a false failure against the group block.
_radiogroup_bodies = [
    b for s, b in RULES
    if '[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]'
    in s
]
check("the sidebar radiogroup stretches its options so the pills fill the "
      "sidebar",
      any("align-items: stretch" in b for b in _radiogroup_bodies),
      f"{len(_radiogroup_bodies)} rule(s) name the radiogroup")
check("the nav's element container is forced to full width — Streamlit's own "
      "`width: fit-content` on a radio's wrapper beats any `width: 100%` "
      "below it",
      re.search(r'\[data-testid="stElementContainer"\]:has\([^)]*'
                r'\[data-testid="stRadio"\]\)\s*\{[^}]*width:\s*100%', stripped)
      is not None)
check("that override is written against the widget, not Streamlit's hashed "
      "emotion class",
      not re.search(r'st-emotion-cache-\w+[^}]*\{[^}]*width:\s*100%', stripped))

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f_ in failures:
        print(f"    - {f_}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED")
