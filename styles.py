"""
styles.py
---------
All global CSS lives here as one string, injected once from app.py.
Keeping it in its own module (instead of inline in app.py) makes the
1000+ lines of CSS easy to skim past when reading application logic.
"""

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    /* Light, professional palette. Variable names are kept as `--navy*`
       for backward compatibility with the rest of this stylesheet (a
       full rename would touch hundreds of lines for no visual benefit) —
       but every value below now points at a light-theme color. */
    --navy:        #f6f8fb;   /* page background — soft blue-gray, not pure white */
    --navy-mid:    #ffffff;   /* sidebar background */
    --navy-card:   #ffffff;   /* card background */
    --navy-card2:  #f8fafc;   /* nested/secondary card background */
    --navy-border: #e6eaf1;   /* hairline borders */
    --navy-border2:#d7deea;   /* slightly stronger borders (inputs, focus) */
    --accent:      #2563eb;
    --accent2:     #7c3aed;
    --cyan:        #0891b2;
    --gold:        #d97706;
    --green:       #059669;
    --red:         #dc2626;
    --orange:      #ea580c;
    --text-1:      #0f172a;   /* headings / primary text */
    --text-2:      #52607a;   /* body / secondary text */
    --text-3:      #64748b;   /* muted / secondary text — see note below */
    --text-4:      #94a3b8;   /* decorative only: scrollbar thumbs, dividers */
    --radius:      16px;
    --radius-sm:   10px;
    --radius-lg:   24px;
    --radius-xl:   32px;
    --shadow-sm:   0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06);
    --shadow-md:   0 4px 16px rgba(15,23,42,.06), 0 2px 6px rgba(15,23,42,.05);
    --shadow-lg:   0 12px 32px rgba(15,23,42,.08), 0 4px 12px rgba(15,23,42,.05);
    --glow-blue:   0 8px 28px rgba(37,99,235,.14);
    --glow-purple: 0 8px 28px rgba(124,58,237,.12);
    --glow-cyan:   0 8px 28px rgba(8,145,178,.10);

    /* ── MOTION ──
       Every duration and easing curve in this file used to be written out
       longhand (`.15s`, `.18s`, `.2s`, `.22s`, `.25s`, `.3s`, `.35s`, `.5s`,
       `.6s`, `.7s`, `2s`, `8s`; and `ease`, `ease-in-out`, `linear`, and three
       different spellings of the same cubic-bezier). Nothing coordinated, so
       the app's "feel" changed from card to card purely by which block a
       component happened to land in. These four durations and two curves are
       now the only values any rule is allowed to use:

         --dur-1  140ms — state flips that must feel instant (hover, focus)
         --dur-2  200ms — the default for anything on screen
         --dur-3  320ms — larger surfaces: cards lifting, panels entering
         --dur-4  620ms — deliberate, slow: progress bars, gradient sweeps

       --ease-standard  decelerating curve, for anything entering or moving
       --ease-emphasis   slight overshoot, reserved for "it responded to me" */
    --dur-1:   140ms;
    --dur-2:   200ms;
    --dur-3:   320ms;
    --dur-4:   620ms;
    --ease-standard: cubic-bezier(.4, 0, .2, 1);
    --ease-emphasis:  cubic-bezier(.34, 1.4, .64, 1);

    /* ── TYPE SCALE ──
       The stylesheet had more than twenty distinct `font-size` values, seven
       of them below 0.7rem — down to 0.56rem (≈9px), which is not legible on
       a phone. These eight steps replace them; nothing below --fs-xs. */
    --fs-2xs: 0.7rem;    /* 11.2px — uppercase eyebrow labels */
    --fs-xs:  0.75rem;   /* 12px   — badges, chips, captions */
    --fs-sm:  0.8125rem; /* 13px   — dense body, table cells, metadata */
    --fs-md:  0.875rem;  /* 14px   — default body */
    --fs-lg:  1rem;      /* 16px   — card titles */
    --fs-xl:  1.25rem;   /* 20px   — section headings */
    --fs-2xl: 1.75rem;   /* 28px   — page titles */
    --fs-3xl: 2.35rem;   /* 37.6px — hero wordmark */

    /* ── TEXT-SAFE SEMANTIC COLOURS ──
       `--green`, `--cyan`, `--gold` and `--blue` are fill colours: they were
       chosen to sit behind white text, as indicator dots, and to colour 2rem
       metric numerals. Every one of them is between 3.2:1 and 3.8:1 on white,
       which is fine for a 2rem number and fine as a background, and well
       under the 4.5:1 AA floor for text.

       They were being reused as the `color:` of 11px badges, chips and inline
       alert text, so "Pending", "Submitted", every success alert and the login
       demo heading all rendered below the floor.

       These four are the next step down the same ramp, for text only:
         --green-text  #047857  5.3:1     --cyan-text  #0e7490  4.8:1
         --gold-text   #b45309  5.0:1     --blue-text  #2563eb  5.2:1
       Nothing else changes: the bright values stay on backgrounds, borders,
       shadows and the big numerals, where they were always correct. */
    --green-text:  #047857;
    --cyan-text:   #0e7490;
    --gold-text:   #b45309;
    --blue-text:   #2563eb;
}

/* `--text-3` was `#94a3b8` on white — a 2.5:1 contrast ratio, below the 4.5:1
   WCAG AA floor for body text. It drove every caption, chart title, subtitle
   and metadata line in the app, so effectively all secondary text was too
   faint to read comfortably. `--text-3` is now `#64748b` (7.5:1); the old
   value survives as `--text-4` for purely decorative uses such as scrollbar
   thumbs and hairlines, where no text is being read.

   `--text-4` is now genuinely decorative-only. Two rules broke that contract
   and were moved to `--text-3`: the input placeholder, and the login footer.
   Both are text a person is actively trying to read, and both were sitting at
   roughly 2.5:1 against a white card. */

* { font-family: 'Sora', sans-serif !important; box-sizing: border-box; margin:0; padding:0; }
code, pre { font-family: 'JetBrains Mono', monospace !important; }

/* ═══════════════════════════
   DO NOT let the blanket rule above break Streamlit's OWN icon font.
   Streamlit renders its built-in icons (expander chevrons, and any
   icon=":material/..." passed to st.button/download_button/toast) as
   ligature text inside a span meant to use the "Material Symbols" font
   — the text content IS the icon name (e.g. "check_circle"), and the
   font substitutes it with a glyph. The blanket `* { font-family: Sora
   !important }` above defeats that substitution, so instead of a small
   icon you see the literal icon name as plain text. This restores the
   correct font on exactly those elements, nothing else.
   ═══════════════════════════ */
[data-testid="stIconMaterial"],
[data-testid="stExpanderIcon"],
[class*="material-symbols"],
[class*="material-icons"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}

html, body, [data-testid="stApp"] {
    background-color: var(--navy) !important;
    color: var(--text-1) !important;
}

/* ═══════════════════════════
   KEYBOARD FOCUS (U-09)

   This stylesheet contained no `:focus` rule at all, while containing a
   great many `:hover` rules. Hover styling changed the appearance of
   every button and card, but a keyboard user tabbing through got nothing:
   Streamlit's own ring is a faint browser outline that several of the
   custom button skins below visually cancel out, so focus was effectively
   invisible. Anyone driving the app from the keyboard — including an
   administrator doing the type-to-confirm deletion flow, which *requires*
   keyboard entry — had no way to tell which control was focused.

   `:focus-visible` rather than `:focus` so a mouse click does not leave a
   ring behind, and the ring is drawn with `outline` + `outline-offset` so
   it is never clipped by `overflow: hidden` on an ancestor.
   ═══════════════════════════ */
:where(a, button, input, select, textarea, summary, [role="button"],
       [role="radio"], [role="checkbox"], [role="tab"], [tabindex]):focus-visible {
    outline: 3px solid var(--accent) !important;
    outline-offset: 2px !important;
    border-radius: 6px;
}
/* Inputs get a tint as well as the ring, so focus stays obvious even if a
   custom skin overrides `outline` locally. */
input:focus-visible, textarea:focus-visible, select:focus-visible {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 4px rgba(37, 99, 235, .14) !important;
}
/* Never remove the ring without putting an equivalent one in place. */
:focus:not(:focus-visible) { outline: none !important; }

#MainMenu, footer { visibility: hidden; }
/* `[data-testid="stDecoration"] { display: none; }` used to live here. No
   element with that test-id exists in Streamlit 1.64 — the rule matched
   nothing, and Streamlit's header decoration is now hidden by the
   `stHeader` rules below instead. */
.block-container { padding: 1rem 2.5rem 1.5rem !important; max-width: 1440px !important; }

/* Tighten the gap between the role switcher and the content below it */
[data-testid="stVerticalBlock"] > div {
    gap: 0.75rem !important;
}

/* ═══════════════════════════
   LUCIDE ICONS (Inline SVG)
   Pure inline SVGs, zero network dependencies, 100% reliable rendering.
   ═══════════════════════════ */
.lc-ico {
    display: inline-block;
    vertical-align: -3px;
    flex-shrink: 0;
    overflow: visible;
}

/* ══════════════════════════════════════════════════════════════
   SIDEBAR COLLAPSE & EXPAND CONTROLS (Cohesive, perfectly matched)
   ══════════════════════════════════════════════════════════════ */

/* The two test-ids below used to be `collapsedControl` and
   `stSidebarCollapse`. Neither string exists anywhere in the installed
   Streamlit's frontend bundle, so all ~110 lines of rules for them matched
   nothing and the sidebar toggle rendered as Streamlit's bare default — the
   app's carefully matched blue-gradient chevron pair simply never applied.

   Verified against the bundle:
     collapsed  ->  data-testid="stExpandSidebarButton"   (IS the <button>)
     expanded   ->  data-testid="stSidebarCollapseButton"  (a wrapper div
                                                             AROUND the button)

   Note the asymmetry, which is why the selectors below differ: the collapsed
   button is the test-id element itself, so it is styled directly, while the
   expanded one is a container, so its inner button is targeted.

   The old `::before { content: "»" / "«" }` trick is dropped. Both buttons
   already render Streamlit's own
   `:material/keyboard_double_arrow_right:` / `:material/keyboard_double_arrow_left:`
   icon, and hiding that icon to draw a chevron in CSS was only ever a
   workaround for the icon failing to load. */

/* 1. Open button (sidebar collapsed) — the test-id IS the button */
[data-testid="stExpandSidebarButton"] {
    position: fixed !important;
    top: 14px !important;
    left: 16px !important;
    z-index: 999999 !important;
    background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
    border: 1px solid rgba(255,255,255,.25) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    width: 44px !important;
    height: 36px !important;
    min-width: 44px !important;
    min-height: 36px !important;
    padding: 0 !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 4px 14px rgba(37,99,235,.35) !important;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) var(--ease-standard) !important;
    overflow: hidden !important;
}

[data-testid="stExpandSidebarButton"]:hover {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    transform: scale(1.05) !important;
    box-shadow: 0 6px 20px rgba(37,99,235,.45) !important;
    border-color: rgba(255,255,255,.4) !important;
}

[data-testid="stExpandSidebarButton"]:active {
    transform: scale(0.96) !important;
}

[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] p,
[data-testid="stExpandSidebarButton"] span {
    color: #ffffff !important;
    font-size: 1.2rem !important;
    line-height: 1 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,.2) !important;
}

/* 2. Close button (sidebar open) — the test-id WRAPS the button */
[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    align-items: center !important;
}

[data-testid="stSidebarCollapseButton"] button {
    background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
    border: 1px solid rgba(255,255,255,.25) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    width: 44px !important;
    height: 36px !important;
    min-width: 44px !important;
    min-height: 36px !important;
    padding: 0 !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 4px 14px rgba(37,99,235,.35) !important;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) var(--ease-standard) !important;
    overflow: hidden !important;
}

[data-testid="stSidebarCollapseButton"] button:hover {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    transform: scale(1.05) !important;
    box-shadow: 0 6px 20px rgba(37,99,235,.45) !important;
    border-color: rgba(255,255,255,.4) !important;
}

[data-testid="stSidebarCollapseButton"] button:active {
    transform: scale(0.96) !important;
}

[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] button p,
[data-testid="stSidebarCollapseButton"] button span {
    color: #ffffff !important;
    font-size: 1.2rem !important;
    line-height: 1 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,.2) !important;
}

[data-testid="stSidebar"] {
    background: var(--navy-mid) !important;
    border-right: 1px solid var(--navy-border) !important;
}
[data-testid="stSidebar"] * { color: var(--text-1) !important; }

.sidebar-profile {
    background: linear-gradient(135deg,rgba(59,130,246,.1),rgba(139,92,246,.08));
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius);
    padding: 1.3rem 1.1rem;
    margin-bottom: 1.4rem;
    position: relative;
    overflow: hidden;
}
.sidebar-profile::before {
    content:'';
    position:absolute; top:-30px; right:-30px;
    width:100px; height:100px; border-radius:50%;
    background: radial-gradient(circle, rgba(59,130,246,.15), transparent 70%);
}
.sidebar-avatar {
    width: 50px; height: 50px; border-radius: 14px;
    background: linear-gradient(135deg, #1d4ed8, #7c3aed);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.25rem; font-weight: 800; color: #fff;
    margin-bottom: .7rem;
    box-shadow: 0 4px 16px rgba(59,130,246,.35);
}
.sidebar-name  { font-size: .95rem; font-weight: 700; color: var(--text-1); }
.sidebar-role  {
    font-size: var(--fs-2xs); font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: var(--accent); margin-top: 3px;
}
.sidebar-label {
    font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .14em;
    color: var(--text-3); font-weight: 700; margin: 1.1rem 0 .5rem;
    padding-left: .2rem;
}

/* Administrator-only deployment health (admin sidebar).

   Both colours clear 4.5:1 against the sidebar AND against their own tint, which
   was measured rather than eyeballed: --green-text is 5.5:1 on white and 5.0:1 on
   its .07 tint; #b91c1c is 6.5:1 on white and 5.7:1 on its .08 tint. The <code>
   chip inherits the parent's colour, so it lands on the same 5.7:1. */
.health-ok,
.health-bad {
    font-size: var(--fs-2xs);
    line-height: 1.5;
    padding: .45rem .55rem;
    border-radius: var(--radius-sm);
    margin-top: .25rem;
}
.health-ok {
    background: rgba(4, 120, 87, 0.07);
    border: 1px solid rgba(4, 120, 87, 0.22);
    color: #047857;
    font-weight: 600;
}
.health-bad {
    background: rgba(220, 38, 38, 0.08);
    border: 1px solid rgba(220, 38, 38, 0.25);
    color: #b91c1c;
    font-weight: 600;
}
.health-bad code {
    background: rgba(220, 38, 38, 0.10);
    border-radius: 4px;
    padding: 0 .25rem;
    color: inherit;
    font-size: inherit;
}

.sidebar-engine-badge {
    margin-top: 0.9rem;
    padding: 0.75rem 0.95rem;
    background: linear-gradient(135deg, rgba(37,99,235,.06), rgba(124,58,237,.05));
    border: 1px solid rgba(37,99,235,.18);
    border-radius: 12px;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) ease;
}
.sidebar-engine-badge:hover {
    border-color: rgba(37,99,235,.35);
    background: linear-gradient(135deg, rgba(37,99,235,.1), rgba(124,58,237,.08));
    box-shadow: 0 4px 14px rgba(37,99,235,.08);
}

/* ── The badge's two rows ──────────────────────────────────────────────────
   A single flex row with `justify-content: space-between` put the pill hard
   against the right edge of a 240px sidebar, so the engine name wrapped onto
   a second line and the pill sat beside the gap. The rows are laid out
   separately now, and the name is allowed to shrink rather than push the pill
   out of the box.

   `min-width: 0` on the name is load-bearing: without it a flex item refuses
   to shrink below its content width, so the row overflows instead of wrapping
   cleanly however much room the other element is given. */
.engine-badge-head {
    display: flex;
    align-items: center;
    gap: .5rem;
}

.engine-badge-name {
    font-weight: 700;
    font-size: .72rem;
    color: var(--text-1);
    letter-spacing: .01em;
    /* Shrinkable, so a long value truncates with an ellipsis rather than
       displacing the tag. */
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.engine-badge-tag {
    margin-left: auto;
    flex-shrink: 0;
    font-size: .7rem;
    font-weight: 700;
    padding: .12rem .45rem;
    border-radius: 999px;
    background: rgba(37, 99, 235, .08);
    color: #2563eb;
    border: 1px solid rgba(37, 99, 235, .2);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}

.engine-badge-bands {
    font-size: .7rem;
    color: var(--text-3);
    margin-top: .4rem;
    line-height: 1.5;
}
.engine-indicator-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
    display: inline-block;
    flex-shrink: 0;
    animation: engine-pulse-anim 2s infinite ease-in-out;
}
@keyframes engine-pulse-anim {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: .65; transform: scale(0.85); }
}

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR NAVIGATION

   Streamlit 1.64 renders `st.radio` like this — read out of the installed
   frontend bundle (`static/js/Radio.*.js`), not assumed:

     div.stRadio[data-testid=stRadio]
       div[data-testid=stWidgetLabel]              <- "Navigation", hidden below
       div[role=radiogroup][data-testid=stRadioGroup]
         div.react-aria-RadioField[data-selected]  <- one per option
           label[data-testid=stRadioOption][data-selected]
             span                                 <- visually-hidden wrapper
               input[type=radio][checked]         <- the real control
             div                                  <- row: flex, gap
               div > div                          <- circle, then the dot
               <option text>

   Two things follow from that, and both were wrong before.

   1. The circle is `label > div(row) > :first-child`. There is no class and no
      test-id on it — it is two emotion-styled divs whose hashed target names
      change on every Streamlit build, which is why nothing could be written
      against them directly. Hiding the row's first child is positional but it
      is the only hook that is stable, and the consequence of Streamlit ever
      reordering those two children is a circle reappearing, not a broken
      layout. This is the "remove the radio circle, show text only" request.

   2. Selection is published as `data-selected` (on both the wrapper div and
      the label), not `data-checked`. A previous pass here guessed
      `data-checked`, which matches nothing; the rule below relied entirely on
      `:has(input:checked)` underneath it and only ever worked by accident.
      Both are now listed, because the input is real and `checked` is a
      genuine property of it — belt and braces against a Streamlit upgrade
      that drops one of the two.
   ══════════════════════════════════════════════════════════════════════════ */

/* Hiding the radio circle.

   This rule has broken the navigation three separate ways, and every version was
   written against a Streamlit DOM measured on the wrong build. The app is run
   from an anaconda environment on Streamlit 1.61.1; the checks here were being
   run from `.venv` on 1.64.0. The two builds do not agree:

     1.64.0   LABEL > SPAN > INPUT
                    DIV (row)
                      DIV                            ring, no data-testid
                      DIV[data-testid=stMarkdownContainer] > P   label

     1.61.1   LABEL > SPAN > INPUT
                    DIV (row)
                      DIV                            wrapper: NO data-testid, and
                        ├── DIV                      holds BOTH the ring and the
                        │   └── DIV                    label below it
                        └── DIV[data-testid=stMarkdownContainer] > P

   So `div:not([data-testid])` — correct on 1.64.0 — matches the label wrapper on
   1.61.1 and deletes the navigation text. Measured there: every option 239x43
   with an empty `<p>`, `getClientRects().length === 0`, `offsetParent === null`,
   `innerText === ""`. Rule-by-rule bisection of the whole stylesheet confirmed
   that one rule alone takes the paragraph from 22px to 0px.

   Note the ring sits at a different depth on each build — a direct child of the
   row on 1.64.0, a grandchild on 1.61.1 — so a `> div > *` selector cannot reach
   both. This is written as a descendant of the row instead, and identifies the
   ring by what it is NOT: it holds no text, no control and no test id. That
   excludes the row and the wrapper (both contain a `<p>`) and the markdown
   container (marked), leaving only the decorative boxes.

   `:has()` is load-bearing, and that is a real constraint rather than a stylistic
   one. A browser without it drops this entire selector list, which leaves the
   text visible and the ring visible: a plainer navigation, but a usable one. The
   alternative failure, the one that shipped, was an invisible navigation. */
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div
    div:not([data-testid]):not(:has(p)):not(:has(input)) {
    display: none !important;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"] input[type="radio"] {
    display: none !important;
}

/* Pin the option left-aligned and evenly filled.

   `align-items` differs between the two elements on purpose, because the row's
   main axis differs between builds. Measured on 1.61.1:

       option  LABEL  display:flex  direction:row     align-items:center
       row      DIV    display:flex  direction:COLUMN  align-items:center

   With the row in a column, `align-items: center` acts on the HORIZONTAL axis,
   so each label is centred by its own text length — the "scattered" appearance,
   with the six labels starting at x = 66, 93, 104, 110, 118 and 128. On 1.64.0
   the row is `direction: row`, where the same declaration acts on the vertical
   axis and is exactly right. One stylesheet, two layouts, opposite outcomes.

   So: the option keeps `center` to sit its single row vertically in the pill,
   and the row gets `flex-start` to keep its content hard against the left edge
   on either axis. Both are stated explicitly rather than inherited, so the
   alignment does not depend on which rule happens to win the cascade. */
[data-testid="stSidebar"] [data-testid="stRadioOption"] {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: left !important;
    flex: 1 1 auto;
    min-width: 0;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div {
    align-items: flex-start !important;
    justify-content: flex-start !important;
    text-align: left !important;
}

/* Last line of defence for the option text. If a future Streamlit nests the
   label somewhere this stylesheet does not expect, the failure should be an
   unstyled radio rather than an invisible one.

   `nowrap` keeps every pill the same height: "Lecturer Teaching Style" is the
   longest label, and in a narrowed sidebar it was the one item that wrapped to
   two lines, which is the other half of the unevenness. `ellipsis` is the
   safety valve for a genuinely squeezed sidebar — at normal widths nothing is
   truncated. */
[data-testid="stSidebar"] [data-testid="stRadioOption"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"]
    [data-testid="stMarkdownContainer"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: var(--text-2) !important;
    font-size: inherit;
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
}
/* With the circle gone the row has nothing giving it width, so the label
   would collapse to the width of its text instead of filling the pill.
   `margin: 0` on the same two children because the option label is rendered
   through the markdown component and arrives as a <p> with a default
   1em bottom margin, which pushed the row's contents off-centre. */
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div {
    flex: 1 1 auto !important;
    min-width: 0;
    /* `flex-start`, not `center`. This row is a COLUMN on Streamlit 1.61.1 and a
       ROW on 1.64.0, so `center` aligns the label vertically on one build and
       horizontally on the other — and on 1.61.1 that is what centred every nav
       item by its own text length. `flex-start` pins the content to the leading
       edge on either axis, and since the row is exactly one line tall there is
       no vertical slack for it to give up. */
    align-items: flex-start !important;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > * {
    margin: 0 !important;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: var(--navy-card2) !important;
    border: 1px solid var(--navy-border) !important;
    border-radius: var(--radius-sm) !important;
    padding: .55rem .85rem !important;
    min-height: 2.7rem;
    display: flex !important;
    align-items: center !important;
    line-height: 1.25 !important;
    font-size: .88rem !important;
    color: var(--text-2) !important;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-1) ease !important;
    cursor: pointer !important;
    box-shadow: 0 1px 2px rgba(15,23,42,.03) !important;
    /* Equal-width nav buttons in sidebar */
    width: 100% !important;
    box-sizing: border-box !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: rgba(59,130,246,.1) !important;
    color: var(--text-1) !important;
    border-color: rgba(59,130,246,.25) !important;
    transform: translateX(2px);
    box-shadow: 0 2px 6px rgba(59,130,246,.12) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:active {
    transform: translateX(2px) scale(.98);
}
/* `data-selected` is what Streamlit actually sets (verified above);
   `:has(input:checked)` covers the same state through the hidden input.

   The accent left edge is deliberate: it is the only high-contrast signal for
   "this is the page you are on". The background tint is a ~4% alpha shift on a
   near-white card, which does not survive a glare-heavy laptop screen or a
   phone in daylight. */
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-selected],
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(59,130,246,.16), rgba(139,92,246,.1)) !important;
    border-color: rgba(59,130,246,.35) !important;
    border-left: 3px solid var(--accent) !important;
    padding-left: calc(.85rem - 2px) !important;
    color: var(--text-1) !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(59,130,246,.1) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"],
[data-testid="stSidebar"] [data-testid="stRadio"] > div,
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"],
[data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stWidgetLabel"] + div {
    width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}
/* The 5px between nav buttons. Streamlit's vertical radio group ships
   `gap: none` (it only gaps horizontal groups, and only when captions are
   present), so without this the options are flush with each other and the
   individual pill borders read as one box.

   `align-items: stretch` is the load-bearing half. Streamlit's own radiogroup
   style is `align-items: center` when horizontal and `flex-start` when
   vertical, and the block above overrides its `flex-direction` to column
   without touching `align-items`. In a column flex container that means every
   option is sized to its own content instead of the full width, so the
   `width: 100%` on the label resolves against a content-sized parent and does
   nothing. Measured widths before this fix were 96 / 135 / 152 / 158px — each
   one exactly as wide as its own label text — which is what turned a nav
   button into a small box once the text stopped contributing width. Stretching
   lets each pill fill the sidebar. Scoped to the sidebar, and the sidebar nav
   is always vertical, so the horizontal groups are unaffected. */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
    gap: 5px !important;
    align-items: stretch !important;
}

/* The rule above is necessary and not sufficient, and the reason is worth
   writing down because it cost the most time to find.

   Streamlit ships an emotion class — observed on this build as
   `.st-emotion-cache-zh2fnc`, but the hash changes on every release and is not
   something to write a selector against — that applies `width: fit-content` to
   the `stElementContainer` wrapping a radio widget. In a page column that is
   correct: a bare `st.radio` should hug its options. In the sidebar it makes
   the whole nav as wide as its longest label, and every `width: 100%` below it
   then resolves against that instead of the sidebar.

   Measured on the signed-in admin sidebar, twelve `stElementContainer`s:
   eleven at 239px (the sidebar's inner width) and the nav's at 158px — exactly
   the width of "User Management". An explicit `width` beats the parent's
   `align-items: stretch`, so nothing above this could win it back.

   `:has()` rather than the hashed class, so this survives a Streamlit upgrade.
   The file already depends on `:has()` further up (the `input:checked` fallback
   on the selected-state rule), so this adds no new browser requirement. */
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"]) {
    width: 100% !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stWidgetLabel"] {
    display: none !important;
}

/* Horizontal radios, i.e. the ones OUTSIDE the sidebar.
   The `:not()` guard is not decoration: the sidebar's navigation is also a
   `[role="radiogroup"]`, and without it this rule was setting the nav's
   `flex-direction: row` and `gap: 0.75rem` as well — it only lost to the
   nav block above on specificity, which is exactly the kind of accidental
   win that stops being accidental the moment someone edits either rule. */
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 0.75rem !important;
}

/* ═══════════════════════════
   BUTTONS
   Two layers of defense against Streamlit swallowing our text color:

   1. PRIMARY DEFENSE (in the Python code, not here): every button meant
      to look like a bold call-to-action is created with `type="primary"`.
      Streamlit's own internal styling always pairs primary-kind buttons
      with white label text by convention — leaning on that built-in
      pairing sidesteps a real problem we hit earlier, where our own
      `color: #fff !important` on the button lost to Streamlit's OWN
      more specific / later-in-the-cascade rule on the *inner* label
      element, no matter how many `!important`s we stacked on top of it.
      We only override `background` here (to swap Streamlit's flat
      primary-color fill for our gradient) — never `color` — for exactly
      that reason.

   2. BACKUP (below): still forces white text explicitly, in case a
      button somewhere doesn't get `type="primary"`, using explicit
      element-type selectors (p/div/span/label), not just a universal
      `*`, since a bare `*` has zero CSS specificity and can still lose
      to a more specific built-in Streamlit rule.

   Selectors cover both older (class-based) and newer (data-testid-based)
   internal Streamlit markup, since relying on just one style is fragile
   across versions.
   ═══════════════════════════ */
.stButton > button, .stButton > button p, .stButton > button div,
.stButton > button span, .stButton > button label, .stButton > button *,
.stFormSubmitButton > button, .stFormSubmitButton > button p, .stFormSubmitButton > button div,
.stFormSubmitButton > button span, .stFormSubmitButton > button label, .stFormSubmitButton > button *,
.stDownloadButton > button, .stDownloadButton > button p, .stDownloadButton > button div,
.stDownloadButton > button span, .stDownloadButton > button label, .stDownloadButton > button *,
[data-testid^="stBaseButton"], [data-testid^="stBaseButton"] p, [data-testid^="stBaseButton"] div,
[data-testid^="stBaseButton"] span, [data-testid^="stBaseButton"] label, [data-testid^="stBaseButton"] * {
    color: #ffffff !important;
}
.stButton > button,
.stFormSubmitButton > button,
.stDownloadButton > button,
[data-testid^="stBaseButton"] {
    background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: .7rem 1.8rem !important;
    font-weight: 700 !important; font-size: .92rem !important;
    box-shadow: 0 4px 24px rgba(59,130,246,.3) !important;
    /* These two were the only declarations in the rule without `!important`.
       Streamlit sets both on its own button and wins on source order, so the
       full-width intent silently did not apply and buttons came out
       shrink-to-fit against the card's padding. */
    width: 100% !important;
    min-height: 2.9rem !important;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-1) var(--ease-emphasis) !important;
    letter-spacing: .01em;
}
.stButton > button:hover, .stFormSubmitButton > button:hover,
.stDownloadButton > button:hover, [data-testid^="stBaseButton"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(59,130,246,.45) !important;
}
.stButton > button:active, .stFormSubmitButton > button:active,
.stDownloadButton > button:active, [data-testid^="stBaseButton"]:active {
    transform: translateY(0) !important;
}

.logout-btn .stButton > button, .logout-btn .stButton > button p,
.logout-btn .stButton > button div, .logout-btn .stButton > button span,
.logout-btn .stButton > button *,
.logout-btn [data-testid^="stBaseButton"], .logout-btn [data-testid^="stBaseButton"] p,
.logout-btn [data-testid^="stBaseButton"] div, .logout-btn [data-testid^="stBaseButton"] span,
.logout-btn [data-testid^="stBaseButton"] * {
    color: #dc2626 !important;
}
.logout-btn .stButton > button, .logout-btn [data-testid^="stBaseButton"] {
    background: rgba(239,68,68,.1) !important;
    border: 1px solid rgba(239,68,68,.25) !important;
    box-shadow: none !important;
}
.logout-btn .stButton > button:hover, .logout-btn [data-testid^="stBaseButton"]:hover {
    background: rgba(239,68,68,.18) !important;
    border-color: rgba(239,68,68,.4) !important;
    box-shadow: 0 4px 16px rgba(239,68,68,.15) !important;
}

/* Placeholder text in inputs was too faint to read — give it clear,
   deliberate contrast instead of relying on the browser default.

   This used to be `#94a3b8`, the value this file documents as `--text-4`,
   "decorative only: scrollbar thumbs, dividers". A placeholder is not
   decorative — it is the only description of the field you have while the
   field is empty, and it is what people read to know what to type. `#94a3b8`
   on white is roughly 2.5:1, well under the 4.5:1 WCAG AA floor for text.
   `--text-3` (`#64748b`) is 7.5:1 and is what every other secondary string in
   the app already uses. `opacity: 1` matters too: Firefox dims placeholders
   with opacity on top of the colour, which would have halved the result. */
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: var(--text-3) !important;
    opacity: 1 !important;
}

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: var(--navy-card) !important;
    border: 1px solid var(--navy-border2) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-1) !important;
    font-size: .9rem !important;
    transition: border-color var(--dur-2), box-shadow var(--dur-2) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,.15), 0 4px 16px rgba(59,130,246,.1) !important;
    outline: none !important;
}

/* The password show/hide "eye" toggle is a native Streamlit button
   rendered inside the input. Left unstyled it defaults to a dark
   square that clashes with this light theme. Give it a matching light
   background, and make sure it fully occludes anything behind it
   (some browsers draw their own password-manager icon in the same
   corner, which can visually collide with this button otherwise).

   NOTE: `[data-testid="InputInstructions"]` was previously caught by this
   rule. That element is Streamlit's "Press Enter to submit form" hint —
   a small text label, not a button. Giving it an opaque background and
   `z-index: 2` painted a white box over the input text, making it
   impossible to see what you were typing. It is now styled separately
   below. */
[data-testid="stTextInput"] button[title*="password" i],
[data-testid="stTextInput"] div[data-baseweb="input"] button {
    background: var(--navy-card2) !important;
    border-left: 1px solid var(--navy-border2) !important;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0 !important;
    position: relative;
    z-index: 2;
}

/* Streamlit's "Press Enter to submit form" hint. Rendered inside the
   input container; without this rule it inherits no styling and can
   overlap the text being typed. Make it a small, unobtrusive label. */
[data-testid="InputInstructions"] {
    font-size: .75rem !important;
    color: var(--text-3) !important;
    background: transparent !important;
    border: none !important;
    padding: .15rem 0 !important;
    margin: 0 !important;
    position: static !important;
    z-index: auto !important;
    pointer-events: none !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"] button svg {
    fill: var(--text-2) !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"] {
    background: var(--navy-card) !important;
}

[data-baseweb="select"] > div {
    background: var(--navy-card) !important;
    border: 1px solid var(--navy-border2) !important;
    border-radius: var(--radius-sm) !important;
}
[data-baseweb="select"] * { color: var(--text-1) !important; }
[data-baseweb="popover"] > div {
    background: var(--navy-card2) !important;
    border: 1px solid var(--navy-border2) !important;
    border-radius: var(--radius-sm) !important;
}
[data-baseweb="menu"] { background: var(--navy-card2) !important; }

[data-testid="stSlider"] p,
[data-testid="stSlider"] > div > div > div { color: var(--text-2) !important; font-size: .85rem !important; }
[data-testid="stSlider"] [data-baseweb="slider"] { padding-top: 6px !important; padding-bottom: 6px !important; }
[data-testid="stSlider"] [data-baseweb="slider"] > div:nth-child(1) {
    height: 4px !important; background: var(--navy-border2) !important;
    border-radius: 999px !important; top: 50% !important; transform: translateY(-50%) !important;
    box-shadow: none !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] > div:nth-child(2) {
    height: 4px !important;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6) !important;
    border-radius: 999px !important; top: 50% !important; transform: translateY(-50%) !important;
    box-shadow: 0 0 8px rgba(59,130,246,.35) !important;
}
[data-testid="stSlider"] [role="slider"] {
    width: 18px !important; height: 18px !important; border-radius: 50% !important;
    background: #ffffff !important; border: 3px solid #3b82f6 !important;
    box-shadow: 0 2px 8px rgba(59,130,246,.45), 0 0 0 4px rgba(59,130,246,.1) !important;
    top: 50% !important; transform: translateY(-50%) !important;
    transition: box-shadow var(--dur-1) ease, border-color var(--dur-1) ease !important; cursor: grab !important;
}
[data-testid="stSlider"] [role="slider"]:hover {
    border-color: #8b5cf6 !important;
    box-shadow: 0 2px 12px rgba(139,92,246,.55), 0 0 0 6px rgba(139,92,246,.12) !important;
}
[data-testid="stSlider"] [role="slider"]:active {
    cursor: grabbing !important; border-color: #06b6d4 !important;
    box-shadow: 0 2px 14px rgba(6,182,212,.5), 0 0 0 6px rgba(6,182,212,.12) !important;
}
[data-testid="stSlider"] [role="slider"] + div,
[data-testid="stSlider"] [data-baseweb="tooltip"] {
    background: var(--navy-card2) !important; border: 1px solid var(--navy-border2) !important;
    border-radius: 8px !important; color: var(--text-1) !important;
    font-size: .78rem !important; font-weight: 700 !important;
    padding: .2rem .55rem !important; box-shadow: var(--shadow-md) !important;
}

[data-testid="stCheckbox"] label { color: var(--text-2) !important; font-size: .88rem !important; }
[data-testid="stCheckbox"] label:hover { color: var(--text-1) !important; }

.page-header {
    background: linear-gradient(135deg, rgba(59,130,246,.1) 0%, rgba(139,92,246,.07) 50%, rgba(6,182,212,.05) 100%);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius-xl);
    padding: 2.5rem 3rem;
    margin-bottom: 2.5rem;
    position: relative; overflow: hidden;
    backdrop-filter: blur(12px);
}
.page-header::before {
    content: ''; position: absolute; top: -80px; right: -80px;
    width: 280px; height: 280px; border-radius: 50%;
    background: radial-gradient(circle, rgba(59,130,246,.12), transparent 65%);
}
.page-header::after {
    content: ''; position: absolute; bottom: -60px; left: 25%;
    width: 200px; height: 200px; border-radius: 50%;
    background: radial-gradient(circle, rgba(139,92,246,.08), transparent 65%);
}
.page-header-top { display: flex; align-items: center; gap: 1.2rem; margin-bottom: 1rem; position: relative; z-index: 1; }
.page-header-badge {
    display: inline-flex; align-items: center; gap: .4rem;
    background: rgba(59,130,246,.12); border: 1px solid rgba(59,130,246,.25);
    border-radius: 999px; padding: .28rem .8rem;
    font-size: var(--fs-2xs); font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #2563eb; margin-bottom: .8rem;
}
.page-header-icon-wrap {
    width: 60px; height: 60px;
    background: linear-gradient(135deg, rgba(59,130,246,.2), rgba(139,92,246,.15));
    border: 1px solid rgba(59,130,246,.3); border-radius: 18px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; box-shadow: 0 8px 24px rgba(59,130,246,.2);
}
.page-header h1 {
    font-size: 2rem; font-weight: 800; color: var(--text-1); margin: 0; letter-spacing: -.02em;
    background: linear-gradient(135deg, #0f172a 40%, #2563eb);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    position: relative; z-index: 1;
}
.page-header p { font-size: .9rem; color: var(--text-2); margin: .4rem 0 0; position: relative; z-index: 1; max-width: 600px; }

.metric-card {
    background: var(--navy-card); border: 1px solid var(--navy-border);
    border-radius: var(--radius); padding: 1.6rem 1.4rem; text-align: center;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-3) ease; margin-bottom: 1rem; position: relative; overflow: hidden;
}
.metric-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(59,130,246,.4), transparent);
    opacity: 0; transition: opacity var(--dur-3);
}
.metric-card::after {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(59,130,246,.06), transparent 70%);
    opacity: 0; transition: opacity var(--dur-3);
}
.metric-card:hover {
    border-color: rgba(59,130,246,.4); transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(59,130,246,.15), 0 0 0 1px rgba(59,130,246,.1);
}
.metric-card:hover::before, .metric-card:hover::after { opacity: 1; }
.metric-icon-wrap { display:flex; align-items:center; justify-content:center; min-height:44px; margin-bottom:.6rem; }
.metric-value { font-size: 2.1rem; font-weight: 800; color: var(--text-1); line-height: 1; }
.metric-label {
    font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .12em;
    color: var(--text-3); margin-top: .5rem; font-weight: 600;
}
.metric-accent-blue   .metric-value { color: #2563eb; }
.metric-accent-green  .metric-value { color: var(--green-text); }
.metric-accent-gold   .metric-value { color: var(--gold-text); }
.metric-accent-purple .metric-value { color: #7c3aed; }
.metric-accent-cyan   .metric-value { color: var(--cyan-text); }

.section-header { display: flex; align-items: center; gap: .9rem; margin-bottom: 1.5rem; margin-top: .5rem; }
.section-header-line { flex: 1; height: 1px; background: linear-gradient(90deg, var(--navy-border2), transparent); }
.section-header-pill {
    display: inline-flex; align-items: center; gap: .45rem;
    background: rgba(59,130,246,.08); border: 1px solid rgba(59,130,246,.2);
    border-radius: 999px; padding: .3rem .9rem;
    font-size: var(--fs-2xs); font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #2563eb; white-space: nowrap;
}

/* glass-card is now a clean light card — the original dark background
   was producing the ugly black bars visible in the admin and student
   pages after submission. Every usage is now consistent with the overall
   light theme. */
.glass-card {
    background: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius-lg); padding: 2rem; margin-bottom: 1.8rem;
    box-shadow: var(--shadow-sm); position: relative; overflow: hidden;
}
.glass-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2), transparent);
}

/* ── INFO CARD — structured-responses "card" used in the after-submission
   read-only summary view. Clean white card with a left accent border and
   a subtle header stripe. ── */
.info-card {
    background: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.4rem;
    box-shadow: var(--shadow-sm);
    position: relative;
}
.info-card-title {
    font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .14em;
    font-weight: 700; color: var(--accent); margin-bottom: 1.1rem;
    display: flex; align-items: center; gap: .4rem;
}
.detail-row {
    display: flex; align-items: flex-start; gap: .6rem;
    padding: .55rem 0;
    border-bottom: 1px solid var(--navy-border);
    font-size: .88rem; color: var(--text-2); line-height: 1.6;
}
.detail-row:last-child { border-bottom: none; }
.detail-row strong { color: var(--text-1); min-width: 140px; flex-shrink: 0; font-weight: 600; }

/* ── QUOTE CARD — displays the student's comment text after submission ── */
.quote-card {
    background: linear-gradient(135deg, rgba(59,130,246,.04) 0%, rgba(139,92,246,.02) 100%);
    border: 1px solid rgba(59,130,246,.18);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 1.6rem 2rem;
    margin-bottom: 1.4rem;
    position: relative;
}
.quote-card::before {
    content: '\201C';
    position: absolute; top: .6rem; left: 1.2rem;
    font-size: 3.5rem; line-height: 1;
    color: rgba(37,99,235,.15); font-weight: 800; font-family: Georgia, serif;
}
.quote-card p {
    font-size: .95rem !important; color: var(--text-1) !important;
    line-height: 1.85 !important; margin: 0 !important;
    font-style: italic; padding-left: .5rem;
}

/* ── DATA TABLE HEADER — the caption bar above an st.dataframe ──
   `.data-table-wrap` used to sit around this header, carrying the card's
   background, border, radius, shadow and bottom margin. It could not: the
   header and the dataframe are two separate element calls, and an unclosed
   `<div>` in the first is closed by the parser at the end of that fragment,
   so nothing ever wrapped anything. The wrapper styled one strip of text and
   the table sat outside the frame. The card treatment is on the header itself
   now, and the table below keeps the frame it already had from
   `[data-testid="stDataFrame"]`. */
.data-table-header {
    display: flex; align-items: center; gap: .5rem;
    padding: .9rem 1.2rem;
    background: linear-gradient(90deg, rgba(37,99,235,.05), rgba(124,58,237,.03));
    background-color: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius);
    box-shadow: var(--shadow-sm);
    margin-bottom: .5rem;
    font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .13em;
    font-weight: 700; color: var(--accent);
}
/* Dead with the wrapper it depended on: it stripped the dataframe's own frame
   so the two would read as one card. There is no wrapper, so the dataframe
   keeps the border and radius set further down on
   `[data-testid="stDataFrame"]`. */
[data-testid="stDataFrame"] { border-color: var(--navy-border2) !important; }

/* ── SUBMISSION RESULT CARD — success banner shown when a user has
   already submitted for a given category ── */
.submission-result-card {
    background: linear-gradient(135deg, rgba(5,150,105,.05) 0%, rgba(6,182,212,.03) 100%);
    border: 1px solid rgba(5,150,105,.2);
    border-radius: var(--radius-xl);
    padding: 2.8rem 2.5rem 2.2rem;
    text-align: center;
    position: relative; overflow: hidden;
    margin-bottom: 2rem;
}
.submission-result-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--green), #34d399, var(--cyan));
}
.submission-result-card .src-icon {
    display: flex; justify-content: center; margin-bottom: 1rem;
}
.submission-result-card h3 {
    font-size: 1.4rem; font-weight: 800; color: var(--green-text);
    margin-bottom: .55rem; letter-spacing: -.01em;
}
.submission-result-card p {
    font-size: .88rem !important; color: var(--text-2) !important;
    line-height: 1.75 !important; max-width: 520px; margin: 0 auto !important;
}

.context-panel {
    background: linear-gradient(135deg, rgba(59,130,246,.05) 0%, rgba(139,92,246,.03) 100%);
    border: 1px solid rgba(59,130,246,.18);
    border-radius: var(--radius-lg); padding: 1.8rem 2rem; margin-bottom: 1.6rem;
    position: relative; overflow: hidden;
}
.context-panel::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
}
.context-panel-title {
    font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .14em;
    color: #2563eb; font-weight: 700; margin-bottom: 1.2rem;
    display: flex; align-items: center; gap: .45rem;
}
.checkbox-hint { font-size: .72rem; color: var(--text-3); margin-bottom: .7rem; font-style: italic; }

.cat-card {
    background: var(--navy-card); border: 1px solid var(--navy-border);
    border-radius: var(--radius-lg); padding: 1.8rem 1.6rem; margin-bottom: 1rem;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-3) ease; position: relative; overflow: hidden;
}
.cat-card::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transform: scaleX(0); transition: transform var(--dur-3) ease; transform-origin: left;
}
.cat-card:hover { border-color: rgba(59,130,246,.35); transform: translateY(-3px); box-shadow: var(--glow-blue); }
.cat-card:hover::after { transform: scaleX(1); }
.cat-card-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; }
.cat-card-icon-wrap {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, rgba(59,130,246,.15), rgba(139,92,246,.1));
    border: 1px solid rgba(59,130,246,.2); border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
}
.cat-card-title { font-size: 1rem; font-weight: 700; color: var(--text-1); margin-bottom: .3rem; }
.cat-card-desc { font-size: .8rem; color: var(--text-2); line-height: 1.6; margin-bottom: 1rem; }
.cat-card-footer { display: flex; align-items: center; justify-content: space-between; padding-top: .8rem; border-top: 1px solid var(--navy-border); }
.badge-submitted {
    display: inline-flex; align-items: center; gap: .35rem;
    background: rgba(16,185,129,.1); border: 1px solid rgba(16,185,129,.25);
    border-radius: 999px; padding: .22rem .75rem; font-size: .7rem; font-weight: 700; color: var(--green-text);
}
.badge-pending {
    display: inline-flex; align-items: center; gap: .35rem;
    background: rgba(245,158,11,.1); border: 1px solid rgba(245,158,11,.25);
    border-radius: 999px; padding: .22rem .75rem; font-size: .7rem; font-weight: 700; color: var(--gold-text);
}
.cat-stat { font-size: .75rem; color: var(--text-3); display:inline-flex; align-items:center; gap:.3rem; }

.already-submitted {
    background: linear-gradient(135deg, rgba(16,185,129,.06) 0%, rgba(6,182,212,.04) 100%);
    border: 1px solid rgba(16,185,129,.2);
    border-radius: var(--radius-xl); padding: 3rem 2.5rem; text-align: center;
    position: relative; overflow: hidden;
}
.already-submitted .as-icon-wrap { display:flex; justify-content:center; margin-bottom: 1rem; }
.already-submitted h3 { font-size: 1.3rem; font-weight: 700; color: var(--green-text); margin-bottom: .6rem; }
.already-submitted p  { font-size: .9rem; color: var(--text-2); line-height: 1.7; margin: 0; }

.form-section-label {
    font-size: .7rem; text-transform: uppercase; letter-spacing: .12em;
    color: var(--text-3); font-weight: 700; margin-bottom: .8rem;
    display: flex; align-items: center; gap: .4rem;
}
.rating-display {
    background: linear-gradient(135deg, rgba(245,158,11,.06), rgba(249,115,22,.04));
    border: 1px solid rgba(245,158,11,.15);
    border-radius: var(--radius-sm); padding: 1rem 1.4rem;
    display: flex; align-items: center; justify-content: space-between; margin: .8rem 0;
}
.rating-stars { display:flex; gap:.15rem; }
.rating-text  { font-size: 1rem; font-weight: 700; }

/* `backdrop-filter: blur(4px)` used to sit here. The alert's own background is
   a 7–8% alpha tint over an opaque white page, so there is nothing behind it to
   blur and the result was pixel-identical — but it promoted every alert on
   every page to its own compositing layer and blurred the whole area behind it
   on each repaint. Removed: same appearance, no per-alert layer. */
.alert {
    border-radius: var(--radius-sm); padding: 1rem 1.3rem; font-size: .88rem;
    margin: .9rem 0; border-left: 3px solid;
    display: flex; align-items: flex-start; gap: .7rem;
}
.alert-success { background: rgba(16,185,129,.07);  border-color: var(--green); color: var(--green-text); }
.alert-error   { background: rgba(239,68,68,.07);   border-color: var(--red);   color: #dc2626; }
.alert-warning { background: rgba(217,119,6,.08);  border-color: var(--gold);  color: #b45309; }
.alert-info { background: rgba(59,130,246,.07);  border-color: var(--accent);color: var(--blue-text); }

/* ═══════════════════════════
   RESULT DIALOG (components.result_dialog)

   A modal for moments a flow COMPLETES — registration finished, password
   reset finished, an account deleted. Not for form-validation errors: a
   modal on a validation failure puts a dismiss click between the user and
   the field they need to fix, so those stay inline `.alert`s.

   The icon sits in a tinted circle rather than floating in the text the way
   `.alert` does, because a dialog is a self-contained panel and the text
   below it is short enough that a left-aligned glyph would read as a stray
   ornament. `.result-dialog-icon` reuses `svg` sizing from `.lc-ico` so the
   glyph scales with the circle.
   ═══════════════════════════ */
.result-dialog {
    text-align: center; padding: .4rem .2rem .2rem;
}
.result-dialog-icon {
    width: 64px; height: 64px; margin: 0 auto .9rem;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
}
.result-dialog-body {
    font-size: .95rem; line-height: 1.65; color: var(--text-1); font-weight: 500;
}
.result-dialog-details {
    margin-top: .8rem; padding: .7rem .85rem; border-radius: var(--radius-sm);
    font-size: .82rem; line-height: 1.6; color: var(--text-2);
    background: var(--navy-card2); border: 1px solid var(--navy-border);
    text-align: left;
}
.result-dialog-success .result-dialog-icon { background: rgba(16,185,129,.12); color: var(--green-text); }
.result-dialog-error   .result-dialog-icon { background: rgba(239,68,68,.12);  color: #dc2626; }
.result-dialog-warning .result-dialog-icon { background: rgba(217,119,6,.14);  color: #b45309; }
.result-dialog-info    .result-dialog-icon { background: rgba(59,130,246,.12); color: #2563eb; }

/* ═══════════════════════════
   CONFIRMATION DIALOG (components.request_confirmation)

   The counterpart of the result dialog above: that one reports something that
   already happened, this one asks BEFORE it happens. Everything the modal
   prints is escaped in components.py, so the styling only has to make the
   decision readable — question first, then the facts being confirmed, then the
   consequence, with the affirmative choice on the right.
   ═══════════════════════════ */
.confirm-dialog { text-align: center; padding: .35rem .2rem .1rem; }
.confirm-dialog-icon {
    width: 56px; height: 56px; margin: 0 auto .8rem;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: rgba(217,119,6,.14); color: #b45309;
}
.confirm-dialog-title { font-size: 1.05rem; font-weight: 800; color: var(--text-1); margin-bottom: .3rem; }
.confirm-dialog-intro { font-size: .84rem; line-height: 1.6; color: var(--text-2); }
.confirm-dialog-rating {
    display: flex; align-items: center; justify-content: center; gap: .5rem;
    margin: .85rem 0 .1rem; font-size: .82rem; font-weight: 700; color: var(--text-1);
}
.confirm-dialog-summary {
    margin: .85rem 0 0; padding: .2rem .1rem;
    background: var(--navy-card2); border: 1px solid var(--navy-border2);
    border-radius: var(--radius-sm); text-align: left;
}
.confirm-dialog-row {
    display: flex; align-items: baseline; justify-content: space-between; gap: .9rem;
    padding: .5rem .85rem; border-bottom: 1px solid var(--navy-border);
}
.confirm-dialog-row:last-child { border-bottom: none; }
.confirm-dialog-row span {
    font-size: .7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .06em; color: var(--text-3); flex: 0 0 auto;
}
.confirm-dialog-row strong {
    font-size: .82rem; font-weight: 600; color: var(--text-1);
    text-align: right; word-break: break-word; overflow-wrap: anywhere;
}
.confirm-dialog-warning {
    display: flex; align-items: flex-start; gap: .5rem; text-align: left;
    margin-top: .85rem; padding: .7rem .85rem;
    border-radius: var(--radius-sm);
    background: rgba(220,38,38,.06);
    border: 1px solid rgba(220,38,38,.2);
    border-left: 3px solid var(--red);
    font-size: .76rem; line-height: 1.55; color: #92400e;
}
.confirm-dialog-warning > svg { flex-shrink: 0; margin-top: .1rem; }

/* ═══════════════════════════
   DIALOG ADAPTATION (every modal)

   All four dialogs in the app (result, submit-confirm, delete-confirm,
   restore-confirm) open at width="small": a moderate centred panel that
   matches the praised submit-confirmation size. Streamlit's small modal
   already shrinks to the viewport, so this block only trims OUR content —
   tighter banner padding, a shorter scroll window for the delete summary,
   and slightly smaller titles — so nothing inside the modal forces
   horizontal scrolling on a phone. Two-button rows stay two-column
   everywhere, matching the confirmed-good submit dialog.
   ═══════════════════════════ */
@media screen and (max-width: 576px) {
    .confirm-dialog-title { font-size: .95rem; }
    .confirm-dialog-intro { font-size: .8rem; }
    .result-dialog-body { font-size: .88rem; }
    .danger-banner { padding: .65rem .75rem; font-size: .78rem; }
    .confirm-summary { max-height: 240px; }
}

/* ═══════════════════════════
   SEMESTER GATE (Rain / Harmattan)

   The picker and the "not active" explanation. The gate is a return, not a
   warning beside a live form, so it is a self-contained panel: there is
   genuinely nothing else on the page to interact with.
   ═══════════════════════════ */
.semester-picker {
    background: rgba(37,99,235,.04); border: 1px solid rgba(37,99,235,.14);
    border-radius: var(--radius-sm); padding: .8rem 1rem; margin-bottom: .35rem;
}
.semester-picker-label {
    display: flex; align-items: center; gap: .45rem;
    font-size: .82rem; font-weight: 700; color: var(--text-1);
}
.semester-picker-hint { font-size: .74rem; color: var(--text-3); margin-top: .2rem; line-height: 1.5; }
.semester-gate {
    text-align: center; padding: 1.25rem 1.2rem 1.15rem;
    background: var(--navy-card); border: 1px solid var(--navy-border);
    border-radius: var(--radius-lg);
    /* A full-bleed explanation panel reads as an error page; centred and
       capped it reads as a calm empty state with one clear action. Compact
       padding throughout: the card carries one icon, one line of heading
       and three lines of text, so tall air around them reads as broken. */
    max-width: 780px; margin: -1.5rem auto 0 auto;
}
.semester-gate-icon {
    width: 48px; height: 48px; margin: 0 auto .7rem;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: rgba(217,119,6,.13);
}
.semester-gate-title { font-size: 1rem; font-weight: 800; color: var(--text-1); margin: 0 0 .35rem; }
.semester-gate-text {
    font-size: .83rem; line-height: 1.65; color: var(--text-2);
    max-width: 620px; margin: 0 auto;
    /* Stated, not inherited: this is the line a reader judges centring by.
       `balance` evens the wrapped line lengths so centred text reads centred
       instead of ragged; engines without it ignore the declaration. */
    text-align: center; text-wrap: balance;
}
@media screen and (max-width: 576px) {
    .semester-gate { padding: 1.1rem .95rem 1rem; }
    .semester-gate-title { font-size: .95rem; }
    .semester-gate-text { font-size: .8rem; }
}
.course-semester-note {
    display: flex; align-items: center; gap: .45rem;
    font-size: .78rem; color: var(--text-2); line-height: 1.5;
    background: var(--navy-card2); border: 1px solid var(--navy-border);
    border-radius: var(--radius-sm); padding: .55rem .8rem; margin-bottom: .5rem;
}

.insight-card {
    background: var(--navy-card); border: 1px solid var(--navy-border);
    border-radius: var(--radius-lg); padding: 1.8rem 2rem; margin-bottom: 1.2rem;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-3) ease; position: relative; overflow: hidden;
}
.insight-card:hover { transform: translateY(-3px); box-shadow: 0 16px 48px rgba(59,130,246,.12); }
.insight-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem; flex-wrap: wrap; gap:.6rem; }
.insight-header-left { display: flex; align-items: center; gap: .85rem; }
.insight-title { font-size: 1.05rem; font-weight: 700; color: var(--text-1); }
.insight-metrics { 
    display: grid; 
    gap: 1rem; 
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); 
    margin-bottom: 1.2rem; 
}
.insight-metric { background: rgba(15,23,42,.025); border: 1px solid var(--navy-border); border-radius: var(--radius-sm); padding: .9rem 1rem; text-align: center; }
.insight-metric-value { font-size: 1.4rem; font-weight: 800; line-height: 1; margin-bottom: .3rem; }
.insight-metric-label { font-size: var(--fs-2xs); color: var(--text-3); text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
.insight-rec {
    background: rgba(59,130,246,.04); border: 1px solid rgba(59,130,246,.12);
    border-radius: var(--radius-sm); padding: .9rem 1.1rem;
    font-size: .85rem; color: var(--text-2); line-height: 1.7;
    display: flex; align-items: flex-start; gap: .6rem;
}

.cat-breakdown-row {
    display: grid;
    grid-template-columns: 52px 1fr auto;
    gap: 1rem;
    align-items: center;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    border-radius: var(--radius-sm);
    background: rgba(15,23,42,.02);
    border: 1px solid var(--navy-border);
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) ease;
}
.cat-breakdown-row:hover { background: rgba(59,130,246,.04); border-color: rgba(59,130,246,.2); transform: translateX(4px); }
.cat-breakdown-icon-wrap {
    width: 40px; height: 40px; border-radius: 11px;
    background: linear-gradient(135deg, rgba(59,130,246,.12), rgba(139,92,246,.08));
    border: 1px solid rgba(59,130,246,.15);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.cat-breakdown-info { min-width: 0; }
.cat-breakdown-name { font-size: .92rem; font-weight: 700; color: var(--text-1); }
.cat-breakdown-count { font-size: .72rem; color: var(--text-3); margin-top: .15rem; }
.cat-breakdown-stats { text-align: right; min-width: 120px; }
.cat-breakdown-rating { font-size: .95rem; font-weight: 800; color: var(--gold-text); }
.cat-breakdown-sent { font-size: .7rem; font-weight: 700; margin-top: .1rem; display:flex; align-items:center; gap:.25rem; justify-content:flex-end; }

.system-health-box {
    background: linear-gradient(135deg, rgba(59,130,246,.07), rgba(139,92,246,.04));
    border: 1px solid rgba(59,130,246,.2);
    border-radius: var(--radius-lg); padding: 2rem 2.2rem; margin-top: 1.2rem;
    position: relative; overflow: hidden;
}
.system-health-box::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2), var(--cyan));
}
.system-health-title { font-size: 1rem; font-weight: 700; color: var(--blue-text); margin-bottom: .8rem; display: flex; align-items: center; gap: .5rem; }
.system-health-body { font-size: .88rem; color: var(--text-2); line-height: 1.8; }
.sh-tag {
    display: inline-flex; align-items: center; gap: .3rem;
    background: rgba(59,130,246,.1); border: 1px solid rgba(59,130,246,.2);
    border-radius: 6px; padding: .15rem .55rem;
    font-size: .78rem; font-weight: 700; margin: .1rem .2rem; vertical-align: middle;
}

.empty-state { text-align: center; padding: 4rem 2rem; background: var(--navy-card); border: 1px dashed var(--navy-border2); border-radius: var(--radius-xl); }
.empty-state-icon-wrap { display:flex; justify-content:center; margin-bottom: 1.2rem; opacity: .7; }
.empty-state-title { font-size: 1.15rem; font-weight: 700; color: var(--text-2); margin-bottom: .5rem; }
.empty-state-desc { font-size: .85rem; color: var(--text-3); }

/* ══════════════════════════════════════════════════════════════
   ROLE SWITCHER (Segmented Pill Toggle)
   ══════════════════════════════════════════════════════════════
   The Student / Administrator toggle on the sign-in portal.

   These 86 lines used to hang off a `.role-switch-container` div that
   `login.py` emitted as the opening and closing tag of two SEPARATE
   `st.markdown` calls. Streamlit sanitises and re-parses each markdown
   block on its own, so the closing tag landed in a different container
   than the opening one, the wrapper never formed, and every rule below
   matched nothing. The portal toggle rendered as two unstyled radio
   buttons — on the app's primary entry screen.

   `login.py` now calls `st_compat.segmented_control`, which uses
   `st.segmented_control` on Streamlit >= 1.40 and falls back to
   `st.radio` below that. The two render completely different DOM, so
   both are styled here, each by attributes verified against the
   installed Streamlit's own frontend bundle:

     st.segmented_control ->  data-testid="stButtonGroup"
                             button[data-variant="segmented_control"]
                             button[data-variant="segmented_control"][data-selected]

     st.radio (fallback)   ->  data-testid="stRadio"
                             [data-testid="stRadio"] > label
                             [role="radiogroup"]

   No emotion `target:` class name (eqzt73c26 and friends) is used
   anywhere below: those hashes are regenerated on every Streamlit
   build, so a rule written against one silently stops matching on
   upgrade. `data-variant` and `data-selected` are semantic attributes
   Streamlit and Radix set deliberately, and are stable. */
.stButtonGroup {
    margin: 0.25rem auto 0.75rem auto !important;
    max-width: 480px !important;
}
.stButtonGroup [data-testid="stWidgetLabel"] {
    display: none !important;
}
.stButtonGroup [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    align-items: stretch !important;
    gap: 4px !important;
    width: 100% !important;
    background: #ffffff !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 9999px !important;
    padding: 5px !important;
    margin: 0 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}
.stButtonGroup button[data-variant="segmented_control"] {
    flex: 1 1 0% !important;
    min-width: 0 !important;
    min-height: 42px !important;
    border: none !important;
    border-radius: 9999px !important;
    background: transparent !important;
    color: #4B5563 !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    padding: 8px 18px !important;
    cursor: pointer !important;
    box-shadow: none !important;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) var(--ease-standard) !important;
    -webkit-appearance: none !important;
    appearance: none !important;
    white-space: nowrap !important;
}
.stButtonGroup button[data-variant="segmented_control"]:not([data-selected]):hover {
    color: #111827 !important;
    background: rgba(37,99,235,0.06) !important;
}
.stButtonGroup button[data-variant="segmented_control"][data-selected] {
    background: #2563EB !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
}
/* The label text lives in a child <div>/<p> in the segmented control and in
   a <p>/<span> in the radio fallback. Both carry their own colour, so the
   selected white has to be forced down onto them or the white button keeps
   dark text on it. */
.stButtonGroup button[data-variant="segmented_control"][data-selected] *,
.stButtonGroup button[data-variant="segmented_control"][data-selected] p,
.stButtonGroup button[data-variant="segmented_control"][data-selected] span {
    color: #ffffff !important;
}

/* ── st.radio fallback for Streamlit < 1.40 ──
   Same visual result from the older DOM, so the portal looks the same
   regardless of which Streamlit the deployment resolves to.

   SCOPE — these selectors used to be a bare `[data-testid="stRadio"]`,
   which matches the sidebar's navigation radio as well as the login
   portal switcher, so every rule below was silently styling the nav:
   `border-radius: 999px` on `[role="radiogroup"]` painted the whole
   navigation as a white pill with a drop shadow (the reported "ugly
   transparent oval behind the nav"), `margin: .5rem auto 2.25rem auto` +
   `max-width: 420px` re-laid-out the nav container, `justify-content:
   center` + `text-align: center` centred the nav labels, and
   `min-height: 42px` overrode the nav's own sizing.

   The sidebar nav has its own, entirely separate block far above. To stop
   the two blocks competing over one widget, every selector here now
   excludes a radio that is inside the sidebar:

       :not([data-testid="stSidebar"] [data-testid="stRadio"])

   The argument is a full complex selector, which is Selectors Level 4
   and is what `:not()` has accepted since Chrome 88 / Firefox 84 /
   Safari 9. It is strictly older than the `:has()` this block already
   relied on, so nothing that worked before stops working.

   `data-checked` is also gone. The Radio component does not emit it; the
   real attributes are `data-selected` / `data-pressed` / `data-hovered` /
   `data-disabled`, and `data-selected` is absent rather than "false" when
   unselected. The old rules only ever worked through their
   `:has(input:checked)` fallback. */

[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) {
    margin: 0.5rem auto 2.25rem auto !important;
    max-width: 420px !important;
    width: 100% !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) > label,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) [data-testid="stWidgetLabel"] {
    display: none !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) > div,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    align-items: stretch !important;
    gap: 4px !important;
    width: 100% !important;
    background: #ffffff !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 9999px !important;
    padding: 5px !important;
    margin: 0 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label {
    flex: 1 1 0% !important;
    min-width: 0 !important;
    min-height: 42px !important;
    border: none !important;
    border-radius: 9999px !important;
    background: transparent !important;
    color: #4B5563 !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    padding: 8px 18px !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    box-shadow: none !important;
    margin: 0 !important;
    user-select: none !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) var(--ease-standard) !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label:hover {
    color: #111827 !important;
    background: rgba(37,99,235,0.06) !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label > div:first-child,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label input {
    display: none !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label p,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label span {
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    margin: 0 !important;
    line-height: 1.2 !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label[data-selected="true"],
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label:has(input:checked) {
    background: #2563EB !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
}
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label[data-selected="true"] p,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label[data-selected="true"] span,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label:has(input:checked) p,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label:has(input:checked) span,
[data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label:has(input:checked) * {
    color: #ffffff !important;
}

/* ── LOGIN — hero ──

   The institution line ("Federal University of Technology, Owerri · Dept. of
   Information Technology"), the "Live Feedback Platform" badge and the
   academic-session pill that used to sit above the wordmark are gone, along
   with their rules.

   They were not decoration. Three stacked pills pushed the title down by roughly
   a third of the viewport, which is what left a phone user scrolling past the
   whole hero to reach the login form. The department name is not lost — the
   login footer still carries it in full.

   `.pulse-dot` stays. It is defined here but rendered by app.py rather than the
   login page, so removing it along with the badge that used to own it would
   have quietly unstyled a live status indicator somewhere else. */
.pulse-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 0 0 rgba(16,185,129,0.7);
    animation: pulse 1.8s infinite;
}
@keyframes pulse {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16,185,129,0.7); }
    70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16,185,129,0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16,185,129,0); }
}
.login-hero {
    display: flex; align-items: center; gap: 1.1rem;
    margin-bottom: 1rem;
}
.login-logo {
    width: 76px; height: 76px; flex-shrink: 0;
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    border-radius: 20px; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 14px 34px rgba(37,99,235,.25);
    border: 1px solid rgba(255,255,255,0.3);
    transition: transform var(--dur-3) ease;
}
.login-logo:hover {
    transform: translateY(-3px) rotate(2deg);
}
.login-title { font-size: 2.35rem; font-weight: 800; line-height: 1.18; letter-spacing: -.025em; margin: 0; }
.login-title-dark { color: #1E1F24; }
.login-title-gradient {
    background: linear-gradient(135deg, #5B61F6 0%, #00D2FF 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: textShimmer 4s ease infinite alternate;
}
@keyframes textShimmer {
    0% { background-position: 0% 50%; }
    100% { background-position: 100% 50%; }
}
.login-subtitle { font-size: .95rem; color: #475569; line-height: 1.75; max-width: 460px; margin-top: 1rem; margin-bottom: 2rem; }
/* "Scroll down to access the login form."

   Hidden by default, revealed only by the phone breakpoint. On desktop the login
   form sits in the column beside this one, so there is nothing to scroll to and
   the instruction would simply be wrong. `display: none` rather than a muted
   style, so it cannot take up space it was never meant to use. */
.login-scroll-hint { display: none; }
@keyframes scrollHintBounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(3px); }
}
/* ══════════════════════════════════════════════════════════════════════
   ADAPTIVE GRID UTILITIES
   ══════════════════════════════════════════════════════════════════════ */

/* Base adaptive grid — items never smaller than 240px, grow to fill space.
   Usage: .adaptive-grid { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); } */
.adaptive-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

/* Tighter adaptive grid for compact cards — minimum 200px */
.adaptive-grid-compact {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

/* 3-column adaptive grid for metrics — collapses to 2 then 1 on narrow viewports */
.adaptive-metrics-3 {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

/* 4-column adaptive grid for engine stats — collapses gracefully */
.adaptive-metrics-4 {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

/* Feature card grid — 2 columns on desktop, 1 on mobile */
.adaptive-features {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

/* Preview card grid — 3 columns on wide, 2 on medium, 1 on narrow */
.adaptive-preview {
    display: grid;
    gap: 0.65rem;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

/* ══════════════════════════════════════════════════════════════════════ */

.login-feature-grid {
    display: grid;
    gap: 0.85rem;
    /* Fixed pair on desktop (the reference design), one column once the
       login columns stack — never an auto-fit guess, so a tile can neither
       squeeze nor push its neighbours off screen. */
    grid-template-columns: 1fr 1fr;
    margin-bottom: 1.6rem;
    overflow-x: clip;
}
.login-feature-grid > * { min-width: 0; }
.login-feature-card {
    background: #ffffff; border: 1px solid var(--navy-border2);
    border-radius: 14px; padding: 1.1rem 1.15rem;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) var(--ease-standard);
    box-shadow: 0 1px 3px rgba(15,23,42,.03);
}
.login-feature-card:hover {
    border-color: rgba(37,99,235,.35); transform: translateY(-3px);
    box-shadow: 0 10px 24px rgba(37,99,235,.09);
}
.login-feature-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-bottom: .65rem; }
.login-feature-title { font-size: .88rem; font-weight: 700; color: #0f172a; }
.login-feature-desc { font-size: .75rem; color: #64748b; line-height: 1.45; margin-top: .2rem; }
.login-stats-bar { display: flex; border: 1px solid var(--navy-border2); border-radius: 14px; overflow: hidden; max-width: 440px; background: #ffffff; box-shadow: var(--shadow-sm); }
.login-stat-item { flex: 1; padding: .9rem .6rem; text-align: center; border-right: 1px solid var(--navy-border); }
.login-stat-item:last-child { border-right: none; }
.login-stat-value { font-size: 1.18rem; font-weight: 800; color: #0f172a; }
.login-stat-label { font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .09em; color: #64748b; margin-top: .25rem; font-weight: 600; }

/* ── Decorative Dashboard Preview (Exact Reference UI) ──
   Three designed proportions — wide line chart, narrow donut, narrow stat
   column — not three equal tracks. Equal tracks are what squeezed the line
   chart and stranded the stat cards on narrow screens; explicit stages below
   collapse 3 → 2 (+ full-row stat pair) → 1, deterministically. */
.login-preview-card {
    display: grid;
    gap: 0.65rem;
    grid-template-columns: 2.1fr 1.4fr 1.15fr;
    background: var(--navy-card2);
    border: 1px solid var(--navy-border);
    border-radius: 16px;
    padding: 0.75rem;
    margin: 1rem 0 1.3rem 0;
    overflow-x: clip;
}
.login-preview-card > * { min-width: 0; }
.login-preview-tile {
    background: #ffffff;
    border: 1px solid var(--navy-border);
    border-radius: 12px;
    padding: 0.65rem 0.75rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.preview-tile-title {
    font-size: var(--fs-2xs);
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.35rem;
}
.preview-chart-svg {
    width: 100%;
    height: 96px;
    display: block;
}
.sentiment-donut-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 0.15rem 0 0.35rem 0;
}
.sentiment-donut-pie {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: conic-gradient(#10b981 0% 64%, #f59e0b 64% 84%, #ef4444 84% 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}
.sentiment-donut-hole {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #ffffff;
}
.sentiment-legend {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    font-size: var(--fs-2xs);
    color: #64748b;
    font-weight: 500;
}
.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
}
.legend-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    display: inline-block;
}
.dot-green { background: #10b981; }
.dot-amber { background: #f59e0b; }
.dot-red { background: #ef4444; }
.dot-blue { background: #2563eb; }
.dot-cyan { background: #06b6d4; }
.dot-purple { background: #7c3aed; }

.preview-stat-col {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.preview-stat-card {
    background: #ffffff;
    border: 1px solid var(--navy-border);
    border-radius: 12px;
    padding: 0.55rem 0.65rem;
    display: flex;
    align-items: center;
    gap: 0.55rem;
    flex: 1;
}
.preview-stat-card-topcourse {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.15rem;
}
.preview-stat-header {
    font-size: var(--fs-2xs);
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.15rem;
}
.preview-stat-body {
    display: flex;
    align-items: center;
    gap: 0.55rem;
}
.preview-stat-icon {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.preview-stat-icon.icon-purple {
    background: #f3e8ff;
    color: #7c3aed;
}
.preview-stat-icon.icon-green {
    background: #dcfce7;
    color: var(--green-text);
}
.preview-stat-value {
    font-size: 0.98rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
}
.preview-stat-label {
    font-size: var(--fs-2xs);
    color: #64748b;
    font-weight: 500;
    margin-top: 1px;
}

.login-form-header {
    margin-top: 0; margin-bottom: 1.2rem;
    background: #ffffff; border: 1px solid var(--navy-border2);
    border-radius: 20px; padding: 2rem 1.8rem 1.6rem; position: relative; overflow: hidden;
    box-shadow: 0 10px 30px rgba(15,23,42,.05), 0 1px 3px rgba(15,23,42,.04);
}
.login-form-header-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #2563eb, #7c3aed, #06b6d4); }
.login-form-header-tag {
    display: inline-block;
    font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .14em;
    color: #2563eb; font-weight: 700; margin-bottom: .4rem;
    background: rgba(37,99,235,.07); padding: .2rem .6rem; border-radius: 6px;
}
.login-form-header h2 { font-size: 1.6rem; font-weight: 800; color: #0f172a; margin-bottom: .3rem; letter-spacing: -.01em; }
.login-form-header p { font-size: .84rem; color: #64748b; margin: 0; line-height: 1.5; }
.login-demo-box {
    margin-top: .8rem; background: var(--navy-card2);
    border: 1px solid var(--navy-border);
    border-radius: 12px; padding: .9rem 1rem; position: relative; overflow: hidden;
}
.login-demo-bar { position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, #2563eb, #7c3aed, #0891b2); }
.login-demo-title { font-size: var(--fs-2xs); font-weight: 700; text-transform: uppercase; letter-spacing: .12em; color: var(--cyan-text); margin-bottom: .6rem; }
.login-demo-row { display: flex; align-items: center; justify-content: space-between; padding: .35rem 0; }
.login-demo-row-border { border-bottom: 1px solid var(--navy-border); }
.login-demo-badge { font-size: var(--fs-2xs); font-weight: 700; text-transform: uppercase; padding: .15rem .5rem; border-radius: 999px; }
.login-demo-cred { font-family: 'JetBrains Mono', monospace !important; font-size: .72rem; color: #64748b; }
.login-demo-cred strong { color: #1e293b; }
/* Same reason as the placeholder rule above: `#94a3b8` is the decorative
   value, and the footer carries real text — the demo credentials notice —
   on a white card. */
.login-footer { margin-top: .8rem; text-align: center; font-size: var(--fs-2xs); color: var(--text-3); }

/* ── LOGIN — basic admin card ── */
.admin-login-shell { display:flex; justify-content:center; padding-top: 1rem; }
.admin-login-card {
    width: 100%;
    margin-bottom: 1.4rem;
    background: #ffffff;
    border: 1px solid var(--navy-border2);
    border-radius: 20px;
    padding: 2.5rem 2.2rem;
    text-align: center;
    box-shadow: 0 12px 36px rgba(15,23,42,.06);
    position: relative;
    overflow: hidden;
}
.admin-login-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #475569, #1e293b, #2563eb);
}
.admin-login-icon {
    width: 60px; height: 60px; margin: 0 auto 1.2rem;
    background: rgba(37,99,235,.08); border: 1px solid rgba(37,99,235,.2);
    border-radius: 18px; display:flex; align-items:center; justify-content:center;
    box-shadow: 0 4px 16px rgba(37,99,235,.12);
}
.admin-login-title { font-size: 1.4rem; font-weight: 800; color: var(--text-1); margin-bottom: .4rem; letter-spacing: -.01em; }
.admin-login-subtitle { font-size: .82rem; color: var(--text-3); margin-bottom: 1.8rem; line-height: 1.5; }

/* Markdown paragraphs get the secondary text colour so `st.markdown` body
   copy does not compete with headings. The `!important` used to hit the
   `<p>` Streamlit renders *inside* `st.expander` summaries and inside
   `st.info`/`st.warning`/`st.error`, tinting those status messages the same
   grey as ordinary prose and cancelling their semantic colour. Those
   elements opt back in below. */
[data-testid="stMarkdownContainer"] p { color: var(--text-2) !important; }
[data-testid="stMarkdownContainer"] [data-testid="stAlert"] p { color: inherit !important; }
[data-testid="stMarkdownContainer"] summary p,
[data-testid="stMarkdownContainer"] .stMarkdownBlock p { color: inherit !important; }
[data-testid="stWidgetLabel"] { color: var(--text-2) !important; font-size: .85rem !important; margin-bottom: .2rem !important; }
[data-testid="stWidgetLabel"] p { margin: 0 !important; line-height: 1.3 !important; }
[data-testid="stForm"] { background: transparent !important; border: none !important; padding: 0 !important; }

/* Uniform, deliberate vertical rhythm inside forms — every field and
   button gets the same gap from the one before it, instead of relying
   on Streamlit's own per-element defaults (which don't come out even
   across every widget type and were producing uneven, "floaty" gaps
   between a label and its own input). */
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: .85rem !important; }
[data-testid="stForm"] [data-testid="stElementContainer"] { margin: 0 !important; }

/* The single-line expander rule that used to live here is gone. Every
   declaration in it was restated — identically, at the same specificity —
   by the "ENHANCED EXPANDERS" block further down this file, which also adds
   padding, weight, a hover state and a transition. Two rules of equal
   specificity means the later one always won, so this copy could not have
   had any effect; it only made the stylesheet look like it had two sources
   of truth for the expander. Kept here as a note so nobody re-adds it. */

/* The grid inside st.dataframe is drawn on an HTML canvas (see the note
   at the top of .streamlit/config.toml for why) — CSS can't reach individual
   cell colors, only the outer frame/border around it, styled here. */
[data-testid="stDataFrame"] {
    border: 1px solid var(--navy-border2) !important;
    border-radius: var(--radius-sm) !important;
    background: var(--navy-card) !important;
}
[data-testid="stDataFrameResizable"] { background: var(--navy-card) !important; }
.stPlotlyChart { border-radius: var(--radius-lg) !important; overflow: hidden; }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--text-3) !important; }

/* Scrollbars were 5px wide with a thumb the same tint as the track, which
   is below the ~8px minimum for a comfortable grab and close to invisible
   against the card. Now 10px, with a visible thumb, a hover state and a
   `scrollbar-color` fallback for the Firefox-standard properties. */
* {
    scrollbar-width: thin;
    scrollbar-color: var(--navy-border2) transparent;
}
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--navy); border-radius: 999px; }
::-webkit-scrollbar-thumb { background: var(--navy-border2); border-radius: 999px; border: 2px solid var(--navy); }
::-webkit-scrollbar-thumb:hover { background: var(--text-3); }

/* The one-line `.chart-wrap` that used to live here is gone: the
   "ENHANCED CHART WRAP" block further down restates every one of its
   declarations at the same specificity and adds the hover sheen on top, so
   this copy was unreachable. See the note above the expander rules. */
.chart-title { font-size: var(--fs-2xs); text-transform: uppercase; letter-spacing: .12em; color: var(--text-3); font-weight: 700; margin-bottom: .8rem; padding-left: .2rem; display:flex; align-items:center; gap:.4rem; }

.stat-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }
.stat-pill {
    display: inline-flex; align-items: center; gap: .5rem;
    background: var(--navy-card); border: 1px solid var(--navy-border2);
    border-radius: 999px; padding: .45rem 1rem;
    font-size: .82rem; color: var(--text-2); font-weight: 500; transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2);
}
.stat-pill:hover { border-color: rgba(59,130,246,.3); color: var(--text-1); }
.stat-pill strong { color: var(--text-1); font-weight: 700; }

.progress-wrap { margin: .5rem 0 1.2rem; }
.progress-label { display: flex; justify-content: space-between; font-size: .72rem; color: var(--text-3); margin-bottom: .35rem; font-weight: 600; text-transform: uppercase; letter-spacing: .07em; }
.progress-track { height: 6px; background: var(--navy-border); border-radius: 999px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), var(--accent2)); transition: width var(--dur-4) var(--ease-standard); }

.sub-tag-wrap { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .6rem; }
.sub-tag {
    display: inline-flex; align-items: center; gap: .28rem;
    background: rgba(59,130,246,.08); border: 1px solid rgba(59,130,246,.2);
    border-radius: 8px; padding: .2rem .65rem; font-size: .72rem; font-weight: 600; color: #2563eb;
}
.sub-tag-green { background: rgba(16,185,129,.08); border-color: rgba(16,185,129,.2); color: var(--green-text); }
.sub-tag-gold { background: rgba(217,119,6,.08); border-color: rgba(217,119,6,.25); color: var(--gold-text); }

.tag-pill {
    display: inline-flex; align-items: center; gap: .35rem;
    background: var(--navy-card2); border: 1px solid var(--navy-border);
    border-radius: 999px; padding: .25rem .75rem;
    font-size: .72rem; font-weight: 600; color: var(--text-2);
}
.tag-pill-blue { background: rgba(37,99,235,.08); border-color: rgba(37,99,235,.2); color: #2563eb; }
.tag-pill-green { background: rgba(5,150,105,.08); border-color: rgba(5,150,105,.2); color: var(--green-text); }
.tag-pill-gold { background: rgba(217,119,6,.08); border-color: rgba(217,119,6,.25); color: var(--gold-text); }

/* ══════════════════════════════════════════════════════════════
   RESPONSIVE DESIGN SYSTEM (Mobile, Tablet, Desktop)
   ══════════════════════════════════════════════════════════════ */

/* ── Large Tablet / Small Laptop (max-width: 1024px) ── */
@media screen and (max-width: 1024px) {
    .block-container {
        padding: 1.2rem 1.6rem 3.5rem !important;
    }
    .login-title {
        font-size: 2rem !important;
    }
    .login-preview-card {
        grid-template-columns: 1.5fr 1fr;
    }
    /* The stat column stops being a third track and becomes a full-width row
       of two cards — the only stage between the desktop trio and the phone
       stack, so mid widths never get three squeezed columns. */
    .login-preview-card .preview-stat-col {
        grid-column: 1 / -1;
        display: grid !important;
        grid-template-columns: 1fr 1fr;
        gap: 0.65rem;
    }
}

/* ── Tablet (max-width: 768px) ── */
@media screen and (max-width: 768px) {
    .block-container {
        padding: 1rem 1.2rem 3rem !important;
    }

    /* ── Large surfaces ──
       `.page-header`, `.info-card`, `.quote-card`, `.admin-login-card` and
       `.login-form-header` all had a step down at this width, but the six
       biggest cards in the app did not, so a tablet paid full desktop
       padding for content it no longer had room for:

         .glass-card          2rem        -> 1.3rem
         .insight-card        1.8rem 2rem  -> 1.25rem 1.4rem
         .context-panel       1.8rem 2rem  -> 1.25rem 1.4rem
         .engine-status-card  1.8rem 2rem  -> 1.25rem 1.4rem
         .cat-card            1.8rem 1.6rem -> 1.2rem 1.1rem
         .metric-card         1.6rem 1.4rem -> 1.2rem 1rem

       `.submission-result-card` (2.8rem 2.5rem 2.2rem) and
       `.live-preview-card` (1.4rem 1.8rem 1rem) only stepped down at 576px,
       which left the whole 577–768px band at its widest. They step at 768
       and keep their own smaller step at 576, where these do not apply.

       `.insight-card`/`.context-panel`/`.engine-status-card`/`.cat-card`/
       `.metric-card` keep their `:hover` lift and shadow; only the padding
       is reduced, so no affordance is lost. */
    .glass-card {
        padding: 1.3rem !important;
        margin-bottom: 1.3rem !important;
    }
    .insight-card,
    .context-panel,
    .engine-status-card {
        padding: 1.25rem 1.4rem !important;
    }
    .cat-card {
        padding: 1.2rem 1.1rem !important;
    }
    .metric-card {
        padding: 1.2rem 1rem !important;
    }
    .submission-result-card {
        padding: 2rem 1.5rem 1.6rem !important;
    }
    .live-preview-card {
        padding: 1.2rem 1.3rem .9rem !important;
    }
    .data-table-header {
        padding: .7rem .9rem !important;
    }

    /* ── Grid steps that used to wait for 700px or narrower ──
       `.insight-metrics` is `repeat(3, 1fr)` and only collapsed at the 700px
       column-stacking breakpoint, so between 701 and 768px three cards were
       fighting for one tablet-width row. `.engine-metrics-row` and
       `.engine-trained-row` are `repeat(4, 1fr)` and jumped straight from four
       columns to two, skipping the awkward middle. Both now get an explicit
       step here, and the existing narrower rules below still take over. */
    .insight-metrics {
        grid-template-columns: 1fr 1fr !important;
        gap: .8rem !important;
    }
    .engine-metrics-row,
    .engine-trained-row {
        grid-template-columns: 1fr 1fr !important;
    }

    .login-title {
        font-size: 1.85rem !important;
    }
    .login-subtitle {
        font-size: 0.88rem !important;
        max-width: 100% !important;
        margin-bottom: 1.5rem !important;
    }
    .login-preview-card {
        grid-template-columns: 1fr !important;
        gap: 0.75rem !important;
    }
    .preview-stat-col {
        flex-direction: row !important;
    }
    .preview-stat-card {
        flex: 1 1 0% !important;
    }
    .page-header {
        padding: 1.4rem 1.2rem !important;
        border-radius: var(--radius) !important;
    }
    .page-header h1 {
        font-size: 1.45rem !important;
    }
    .page-header-top {
        gap: 0.8rem !important;
    }
    .page-header-icon-wrap {
        width: 44px !important;
        height: 44px !important;
    }
    .stat-row {
        gap: 0.5rem !important;
        margin-bottom: 1.2rem !important;
    }
    .stat-pill {
        font-size: 0.76rem !important;
        padding: 0.35rem 0.75rem !important;
    }
    .login-form-header {
        padding: 1.5rem 1.2rem !important;
        border-radius: 16px !important;
    }
    .admin-login-card {
        padding: 2rem 1.4rem !important;
        border-radius: 16px !important;
    }
    .info-card {
        padding: 1.2rem 1.2rem !important;
    }
    .quote-card {
        padding: 1.2rem 1.4rem !important;
    }
    .cat-breakdown-row {
        padding: 0.9rem 1rem !important;
        grid-template-columns: 1fr !important;
        gap: 0.75rem !important;
    }
    .cat-breakdown-icon-wrap {
        margin: 0 auto !important;
    }
    .cat-breakdown-stats {
        text-align: left !important;
        min-width: 0 !important;
        display: flex !important;
        gap: 1rem !important;
        justify-content: flex-start !important;
        flex-wrap: wrap !important;
    }
    .cat-breakdown-sent {
        justify-content: flex-start !important;
    }
    /* The two `overflow-x: auto` overrides that used to live here targeted
       `.data-table-wrap`, which no longer exists and never wrapped the table.
       `st.dataframe` scrolls its own canvas horizontally, so nothing is
       needed — and nothing is clipped, because the frame is now on the
       dataframe element itself. */
}

/* ── Mobile Phone (max-width: 576px) ── */
@media screen and (max-width: 576px) {
    .block-container {
        padding: 0.75rem 0.75rem 2.5rem !important;
    }

    /* ── Login page ── */

    /* The two columns stack on a phone, so the login form ends up below this
       entire column — hero, subtitle, feature cards and stats. That is correct
       behaviour, but it left a phone user on what looked like a landing page
       with no way in, so the instruction is shown here and only here. */
    .login-scroll-hint {
        display: flex !important;
        align-items: center;
        gap: 0.45rem;
        max-width: 100%;
        margin: -1rem 0 1.4rem;
        padding: 0.55rem 0.85rem;
        border: 1px dashed rgba(37, 99, 235, 0.35);
        border-radius: 10px;
        background: rgba(37, 99, 235, 0.05);
        color: #1d4ed8;
        font-size: var(--fs-2xs);
        font-weight: 700;
        line-height: 1.3;
    }
    .login-scroll-hint .lc-ico {
        flex-shrink: 0;
        animation: scrollHintBounce 1.8s var(--ease-standard) infinite;
    }
    /* Keep the logo and title side-by-side on mobile (the desktop arrangement)
   instead of stacking them. The text is just small enough to fit beside the
   icon at 360px viewport width. */
.login-hero {
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.6rem !important;
}
.login-logo {
    width: 52px !important;
    height: 52px !important;
}
.login-title {
    font-size: 1.35rem !important;
    line-height: 1.25 !important;
}
    .login-feature-grid {
        grid-template-columns: 1fr !important;
        gap: 0.6rem !important;
    }
    .login-stats-bar {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        max-width: 100% !important;
    }
    .login-stat-item {
        border-bottom: 1px solid var(--navy-border);
    }
    .login-stat-item:nth-child(2) {
        border-right: none !important;
    }
    .login-stat-item:nth-child(3),
    .login-stat-item:nth-child(4) {
        border-bottom: none !important;
    }
    .stButtonGroup,
    [data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) {
        max-width: 100% !important;
        margin: 0.2rem auto 1rem auto !important;
    }
    .stButtonGroup button[data-variant="segmented_control"],
    [data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label {
        padding: 0.4rem 0.5rem !important;
        min-height: 38px !important;
    }
    .stButtonGroup button[data-variant="segmented_control"] p,
    .stButtonGroup button[data-variant="segmented_control"] span,
    [data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label p,
    [data-testid="stRadio"]:not([data-testid="stSidebar"] [data-testid="stRadio"]) label span {
        font-size: 0.82rem !important;
    }
    .preview-stat-col {
        flex-direction: column !important;
        /* Pairs with the 1024px grid conversion above: without this the two
           stat cards would stay two-across on a phone instead of stacking. */
        grid-template-columns: 1fr !important;
    }
    .detail-row {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 0.25rem !important;
        padding: 0.65rem 0 !important;
    }
    .detail-row strong {
        min-width: unset !important;
        font-size: 0.82rem !important;
        color: var(--text-3) !important;
    }
    .cat-breakdown-row {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 0.75rem !important;
    }
    .cat-breakdown-stats {
        width: 100% !important;
        justify-content: space-between !important;
        border-top: 1px dashed var(--navy-border);
        padding-top: 0.5rem;
    }
    .section-header {
        margin-bottom: 1rem !important;
        margin-top: 0.3rem !important;
    }
    .section-header-pill {
        font-size: var(--fs-2xs) !important;
        padding: 0.25rem 0.7rem !important;
    }
    .metric-card {
        padding: 1rem 0.85rem !important;
    }
    .metric-value {
        font-size: 1.4rem !important;
    }
    .metric-label {
        font-size: var(--fs-2xs) !important;
    }
    .submission-result-card {
        padding: 1.8rem 1.2rem 1.4rem !important;
    }
    .submission-result-card h3 {
        font-size: 1.2rem !important;
    }

    /* ── Sidebar navigation ── */
    [data-testid="stSidebar"] [data-testid="stRadioOption"] {
        min-height: 2.2rem !important;
        padding: 0.4rem 0.6rem !important;
        font-size: 0.82rem !important;
    }
    .sidebar-profile {
        padding: 1rem 0.8rem !important;
    }
    .sidebar-avatar {
        width: 40px !important;
        height: 40px !important;
        font-size: 1rem !important;
    }
    .sidebar-name {
        font-size: 0.85rem !important;
    }
    .sidebar-engine-badge {
        padding: 0.6rem 0.75rem !important;
    }

    /* ── Charts and tables ── */
    .chart-wrap {
        padding: 0.75rem !important;
    }
    .chart-title {
        font-size: 0.72rem !important;
    }

    /* ── Forms ── */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox select,
    .stNumberInput input,
    .stDateInput input {
        font-size: 16px !important; /* Prevents iOS zoom on focus */
    }

    /* ── Buttons ── */
    .stButton > button,
    .stFormSubmitButton > button,
    [data-testid^="stBaseButton"] {
        padding: 0.55rem 1rem !important;
        font-size: 0.88rem !important;
        min-height: 42px !important;
    }
    input, select, textarea {
        font-size: 16px !important;
    }
}

/* ══════════════════════════════════════════════════════════════
   PAGE HEADER — ANIMATED SHIMMER UPGRADE
   ══════════════════════════════════════════════════════════════ */
@keyframes headerShimmer {
    0%   { background-position: -200% center; }
    100% { background-position:  200% center; }
}
.page-header::after {
    background: linear-gradient(
        135deg,
        rgba(139,92,246,.07) 0%,
        rgba(59,130,246,.04) 50%,
        rgba(6,182,212,.07) 100%
    );
    animation: headerShimmer 8s linear infinite;
    background-size: 200% 200%;
}
.page-header h1 {
    background: linear-gradient(135deg, #0f172a 30%, #2563eb 65%, #7c3aed 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: headerShimmer 6s linear infinite;
}

/* ══════════════════════════════════════════════════════════════
   ENHANCED METRIC CARDS

   This block used to attach `@keyframes cardFloat` (a 2.5s infinite
   `translateY(0) -> translateY(-2px)` oscillation) to `.metric-card:hover`,
   which silently cancelled the card's real hover lift declared 300 lines
   above — an `animation` on `transform` outranks a plain declaration of the
   same property at all times, so the lift never rendered and the card drifted
   two pixels forever instead. It also meant every card under the pointer
   repainted continuously, for as long as the pointer rested there.

   The lift now lives entirely in the `.metric-card:hover` rule above, which
   is where it always should have been, and this block only contributes the
   transition that makes it move. The transform uses `--ease-emphasis`, the
   overshoot curve: a 4px lift that arrives with a hair of bounce reads as
   "it responded to me", where the standard curve reads as "it moved".
   ══════════════════════════════════════════════════════════════ */
.metric-card {
    transition:
        transform var(--dur-3) var(--ease-emphasis),
        border-color var(--dur-2) var(--ease-standard),
        box-shadow var(--dur-3) var(--ease-standard);
}

/* ══════════════════════════════════════════════════════════════
   SENTIMENT CONFIDENCE BADGE  (used in my_stats.py)
   ══════════════════════════════════════════════════════════════ */
.sentiment-confidence-badge {
    display: inline-flex;
    align-items: center;
    gap: .28rem;
    border: 1px solid;
    border-radius: 999px;
    padding: .18rem .55rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
    letter-spacing: .04em;
    vertical-align: middle;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) ease;
}
.sentiment-confidence-badge:hover {
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0,0,0,.1);
}

/* ══════════════════════════════════════════════════════════════
   ENGINE STATUS CARD  (used in full_dashboard.py)
   ══════════════════════════════════════════════════════════════ */
.engine-status-card {
    background: linear-gradient(135deg,
        rgba(37,99,235,.05) 0%,
        rgba(124,58,237,.04) 50%,
        rgba(6,182,212,.03) 100%);
    border: 1px solid rgba(37,99,235,.2);
    border-radius: var(--radius-lg);
    padding: 1.8rem 2rem;
    margin-bottom: 1.4rem;
    position: relative;
    overflow: hidden;
}
.engine-status-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #2563eb, #7c3aed, #06b6d4);
}
.engine-status-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 1.4rem;
}
.engine-status-left {
    display: flex;
    align-items: center;
    gap: .9rem;
}
.engine-status-icon {
    width: 52px; height: 52px;
    border-radius: 14px;
    border: 1px solid;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 4px 16px rgba(37,99,235,.15);
}
.engine-status-title {
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    color: var(--text-3);
    font-weight: 700;
    margin-bottom: .35rem;
}
.engine-active-pill {
    display: inline-flex;
    align-items: center;
    border: 1px solid;
    border-radius: 999px;
    padding: .3rem .9rem;
    font-size: .78rem;
    font-weight: 700;
    letter-spacing: .02em;
}
.engine-conf-badge {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    background: rgba(124,58,237,.07);
    border: 1px solid rgba(124,58,237,.2);
    border-radius: 999px;
    padding: .35rem .9rem;
    font-size: .72rem;
    font-weight: 600;
    color: #7c3aed;
    white-space: nowrap;
    align-self: flex-start;
}
.engine-metrics-row {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    margin-bottom: 1rem;
}
.engine-metric-box {
    background: rgba(255,255,255,.7);
    border: 1px solid var(--navy-border);
    border-radius: var(--radius-sm);
    padding: .9rem 1rem;
    text-align: center;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) ease;
}
.engine-metric-box:hover {
    border-color: rgba(37,99,235,.3);
    box-shadow: 0 4px 16px rgba(37,99,235,.08);
    transform: translateY(-2px);
}
.engine-metric-val {
    font-size: 1.6rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: .3rem;
}
.engine-metric-lbl {
    font-size: var(--fs-2xs);
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: .08em;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: .25rem;
}
.engine-trained-row {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    background: rgba(5,150,105,.04);
    border: 1px solid rgba(5,150,105,.15);
    border-radius: var(--radius-sm);
    padding: .9rem 1rem;
    margin-top: .5rem;
}
.engine-trained-stat { text-align: center; }
.engine-trained-val {
    font-size: 1.15rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: .2rem;
}
.engine-trained-lbl {
    font-size: var(--fs-2xs);
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: .08em;
    font-weight: 600;
}
.engine-error-pill {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    background: rgba(220,38,38,.06);
    border: 1px solid rgba(220,38,38,.2);
    border-radius: 8px;
    padding: .45rem .9rem;
    font-size: .75rem;
    color: #dc2626;
    margin-top: .7rem;
}

/* ══════════════════════════════════════════════════════════════
   LIVE PREVIEW CARD  (real-time sentiment demo in full_dashboard)
   ══════════════════════════════════════════════════════════════ */
.live-preview-card {
    background: linear-gradient(135deg,
        rgba(6,182,212,.05) 0%,
        rgba(124,58,237,.04) 100%);
    border: 1px solid rgba(6,182,212,.2);
    border-radius: var(--radius-lg);
    padding: 1.4rem 1.8rem 1rem;
    margin-bottom: .6rem;
    position: relative;
    overflow: hidden;
}
.live-preview-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #06b6d4, #7c3aed, #2563eb);
}
.live-preview-header {
    margin-bottom: .3rem;
}
.live-preview-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, rgba(6,182,212,.2), rgba(124,58,237,.15));
    border: 1px solid rgba(6,182,212,.3);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem;
    flex-shrink: 0;
}
.live-preview-title {
    font-size: .88rem;
    font-weight: 700;
    color: var(--text-1);
}
.live-preview-sub {
    font-size: .72rem;
    color: var(--text-3);
    margin-top: .15rem;
}

/* Preview result card */
.preview-result-card {
    background: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius);
    padding: 1.3rem 1.5rem;
    margin: .6rem 0 1.2rem;
    position: relative;
    overflow: hidden;
}
.preview-result-top {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
}
.preview-label-pill {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    border: 1px solid;
    border-radius: 999px;
    padding: .38rem 1.1rem;
    font-size: .85rem;
    font-weight: 800;
    letter-spacing: .02em;
    flex-shrink: 0;
}
.preview-conf-wrap {
    display: flex;
    align-items: center;
    gap: .6rem;
    flex: 1;
    min-width: 140px;
}
.preview-conf-bar-track {
    flex: 1;
    height: 6px;
    background: var(--navy-border);
    border-radius: 999px;
    overflow: hidden;
}
.preview-conf-bar-fill {
    height: 100%;
    border-radius: 999px;
    transition: width var(--dur-4) var(--ease-standard);
}
.preview-conf-text {
    font-size: .72rem;
    color: var(--text-3);
    white-space: nowrap;
    font-weight: 600;
}
.preview-conf-text em {
    font-style: normal;
    color: var(--text-2);
}
.preview-score-pill {
    font-size: .72rem;
    color: var(--text-3);
    background: var(--navy-card2);
    border: 1px solid var(--navy-border);
    border-radius: 6px;
    padding: .2rem .55rem;
    font-weight: 600;
    white-space: nowrap;
}
.preview-score-pill strong {
    color: var(--text-1);
}

/* Polarity bars */
.preview-polarity-bars {
    display: flex;
    flex-direction: column;
    gap: .5rem;
    margin-bottom: .9rem;
}
.preview-pol-item {
    display: flex;
    align-items: center;
    gap: .65rem;
}
.preview-pol-label {
    font-size: var(--fs-2xs);
    font-weight: 700;
    min-width: 65px;
    display: flex;
    align-items: center;
    gap: .25rem;
}
.preview-pol-track {
    flex: 1;
    height: 5px;
    background: var(--navy-border);
    border-radius: 999px;
    overflow: hidden;
}
.preview-pol-fill {
    height: 100%;
    border-radius: 999px;
    transition: width var(--dur-4) ease;
    opacity: .85;
}
.preview-pol-pct {
    font-size: var(--fs-2xs);
    color: var(--text-3);
    font-weight: 700;
    min-width: 28px;
    text-align: right;
}

/* Cue tags */
.preview-cues-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: .35rem;
    margin-bottom: .45rem;
    font-size: .72rem;
    color: var(--text-3);
}
.preview-cue-tag {
    display: inline-flex;
    align-items: center;
    border-radius: 6px;
    padding: .15rem .52rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
}
.preview-cue-pos {
    background: rgba(5,150,105,.09);
    border: 1px solid rgba(5,150,105,.22);
    color: var(--green-text);
}
.preview-cue-neg {
    background: rgba(220,38,38,.08);
    border: 1px solid rgba(220,38,38,.2);
    color: #dc2626;
}
.preview-tag {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    border: 1px solid;
    border-radius: 6px;
    padding: .2rem .6rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
    margin-top: .3rem;
}
.preview-engine-tag {
    font-size: var(--fs-2xs);
    color: var(--text-3);
    margin-top: .7rem;
    display: flex;
    align-items: center;
    gap: .3rem;
    padding-top: .6rem;
    border-top: 1px solid var(--navy-border);
}
.preview-empty-hint {
    font-size: .8rem;
    color: var(--text-3);
    text-align: center;
    padding: 1rem;
    font-style: italic;
}

/* ══════════════════════════════════════════════════════════════
   ENHANCED EXPANDERS
   ══════════════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
    background: var(--navy-card) !important;
    border: 1px solid var(--navy-border2) !important;
    border-radius: var(--radius) !important;
    transition: border-color var(--dur-2) ease, box-shadow var(--dur-2) ease !important;
    margin-bottom: .6rem !important;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(37,99,235,.3) !important;
    box-shadow: 0 4px 16px rgba(37,99,235,.06) !important;
}
[data-testid="stExpander"] summary {
    color: var(--text-2) !important;
    font-size: .88rem !important;
    font-weight: 600 !important;
    padding: .9rem 1.1rem !important;
    border-radius: var(--radius) !important;
    transition: background var(--dur-1) ease !important;
}
[data-testid="stExpander"] summary:hover {
    background: rgba(37,99,235,.04) !important;
    color: var(--text-1) !important;
}

/* ══════════════════════════════════════════════════════════════
   ENHANCED CHART WRAP
   ══════════════════════════════════════════════════════════════ */
.chart-wrap {
    background: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius-lg);
    padding: 1.4rem 1.2rem 1rem;
    margin-bottom: 1.2rem;
    transition: border-color var(--dur-2) ease, box-shadow var(--dur-2) ease;
    position: relative;
    overflow: hidden;
}
.chart-wrap::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(37,99,235,.25), transparent);
    opacity: 0;
    transition: opacity var(--dur-3);
}
.chart-wrap:hover {
    border-color: rgba(37,99,235,.25);
    box-shadow: 0 8px 28px rgba(37,99,235,.07);
}
.chart-wrap:hover::before {
    opacity: 1;
}

/* ══════════════════════════════════════════════════════════════
   ENHANCED SECTION HEADER ANIMATION
   ══════════════════════════════════════════════════════════════ */
.section-header-pill {
    position: relative;
    overflow: hidden;
    transition: background-color, border-color, box-shadow, color, fill, stroke, opacity, transform var(--dur-2) ease;
}
.section-header-pill:hover {
    background: rgba(37,99,235,.14);
    border-color: rgba(37,99,235,.35);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37,99,235,.12);
}

/* ══════════════════════════════════════════════════════════════
   MOBILE RESPONSIVE — new components

   The two `grid-template-columns: 1fr 1fr` rules for
   `.engine-metrics-row`/`.engine-trained-row` that used to sit here are gone:
   they are now declared once, alongside the rest of the tablet grid steps in
   the single 768px block further up, so those two grids have one breakpoint
   instead of two that always agreed. `.insight-metrics` joined them there too.
   ══════════════════════════════════════════════════════════════ */
@media screen and (max-width: 768px) {
    .engine-status-header {
        flex-direction: column !important;
    }
    .preview-result-top {
        flex-direction: column !important;
        align-items: flex-start !important;
    }
    .preview-conf-wrap {
        width: 100% !important;
    }
}
@media screen and (max-width: 576px) {
    /* The two `grid-template-columns: 1fr 1fr` declarations here are kept
       only for the gap; the column count itself is inherited from the 768px
       block above, which already reduced these grids from four to two. */
    .engine-metrics-row {
        gap: .6rem !important;
    }
    .engine-trained-row {
        gap: .6rem !important;
    }
    .live-preview-card {
        padding: 1rem 1.1rem .8rem !important;
    }
}

/* ═══════════════════════════
   RESPONSIVE COLUMN STACKING (U-10)

   Streamlit's `st.columns` lays out as a flex row with no breakpoint of its
   own: below roughly 700px each column keeps its declared fractional width,
   so a 4-up metric row or a 1:1 dashboard pair stays side by side and ends
   up ~150px wide per column, with chart labels and table headers overlapping.
   Forcing the block to wrap and each child to `flex: 1 0 100%` collapses
   columns to full width on small screens, which is the same content
   rearranged rather than truncated. `stHorizontalBlock` is the container
   test-id Streamlit renders for every `st.columns` call.
   ═══════════════════════════ */
@media screen and (max-width: 700px) {
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: .75rem !important;
    }
    /* `stVerticalBlockBorderWrapper` was named here for bordered columns, but
       no such test-id exists — `st.columns(border=)` is never used and the
       wrapper was removed upstream. `stVerticalBlock` is the real container
       test-id, so a bordered `st.container` inside a column row (the danger
       band on User Management, for one) now collapses correctly too. */
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlock"] {
        flex: 1 0 100% !important;
        min-width: 100% !important;
    }
    /* `.insight-metrics` is a hand-rolled 3-column grid on Decision
       Insights; it needs the same treatment as real Streamlit columns. */
    .insight-metrics {
        grid-template-columns: 1fr !important;
        gap: .7rem !important;
    }
}

/* ═══════════════════════════
   USER MANAGEMENT — DIRECTORY
   ═══════════════════════════ */
.um-filter-bar {
    display: flex;
    gap: .6rem;
    align-items: flex-end;
    margin-bottom: .5rem;
}
.um-filter-bar > [data-testid="stVerticalBlock"] { min-width: 0; }

.um-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    background: var(--navy-card);
    border: 1px solid var(--navy-border);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-sm);
    padding: .7rem .95rem;
    margin-bottom: .45rem;
    transition: border-color var(--dur-1), box-shadow var(--dur-1);
}
.um-row:hover { box-shadow: var(--shadow-sm); border-color: var(--navy-border2); }
.um-row.is-target {
    border-color: rgba(37,99,235,.45);
    border-left-color: var(--accent);
    background: rgba(37,99,235,.03);
    box-shadow: 0 0 0 1px rgba(37,99,235,.14);
}
.um-row.is-admin { border-left-color: var(--accent2); }
.um-row.is-admin.is-target { border-color: rgba(124,58,237,.45); background: rgba(124,58,237,.03); }

/* ── DELETION AUDIT TRAIL ──
   `_render_audit_log` on User Management emits a structured row — tinted icon,
   "Deleted <user>", actor and timestamp, the recorded reason, and a count of
   feedback records removed — and until this pass not one of those seven classes
   existed in this file, so the trail rendered as an unstyled stack of block
   divs: the icon sat inline with the text, the timestamp ran straight into the
   username, and the record count floated loose on the right of whatever line it
   happened to land on.

   It is drawn as a timeline instead, because that is what a deletion trail is:
   each row has an icon chip on a continuous left rail, so consecutive entries
   read as a sequence rather than as a list of unrelated cards. The rail is the
   row's own `::before`, so it needs no extra markup and no wrapper element —
   which matters here, because a wrapper div opened in one `st.markdown` call and
   closed in another cannot nest (see the note on `.data-table-header`).

   The icon tint arrives from Python as an inline `style="color:..."`, so the
   chip background is derived from it with `color-mix`, keeping the Python side
   to a single source of truth for "delete vs restore" rather than two parallel
   lists of the same decision. */
.audit-log-row {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: .85rem;
    background: var(--navy-card);
    border: 1px solid var(--navy-border);
    border-radius: var(--radius-sm);
    padding: .8rem 1rem .8rem 2.6rem;
    margin-bottom: .45rem;
    transition: border-color var(--dur-2) var(--ease-standard),
                box-shadow var(--dur-2) var(--ease-standard),
                transform var(--dur-2) var(--ease-standard);
}
.audit-log-row::before {
    content: '';
    position: absolute;
    left: 1.15rem;
    top: 2.55rem;
    bottom: -.45rem;
    width: 2px;
    background: linear-gradient(180deg, var(--navy-border2), transparent);
}
/* The last row has nothing below it, so the rail stops at its own centre. */
.audit-log-row:last-of-type::before { display: none; }
.audit-log-row:hover {
    border-color: var(--navy-border2);
    box-shadow: var(--shadow-sm);
    transform: translateX(2px);
}

.audit-log-icon {
    position: absolute;
    left: .6rem;
    top: .7rem;
    width: 30px; height: 30px;
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, currentColor 12%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, currentColor 26%, transparent);
}
.audit-log-body { min-width: 0; flex: 1 1 auto; }
.audit-log-title {
    font-size: .85rem;
    font-weight: 600;
    color: var(--text-1);
    line-height: 1.4;
}
.audit-log-title strong { font-weight: 800; }
/* Actor and timestamp sit on their own line rather than inline: at 320px the
   single-line version put the timestamp straight after the username with no
   room to break, which is how it read before. */
.audit-log-meta {
    display: block;
    margin-top: 2px;
    font-size: var(--fs-2xs);
    color: var(--text-3);
    font-weight: 500;
}
.audit-log-reason {
    margin-top: .4rem;
    padding-left: .6rem;
    border-left: 2px solid var(--navy-border);
    font-size: var(--fs-xs);
    color: var(--text-2);
    line-height: 1.55;
}
/* Now a flex row of chips: the record count, then the retention countdown.
   It was a single pill holding one value, so this had to become a row rather
   than have the countdown appended inside the same border. */
.audit-log-stats {
    display: flex;
    align-items: center;
    gap: .35rem;
    flex-shrink: 0;
    align-self: center;
    white-space: nowrap;
    font-size: var(--fs-2xs);
    font-weight: 700;
    color: var(--text-3);
    background: var(--navy-card2);
    border: 1px solid var(--navy-border);
    border-radius: 999px;
    padding: .2rem .6rem;
}

/* "N days left to restore" — the deadline until a deletion can still be undone.
   It gets its own chip because it has three states, and severity is driven by
   days remaining rather than by absolute age: what the number is for is deciding
   whether to act now, so 1 day and 0 days are both urgent in the way that
   matters, whatever the calendar says.

   Every colour clears 4.5:1 against its OWN tinted background, not merely
   against white — measured, not eyeballed: --text-2 is 5.8:1 on the grey tint,
   #92400e is 6.4:1 on the gold tint, #b91c1c is 5.5:1 on the red tint.
   --gold-text (#b45309) was tried first for the urgent state and came out at
   4.50:1 on that tint, which is too close to the floor to ship. */
.audit-log-countdown {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: .1rem .5rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
}
.audit-log-countdown.is-normal {
    background: rgba(15, 23, 42, 0.04);
    color: var(--text-2);
}
.audit-log-countdown.is-urgent {
    background: rgba(217, 119, 6, 0.10);
    color: #92400e;
}
.audit-log-countdown.is-critical {
    background: rgba(220, 38, 38, 0.10);
    color: #b91c1c;
}

/* ── DELETE-CONFIRMATION INSTRUCTION ──
   Also unstyled until now: the two prompts above the confirmation text inputs
   ("type <username> exactly", "also type <phrase>") rendered as bare body text
   at the same weight as everything around them, so the single most important
   instruction on the page looked like a caption. */
.confirm-instruction {
    margin: .6rem 0 .2rem;
    padding: .6rem .85rem;
    border-radius: var(--radius-sm);
    background: rgba(37,99,235,.06);
    border: 1px solid rgba(37,99,235,.18);
    border-left: 3px solid var(--accent);
    font-size: var(--fs-sm);
    line-height: 1.6;
    color: var(--text-2);
}
.confirm-instruction strong { color: var(--text-1); font-weight: 700; }
.confirm-instruction code {
    background: var(--navy-card2);
    border: 1px solid var(--navy-border2);
    border-radius: 5px;
    padding: .05rem .35rem;
    font-size: .92em;
    font-weight: 600;
    color: var(--text-1);
}

.um-row-main { display: flex; align-items: center; gap: .7rem; min-width: 0; flex: 1 1 auto; }
.um-row-avatar {
    width: 34px; height: 34px; flex-shrink: 0;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
    color: #fff; font-size: .74rem; font-weight: 700; letter-spacing: .02em;
}
.um-row.is-admin .um-row-avatar { background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); }
.um-row-text { min-width: 0; }
.um-row-name {
    font-size: .85rem; font-weight: 600; color: var(--text-1);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.um-row-sub {
    font-size: var(--fs-2xs); color: var(--text-3);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.um-row-stats { display: flex; align-items: center; gap: .4rem; flex-shrink: 0; }
.um-row-stat {
    font-size: var(--fs-2xs); font-weight: 600; color: var(--text-2);
    background: var(--navy-card2); border: 1px solid var(--navy-border);
    border-radius: 999px; padding: .18rem .55rem; white-space: nowrap;
}
.um-row-stat.is-linked { color: #2563eb; border-color: rgba(37,99,235,.24); background: rgba(37,99,235,.06); }

.um-role-badge {
    display: inline-flex; align-items: center; gap: .25rem;
    font-size: var(--fs-2xs); font-weight: 700; text-transform: uppercase;
    letter-spacing: .06em; border-radius: 999px; padding: .16rem .5rem;
    white-space: nowrap;
}
.um-role-badge.role-admin { color: #7c3aed; background: rgba(124,58,237,.09); border: 1px solid rgba(124,58,237,.24); }
.um-role-badge.role-student { color: #2563eb; background: rgba(37,99,235,.09); border: 1px solid rgba(37,99,235,.24); }
.um-tag {
    display: inline-flex; align-items: center; gap: .22rem;
    font-size: var(--fs-2xs); font-weight: 600; border-radius: 999px;
    padding: .16rem .5rem; white-space: nowrap;
}
.um-tag.tag-protected { color: #b45309; background: rgba(217,119,6,.1); border: 1px solid rgba(217,119,6,.26); }
.um-tag.tag-self { color: #dc2626; background: rgba(220,38,38,.08); border: 1px solid rgba(220,38,38,.24); }
.um-tag.tag-seeded { color: #64748b; background: var(--navy-card2); border: 1px solid var(--navy-border2); }
.um-tag.tag-linked { color: #2563eb; background: rgba(37,99,235,.08); border: 1px solid rgba(37,99,235,.22); }
.um-tag.tag-clean { color: var(--green-text); background: rgba(5,150,105,.08); border: 1px solid rgba(5,150,105,.22); }

/* ═══════════════════════════
   USER MANAGEMENT — DANGER ZONE
   ═══════════════════════════ */
.danger-zone {
    background: linear-gradient(180deg, rgba(220,38,38,.05) 0%, rgba(220,38,38,.015) 100%);
    border: 1px solid rgba(220,38,38,.28);
    border-radius: var(--radius);
    padding: 1.1rem 1.15rem;
    margin-top: .4rem;
    margin-bottom: 1rem;
}
.danger-banner {
    display: flex; align-items: flex-start; gap: .65rem;
    background: rgba(220,38,38,.07);
    border: 1px solid rgba(220,38,38,.22);
    border-left: 3px solid var(--red);
    border-radius: var(--radius-sm);
    padding: .8rem .95rem;
    margin-bottom: 1rem;
    font-size: .82rem;
    line-height: 1.55;
    color: #991b1b;
}
.danger-banner > svg { flex-shrink: 0; margin-top: .12rem; }
.danger-banner strong { color: #7f1d1d; }

.confirm-summary {
    background: var(--navy-card2);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius-sm);
    padding: .3rem .1rem;
    margin: .5rem 0 1rem;
    max-height: 340px;
    overflow-y: auto;
}
.confirm-row {
    display: flex; align-items: baseline; gap: .75rem;
    padding: .5rem .85rem;
    border-bottom: 1px solid var(--navy-border);
}
.confirm-row:last-child { border-bottom: none; }
.confirm-row-key {
    font-size: .7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .07em; color: var(--text-3);
    flex: 0 0 42%; min-width: 0;
}
.confirm-row-val {
    font-size: .82rem; color: var(--text-1); font-weight: 500;
    flex: 1 1 auto; min-width: 0;
    word-break: break-word; overflow-wrap: anywhere;
}
.confirm-note {
    display: flex; align-items: flex-start; gap: .5rem;
    font-size: .76rem; color: var(--text-2);
    background: var(--navy-card2);
    border: 1px dashed var(--navy-border2);
    border-radius: var(--radius-sm);
    padding: .65rem .85rem; margin: .75rem 0;
    line-height: 1.5;
}
.confirm-note > svg { flex-shrink: 0; margin-top: .1rem; }

@media screen and (max-width: 576px) {
    .um-filter-bar { flex-direction: column; align-items: stretch; }
    .confirm-row { flex-direction: column; gap: .15rem; }
    .confirm-row-key { flex: 1 1 auto; }
    .um-row { flex-wrap: wrap; }
    .um-row-stats { width: 100%; justify-content: flex-start; }

    /* ── Deletion audit trail on a phone ──
       `.audit-log-row` is a three-part flex row: icon rail, body, and a
       `white-space: nowrap` stat chip pinned to the right. At 360px that
       leaves the body about 200px once the 2.6rem left indent is taken, and
       the timestamp has nowhere to break. The stat chip drops to its own line
       instead of being squeezed, and the left indent shrinks so the rail
       stops eating a third of the width on a 320px screen. */
    .audit-log-row {
        flex-wrap: wrap;
        padding: .75rem .8rem .7rem 2.2rem;
    }
    .audit-log-icon {
        left: .45rem;
        width: 26px; height: 26px;
    }
    .audit-log-row::before { left: .95rem; }
    .audit-log-stats {
        margin-top: .5rem;
        margin-left: 0;
        align-self: flex-start;
    }
    .confirm-instruction { padding: .55rem .7rem; }
}

/* ══════════════════════════════════════════════════════════════
   GRADIENT-TEXT FALLBACK

   Three rules set `-webkit-text-fill-color: transparent` to reveal a
   `background-clip: text` gradient: `.page-header h1` and
   `.login-title-gradient`. `background-clip: text` is the whole trick — with
   it unsupported, `text-fill-color: transparent` still applies and the
   heading renders invisible, i.e. the page title and the login wordmark
   simply vanish. Supported everywhere modern, but the failure mode is
   "no title", so it gets a real fallback rather than an assumption.

   `color:` is set alongside in each rule already, so the fallback only has to
   undo the fill.
   ══════════════════════════════════════════════════════════════ */
@supports not ((background-clip: text) or (-webkit-background-clip: text)) {
    .page-header h1 {
        background: none;
        -webkit-text-fill-color: var(--text-1) currentColor;
        color: var(--text-1);
        animation: none;
    }
    .login-title-gradient {
        background: none;
        -webkit-text-fill-color: #4C5FD7 currentColor;
        color: #4C5FD7;
        animation: none;
    }
}

/* ══════════════════════════════════════════════════════════════
   REDUCED MOTION (U-11)

   This stylesheet runs six infinite animations with no opt-out: the page
   header's 8s background sweep, the h1's 6s gradient shimmer, the login
   wordmark's 4s shimmer, the status dot's 1.8s pulse, the engine dot's 2s
   pulse, and (until this pass) a 2.5s card float. For a visitor who has asked
   their operating system to reduce motion, that is exactly the perpetual
   large-area movement the setting exists to suppress, and it is also the
   single biggest continuous-repaint cost in the app — every one of those
   animations runs on every page, forever, whether or not anyone is looking
   at the element.

   The override has to come last in the file to win on source order, so it
   sits here rather than next to the animations it cancels.

   `animation: none` alone is not enough: a rule that animates `transform` and
   a rule that sets `transform` are different properties of the element, and
   killing the animation restores whatever `transform` was declared — which
   for `.metric-card:hover` is the hover lift. So transitions are collapsed as
   well, and the decorative pseudo-elements that only *became* visible on
   hover are left at their final state rather than mid-sweep.
   ══════════════════════════════════════════════════════════════ */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 1ms !important;
        animation-iteration-count: 1 !important;
        animation-delay: 0ms !important;
        transition-duration: 1ms !important;
        transition-delay: 0ms !important;
        scroll-behavior: auto !important;
    }

    /* Name each looping animation explicitly rather than trusting the blanket
       rule above: `animation-duration: 1ms` still lets a `fill-mode` or a
       delay leave the element offset, and these five are the ones that
       actually move something a user can see. */
    .page-header::after,
    .page-header h1,
    .login-title-gradient,
    .pulse-dot,
    .login-scroll-hint .lc-ico,
    .engine-indicator-dot {
        animation: none !important;
    }

    /* These two gradients exist only as a moving sheen. With motion off they
       are a flat tint, which is all they ever actually communicated.

       The tint has to be declared with `background-image`, NEVER the
       `background` shorthand. The shorthand resets `background-clip` to its
       initial value, `border-box`, and that single reset is what turned the
       page title into an unreadable navy box: with the gradient no longer
       clipped to the glyphs it painted as a solid rectangle, and the
       `-webkit-text-fill-color: var(--text-1)` below put dark text on top of
       it. The animated rule at the top of this file gets this right only
       because it also re-declares `-webkit-background-clip: text` on the next
       line — this one did not.

       The two `@supports` blocks make the trade explicit rather than
       assumed: where the clip works the title keeps its gradient and simply
       stops shimmering, and where it does not the gradient is dropped for a
       solid colour so the title can never go invisible. */
    @supports ((background-clip: text) or (-webkit-background-clip: text)) {
        .page-header h1 {
            background-image: linear-gradient(135deg, #0f172a 30%, #2563eb 65%, #7c3aed 100%) !important;
            background-size: 200% auto !important;
            -webkit-background-clip: text !important;
            background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            color: var(--text-1) !important;
        }
    }
    @supports not ((background-clip: text) or (-webkit-background-clip: text)) {
        .page-header h1 {
            background: none !important;
            -webkit-text-fill-color: currentColor !important;
            color: var(--text-1) !important;
        }
    }
    .login-title-gradient {
        -webkit-text-fill-color: #4C5FD7 !important;
        color: #4C5FD7 !important;
    }

    /* Hover lifts are instant, not absent — the affordance still has to read. */
    .metric-card:hover,
    .cat-card:hover,
    .insight-card:hover,
    .login-feature-card:hover,
    .stButton > button:hover,
    .stFormSubmitButton > button:hover,
    [data-testid^="stBaseButton"]:hover {
        transform: none !important;
    }
}
/* ══════════════════════════════════════════════════════════════════════
   PREMIUM CHART CARD
   ══════════════════════════════════════════════════════════════════════

   Replaces the `.chart-wrap` pattern that never actually worked. Those call
   sites opened the div in one `st.markdown` and closed it in another, and
   Streamlit closes the markup at the end of each element — so the wrapper was
   always empty and every chart sat on the bare page. See the note on
   `chart_card` in `app_pages/targets.py`.

   The card is now a real `st.container(border=True, key="stChartCard…")`, and it
   is matched through that key rather than through Streamlit's own border
   wrapper. A `key` beginning with `st` becomes the element's `data-testid`, so
   this is a hook on the element we actually rendered; an internal wrapper name
   is undocumented and can be renamed between releases, and a selector that
   matches nothing removes the frame silently. `tests/test_css.py` checks every
   `data-testid` here against the real frontend bundle, so a wrong name fails
   the build rather than the page.

   The frame layered on top: a soft shadow, a gradient hairline along the top
   edge, and a hairline under the title row.
   */
[data-testid^="stChartCard"] {
    background: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius-lg);
    box-shadow: 0 1px 2px rgba(15, 23, 42, .04), 0 8px 28px rgba(15, 23, 42, .05);
    transition: border-color var(--dur-2) ease, box-shadow var(--dur-2) ease,
                transform var(--dur-2) ease;
    overflow: hidden;
    position: relative;
}

/* Lift, and warm the border, on hover. Pointer-only: a hover lift on touch
   sticks after a tap and leaves the card permanently raised. */
@media (hover: hover) and (pointer: fine) {
    [data-testid^="stChartCard"]:hover {
        border-color: rgba(37, 99, 235, .28);
        box-shadow: 0 2px 4px rgba(15, 23, 42, .05), 0 14px 38px rgba(37, 99, 235, .10);
        transform: translateY(-2px);
    }
}

/* The gradient hairline along the top edge. Painted rather than bordered so it
   can fade out at both ends instead of stopping at the corners. */
[data-testid^="stChartCard"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg,
        rgba(37, 99, 235, 0) 0%,
        rgba(37, 99, 235, .55) 22%,
        rgba(124, 58, 237, .55) 62%,
        rgba(37, 99, 235, 0) 100%);
    opacity: .5;
    transition: opacity var(--dur-3) ease;
    pointer-events: none;
}

@media (hover: hover) and (pointer: fine) {
    [data-testid^="stChartCard"]:hover::before {
        opacity: 1;
    }
}

[data-testid^="stChartCard"] > div:first-child {
    padding: 0;
}

/* ── the title row ─────────────────────────────────────────────────── */
.chart-card-head {
    display: flex;
    align-items: center;
    gap: .55rem;
    padding: 1rem 1.35rem .8rem;
    border-bottom: 1px solid var(--navy-border2);
    background: linear-gradient(180deg,
        rgba(248, 250, 252, .95) 0%, rgba(255, 255, 255, 0) 100%);
}

.chart-card-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.9rem; height: 1.9rem;
    border-radius: .6rem;
    background: rgba(37, 99, 235, .10);
    border: 1px solid rgba(37, 99, 235, .18);
    color: #2563eb;
    flex-shrink: 0;
}

.chart-card-title {
    font-size: .78rem;
    font-weight: 700;
    letter-spacing: .10em;
    text-transform: uppercase;
    color: var(--text-2);
}

/* ── the plot ────────────────────────────────────────────────────────
   Streamlit gives every Plotly figure its own toolbar/plot div; removing the
   default padding inside the card is what stops the chart looking like it is
   floating inside a box rather than filling it. */
[data-testid^="stChartCard"] .js-plotly-plot,
[data-testid^="stChartCard"] [data-testid="stPlotlyChart"] {
    border-radius: 0 0 calc(var(--radius-lg) - 1px) calc(var(--radius-lg) - 1px);
}

/* ══════════════════════════════════════════════════════════════════════
   THE BAND SPLIT
   ── The Positive / Neutral / Negative counts on a category card.

   These are the numbers the card's label is derived from. They sit directly
   under the average for a reason: the average is the figure most likely to
   mislead (one angry student and one delighted one average to an
   unremarkable 3.5), and the three counts are what cannot mislead. Showing
   them next to the percentage means the label can be checked at a glance
   instead of being taken on trust.
   ══════════════════════════════════════════════════════════════════════ */

.insight-split {
    display: flex;
    flex-wrap: wrap;
    gap: .4rem;
    margin-top: .7rem;
}

.insight-split-pill {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    padding: .25rem .6rem;
    border-radius: 999px;
    font-size: .7rem;
    font-weight: 600;
    white-space: nowrap;
}

.insight-split-pill strong {
    font-weight: 800;
    font-variant-numeric: tabular-nums;
}

/* The note that appears only when the ratings genuinely disagree — both a
   negative and a positive response in the same category. It states that the
   average is not describing anybody, rather than leaving the reader to work
   out why 3.5 sits next to "50% negative". */
.insight-split-note {
    display: flex;
    align-items: flex-start;
    gap: .5rem;
    margin-top: .7rem;
    padding: .6rem .75rem;
    border-radius: 8px;
    background: rgba(245, 158, 11, .06);
    border: 1px solid rgba(245, 158, 11, .25);
    font-size: .72rem;
    line-height: 1.5;
    color: var(--text-2);
}

.insight-split-note svg {
    flex-shrink: 0;
    margin-top: .12rem;
}

/* ══════════════════════════════════════════════════════════════════════
   PLAYBOOK LIST
   ── The "what to do about it" steps under each Decision Insights card.

   A numbered list rather than another paragraph: the three steps are ordered
   by when they matter, and a paragraph reads as one block of advice where a
   reader needs to see that reading the evidence comes before deciding anything.
   ══════════════════════════════════════════════════════════════════════ */
.playbook-list {
    margin: .7rem 0 .2rem;
    padding-left: 0;
    list-style: none;
    counter-reset: playbook;
    display: flex;
    flex-direction: column;
    gap: .45rem;
}

.playbook-list li {
    counter-increment: playbook;
    position: relative;
    padding-left: 1.9rem;
    font-size: .8rem;
    line-height: 1.55;
    color: var(--text-2);
}

.playbook-list li::before {
    content: counter(playbook);
    position: absolute;
    left: 0; top: .05rem;
    width: 1.45rem; height: 1.45rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(37, 99, 235, .10);
    border: 1px solid rgba(37, 99, 235, .20);
    color: #2563eb;
    /* Held at the 0.7rem floor rather than shrunk for a single digit. The
       digit is the only content here and 11.2px is the project's smallest
       permitted step, so a "1" in a smaller circle would be the one piece of
       text in the UI below it. */
    font-size: .7rem;
    font-weight: 700;
    font-family: var(--font-sans, "Segoe UI", sans-serif);
}

@media (max-width: 700px) {
    .playbook-list li { padding-left: 1.8rem; font-size: .78rem; }
    /* The badge keeps its floor on phones too — the circle grows instead. */
    .playbook-list li::before { width: 1.35rem; height: 1.35rem; }
}

/* Shown in place of a chart when a builder returns None, so the card keeps its
   shape rather than leaving a titled empty box on the page. */
.chart-card-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 7rem;
    margin: 1.1rem 1.35rem;
    border: 1px dashed var(--navy-border2);
    border-radius: var(--radius-md, 12px);
    background: var(--navy-card2);
    color: var(--text-3);
    font-size: .8rem;
    text-align: center;
    padding: 1rem;
}

/* ── phone ───────────────────────────────────────────────────────────
   The card keeps its radius but loses the lift: on a touch device the hover
   state never clears, so the shadow would sit raised forever. */
@media (max-width: 700px) {
    [data-testid^="stChartCard"] {
        border-radius: var(--radius-md, 12px);
        transform: none !important;
    }
    .chart-card-head { padding: .85rem 1rem .7rem; }
    .chart-card-empty { margin: .9rem 1rem; }
}

/* ── reduced motion ────────────────────────────────────────────────────
   The lift is a transform, so it has to be cancelled here explicitly: a
   transition on a property the user has asked us not to animate still runs on
   some engines. */
@media (prefers-reduced-motion: reduce) {
    [data-testid^="stChartCard"] {
        transition: border-color var(--dur-2) ease, box-shadow var(--dur-2) ease;
    }
    [data-testid^="stChartCard"]:hover {
        transform: none;
    }
}

/* ══════════════════════════════════════════════════════════════
   EXECUTIVE DASHBOARD & DECISION SUPPORT SYSTEM UPGRADES
   ══════════════════════════════════════════════════════════════ */

/* Category performance progress meter */
.cat-meter-track {
    height: 6px;
    background: var(--navy-border);
    border-radius: 999px;
    overflow: hidden;
    margin-top: .4rem;
    width: 100%;
    max-width: 240px;
}
.cat-meter-fill {
    height: 100%;
    border-radius: 999px;
    transition: width var(--dur-4) var(--ease-standard);
}

/* Metric card header & delta rows */
.metric-top-badge {
    position: absolute;
    top: .6rem;
    right: .75rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    padding: .15rem .5rem;
    border-radius: 999px;
    background: rgba(15,23,42,.05);
    color: var(--text-3);
    border: 1px solid var(--navy-border);
}
.metric-delta-row {
    font-size: var(--fs-2xs);
    color: var(--text-3);
    margin-top: .45rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: .25rem;
}

/* Sidebar institutional department tag */
.sidebar-dept-tag {
    font-size: var(--fs-2xs);
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--blue-text);
    margin-top: .4rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: .3rem;
}

/* Action plan matrix table in Decision Insights */
.action-matrix-card {
    background: var(--navy-card);
    border: 1px solid var(--navy-border2);
    border-radius: var(--radius-lg);
    padding: 1.4rem 1.6rem;
    margin-top: 1.2rem;
    margin-bottom: 1.4rem;
    box-shadow: var(--shadow-sm);
    position: relative;
    overflow: hidden;
}
.action-matrix-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #2563eb, #7c3aed, #059669);
}
.action-matrix-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.1rem;
    flex-wrap: wrap;
    gap: .5rem;
}
.action-matrix-title {
    font-size: .95rem;
    font-weight: 700;
    color: var(--text-1);
    display: flex;
    align-items: center;
    gap: .45rem;
}
.action-matrix-subtitle {
    font-size: var(--fs-2xs);
    color: var(--text-3);
}
.action-matrix-row {
    display: grid;
    grid-template-columns: 200px 140px 1fr 140px;
    gap: 1rem;
    align-items: center;
    padding: .85rem .95rem;
    background: var(--navy-card2);
    border: 1px solid var(--navy-border);
    border-radius: var(--radius-sm);
    margin-bottom: .6rem;
    transition: background-color var(--dur-2) ease, border-color var(--dur-2) ease;
}
.action-matrix-row:hover {
    background: rgba(37,99,235,.03);
    border-color: rgba(37,99,235,.25);
}
.action-matrix-cat {
    font-size: .88rem;
    font-weight: 700;
    color: var(--text-1);
    display: flex;
    align-items: center;
    gap: .5rem;
}
.action-matrix-badge {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
    padding: .2rem .6rem;
    border-radius: 999px;
    white-space: nowrap;
}
.action-matrix-note {
    font-size: .8rem;
    color: var(--text-2);
    line-height: 1.5;
    word-break: break-word;
}
.action-matrix-meta {
    font-size: var(--fs-2xs);
    color: var(--text-3);
    text-align: right;
    line-height: 1.4;
}
.action-matrix-status {
    display: inline-flex;
    align-items: center;
    gap: .25rem;
    font-size: var(--fs-2xs);
    font-weight: 700;
    padding: .15rem .5rem;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: .06em;
}
.action-matrix-status.is-resolved {
    background: rgba(5,150,105,.1);
    color: var(--green-text);
    border: 1px solid rgba(5,150,105,.25);
}
.action-matrix-status.is-progress {
    background: rgba(37,99,235,.1);
    color: var(--blue-text);
    border: 1px solid rgba(37,99,235,.25);
}
.action-matrix-status.is-pending {
    background: rgba(217,119,6,.1);
    color: var(--gold-text);
    border: 1px solid rgba(217,119,6,.25);
}

/* Tab introduction banner */
.tab-intro-card {
    background: var(--navy-card2);
    border: 1px solid var(--navy-border);
    border-radius: var(--radius-sm);
    padding: .85rem 1.15rem;
    margin-bottom: 1.1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}
.tab-intro-text {
    font-size: .84rem;
    color: var(--text-2);
    line-height: 1.55;
    flex: 1 1 auto;
    min-width: 240px;
}
.tab-intro-text strong {
    color: var(--text-1);
}

/* Executive briefing export card */
.exec-briefing-card {
    background: linear-gradient(135deg, rgba(37,99,235,.06) 0%, rgba(124,58,237,.04) 100%);
    border: 1px solid rgba(37,99,235,.2);
    border-radius: var(--radius-lg);
    padding: 1.4rem 1.8rem;
    margin-top: 1rem;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
}
.exec-briefing-info {
    flex: 1 1 auto;
    min-width: 240px;
}
.exec-briefing-title {
    font-size: 1rem;
    font-weight: 800;
    color: var(--text-1);
    margin-bottom: .25rem;
    display: flex;
    align-items: center;
    gap: .45rem;
}
.exec-briefing-desc {
    font-size: .82rem;
    color: var(--text-2);
    line-height: 1.5;
}

@media screen and (max-width: 768px) {
    .action-matrix-row {
        grid-template-columns: 1fr !important;
        gap: .5rem !important;
    }
    .action-matrix-meta {
        text-align: left !important;
    }
    .cat-meter-track {
        max-width: 100% !important;
    }
}
</style>
"""
