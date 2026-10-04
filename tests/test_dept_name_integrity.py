"""Verify the IT -> IFT rename no longer mangles the pronoun "it".

Guards against the exact regression: a global whole-word `IT` -> `IFT`
find-and-replace also rewrote every English pronoun "it" as the department
name — in code, comments, docstrings, user-facing strings and the guides.
"""
from __future__ import annotations

import ast
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def section(title: str) -> None:
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


SUFFIXES = {".py", ".md", ".txt", ".toml", ".css", ".example"}
SKIP_DIRS = {".venv", "__pycache__", "backup", ".git", "model", ".kilo"}

# Where "IFT" legitimately is the department name or a course code.
GENUINE = re.compile(
    r"FUTO IFT"
    r"|IFT \d"
    r"|IFT Department"
    r"|IFT journal"
    r"|IFT Support"
    r"|IFT programme"
    r"|IFT course"
    r"|IFT admin"
    r"|IFT Dept"
    r"|IFT Feedback"
    r"|IFT Smart"
    r"|IFT students"
    r"|IFT-feedback"
    r"|IFT infrastructure"
    r"|ACADEMIC & IFT",
    re.I,
)

# Cues that mean the word is a pronoun, not a name. Deliberately generous:
# a false positive here only costs a reviewer's eye, while a false negative
# ships "delete it" to a user as "delete IFT".
PRONOUN_CUES = re.compile(
    r"\b(?:without|into|with|about|of|to|for|on|in|by|from|as|and|or|but|than|so|"
    r"because|although|while|when|if|unless|until|whether|per|via|use|uses|used|"
    r"using|keep|keeps|kept|make|makes|made|convert|converts|reintroduce|"
    r"imply|implies|help|helps|helped|leave|leaves|left|moves|move|read|reads|"
    r"carry|carries|carried|render|renders|rendered|wraps|wrapped|reaches|"
    r"reached|needs|need|force|forces|forced|relying|rely|retain|retains|"
    r"return|returns|prefer|prefers|emit|emits|emitted|do|does|did|done|"
    r"deleting|restoring|train|where|find|search|rename|clear|fix|redo|"
    r"drag|click|open|close|run|wait|confirm|check|see|view|prints?|"
    r"proved|hidden|hide|changed?|copy|copies|read|called|calling|adds?|"
    r"swallow|swallows|punish|punishes|penalise|penalises|survive|survives|"
    r"occlude|occludes|substitute|substitutes|give|gives|down|up|out|over|"
    r"before|after|than|inside|beneath|behind|across|through|takes?|took|"
    r"get|gets|got|stop|stops|start|starts|press|paste|record|records)\s+$",
    re.I,
)


SELF = Path(__file__).name


def source_files():
    for p in sorted(ROOT.rglob("*")):
        if p.suffix.lower() not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(ROOT)
        if rel.name.startswith("_"):          # scratch / tooling scripts
            continue
        if rel.name == SELF:                  # this file quotes the damage
            continue
        yield rel, p


# ── 1. No "IFT" left where English wants a pronoun ──
section("1. IFT is never used as a substitute for the pronoun 'it'")

offenders: list[str] = []
for rel, p in source_files():
    for i, line in enumerate(
        p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if "IFT" not in line or GENUINE.search(line):
            continue
        for m in re.finditer(r"IFT", line):
            if PRONOUN_CUES.search(line[: m.start()]):
                offenders.append(f"{rel}:{i}: {line.strip()[:110]}")
                break

check(
    "no line puts IFT where a preposition/verb wants a pronoun",
    not offenders,
    f"{len(offenders)} offender(s)",
)
for o in offenders[:20]:
    print(f"          {o}")

# ── 2. The doubled possessive the first repair pass produced ──
section("2. No doubled possessive ('it's's')")
doubled = [
    f"{rel}:{i}"
    for rel, p in source_files()
    for i, line in enumerate(
        p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    )
    if "it's's" in line
]
check("no \"it's's\" anywhere", not doubled, ", ".join(doubled[:8]))

# ── 3. No accidental whitespace damage from the rewrite ──
section("3. Files still parse and kept their shape")
py = sorted(ROOT.rglob("*.py"))
bad = []
for p in py:
    if any(part in SKIP_DIRS for part in p.parts):
        continue
    try:
        ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as e:
        bad.append(f"{p.relative_to(ROOT)}: {e}")
check("every .py parses", not bad, "; ".join(bad[:5]))

# ── 4. The rename itself is still intact ──
section("4. The department rename itself survived the repair")
cfg = (ROOT / "config.py").read_text(encoding="utf-8", errors="replace")
check("config.py still uses the IFT course codes", "IFT 205" in cfg and "IFT 501" in cfg)
check(
    "no course title repeats the department twice",
    not re.search(r"IFT \d+ [^\"\n]*\bIFT\b (?:Innovation|Infrastructure)", cfg),
)
readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
check("README title still says FUTO IFT", "FUTO IFT" in readme)
check("SETUP_GUIDE title still says FUTO IFT",
      "FUTO IFT" in (ROOT / "SETUP_GUIDE.md").read_text(encoding="utf-8",
                                                       errors="replace"))

# ── 5. The user-facing strings that were wrong are now right ──
section("5. User-facing strings the rename had corrupted")
um = (ROOT / "app_pages" / "user_management.py").read_text(
    encoding="utf-8", errors="replace")
check("delete warning says 'do it', not 'do IFT'",
      "another administrator to do it" in um)
check("last-admin warning says 'Deleting it locks'", "Deleting it locks" in um)
check("seeded-admin warning says 'It is not re-created'", "It is not re-created" in um)
check("danger banner says 'It is not a soft delete'", "It is not a soft delete" in um)

cfg_text = cfg
check("curriculum description says \"where it's falling behind\"",
      "where it's falling behind" in cfg_text)

mail = (ROOT / "email_service.py").read_text(encoding="utf-8", errors="replace")
check("OTP email says 'It expires in'", "It expires in" in mail
      and "IFT expires" not in mail)

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} FAILED: {', '.join(failures)}")
    print("=" * 74)
    sys.exit(1)
print("  all checks passed")
print("=" * 74)
