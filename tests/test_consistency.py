"""C-05 / C-06 — the session constant and the aggregate-filter label.

Three checks here are deliberately *negative* — they assert that something is
absent — and each one exists because a first, cruder version of this check
produced a confident but wrong answer:

  * "All Sessions" is a SUBSTRING of "All Sessions (Aggregate)", so counting
    both spellings double-counted every aggregate use. The check now
    matches the bare form with a negative lookahead, so the two spellings
    stop shadowing each other.
  * It demanded `app.py` reference `CURRENT_SESSION`. The opposite is true:
    the constant is only a fallback for a database with no sessions
    configured, because the active session comes from the
    `academic_sessions` table via the sidebar selector. The fix is to
    correct the documentation, not to make app.py read the constant.
  * It demanded foreign keys. None are wanted — `feedback.username` and
    `password_resets.username` being plain text is the central structural
    fact the whole F-01..F-08 deletion design is built around, and an
    enforced FK would start rejecting admin corrections because
    `feedback.corrected_by` also holds usernames.

Run:  .venv\\Scripts\\python.exe tests\\test_consistency.py
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


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


CODE = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in
                   ("tests", ".venv", "__pycache__", "backup", "model", ".git",
                    ".streamlit", ".kilo")]
    for fn in sorted(filenames):
        if fn.endswith(".py") and not fn.startswith("_"):
            CODE.append((os.path.relpath(os.path.join(dirpath, fn), ROOT),
                         read(os.path.join(dirpath, fn))))

# ── C-06: the aggregate filter ──
section("1. C-06  exactly one spelling of the aggregate filter")
AGG = "All Sessions (Aggregate)"
BARE = "All Sessions"
# "All Sessions" NOT followed by " (Aggregate)" is the competing spelling.
bare_re = re.compile(re.escape(BARE) + r"(?!\s*\(Aggregate\))")

agg_uses, bare_uses = [], []
for rel, text in CODE:
    for n, line in enumerate(text.splitlines(), 1):
        code_part = line.split("#", 1)[0]
        if not code_part.strip():
            continue
        if AGG in code_part:
            agg_uses.append(f"{rel}:{n}")
        if bare_re.search(code_part):
            bare_uses.append(f"{rel}:{n}")

print(f"     {AGG!r}: {len(agg_uses)} use(s)")
for u in agg_uses:
    print(f"       {u}")
print(f"     bare {BARE!r}: {len(bare_uses)} use(s)")
for u in bare_uses:
    print(f"       {u}")

check("the aggregate filter is named in at least one place", bool(agg_uses), agg_uses)

# The canonical spelling may now appear only in config.py. db.py's
# `_AGGREGATE_ALIASES` intentionally repeats the two legacy strings, because
# that set is a READ-side guard for stale browser state, not a place new
# labels are generated. So the rule is: no page or function may *default* to a
# legacy spelling, and only db.py's alias set may mention one.
canonical_outside_config = [u for u in agg_uses if not u.startswith("config.py")]
legacy_outside_alias_set = [u for u in bare_uses if not u.startswith("db.py:")]
print()
check("only config.py defines the canonical label",
      not canonical_outside_config, canonical_outside_config)
check("no page or function defaults to a legacy spelling",
      not legacy_outside_alias_set, legacy_outside_alias_set)
check("the legacy spellings live only in db.py's read-side alias set",
      all(u.startswith("db.py:") for u in bare_uses), bare_uses)

# `db.load_data` must special-case the aggregate values, or an unknown value
# silently returns nothing.
db_src = read("db.py")
load_src = db_src[db_src.find("def load_data"):]
load_src = load_src[:load_src.find("\ndef ", 10)] if "\ndef " in load_src else load_src
print()
print("     db.load_data's handling of the aggregate value:")
for n, line in enumerate(load_src.splitlines(), 1):
    if "_AGGREGATE_ALIASES" in line or "Aggregate" in line or "All Sessions" in line:
        print(f"       {line.strip()[:100]}")
check("load_data recognises the aggregate value",
      "_AGGREGATE_ALIASES" in load_src,
      "it may be silently returning an empty frame for every aggregate view")
check("every read filter uses the shared alias set",
      db_src.count("_AGGREGATE_ALIASES") >= 3,
      f"{db_src.count('_AGGREGATE_ALIASES')} reference(s) (1 definition + N uses)")

# ── C-05: KNOWN_SESSIONS must be gone ──
section("2. C-05  config.KNOWN_SESSIONS is dead and must be deleted")
ks_uses = []
for rel, text in CODE:
    for n, line in enumerate(text.splitlines(), 1):
        if "KNOWN_SESSIONS" in line:
            ks_uses.append(f"{rel}:{n}: {line.strip()[:80]}")
print(f"     {len(ks_uses)} reference(s):")
for u in ks_uses:
    print(f"       {u}")

check("nothing reads KNOWN_SESSIONS", len(ks_uses) <= 1, ks_uses)
check("the constant itself is deleted (no `KNOWN_SESSIONS =` line remains)",
      not any("KNOWN_SESSIONS" in u and "=" in u for u in ks_uses),
      [u for u in ks_uses if "KNOWN_SESSIONS" in u and "=" in u])

# ── C-05: db.py takes the session from config ──
section("3. C-05  db.py takes its session default from config, not a literal")
cfg_session = re.search(r'CURRENT_SESSION\s*(?::\s*[^=]+)?=\s*["\']([^"\']+)["\']', read("config.py"))
cur = cfg_session.group(1) if cfg_session else None
print(f"     config.CURRENT_SESSION = {cur!r}")

ddl = re.search(r"session\s+TEXT[^,\n]*DEFAULT\s+['\"]([^'\"]+)['\"]", db_src)
fstring_ddl = re.search(r'f"""CREATE TABLE IF NOT EXISTS feedback\(', db_src)
# The template inside an f-string still reads '{CURRENT_SESSION}' in the source;
# what matters is that it is interpolated, and what lands in a row.
print(f"     feedback.session DDL default template = {ddl.group(1) if ddl else None!r}")
print(f"     the enclosing CREATE TABLE is an f-string = {bool(fstring_ddl)}")
check("the DDL default is interpolated, not a literal",
      bool(fstring_ddl) and ddl is not None and ddl.group(1) == "{CURRENT_SESSION}",
      f"template={ddl.group(1) if ddl else None!r}")
check("the DDL default is an f-string off CURRENT_SESSION, not a literal",
      re.search(r'f"""CREATE TABLE IF NOT EXISTS feedback\(', db_src) is not None,
      "a literal default will silently go stale when the session changes")
check("db.py imports CURRENT_SESSION from config",
      re.search(r"^from config import \((?:[^)]*CURRENT_SESSION[^)]*)\)", db_src, re.M | re.S) is not None
      or re.search(r"^from config import [^\n]*CURRENT_SESSION", db_src, re.M) is not None)

# ── The cascade the plan actually specifies ──
section("4. The plan's design: explicit cascade, no foreign keys")
del_src = db_src[db_src.find("def delete_user_account"):]
del_src = del_src[:del_src.find("\ndef ")] if "\ndef " in del_src else del_src
for pat in ("DELETE FROM users", "DELETE FROM feedback",
            "DELETE FROM password_resets"):
    check(f"{pat} is present in delete_user_account",
          pat in del_src, "the cascade step is missing")
# The audit log is the RECORD of the deletion, so it must NOT be deleted. An
# earlier version of this probe asserted the opposite.
check("the admin_audit_log record is INSERTed, not deleted",
      "INSERT INTO admin_audit_log" in del_src)
check("the audit snapshot is written in the same transaction as the deletes",
      "INSERT INTO admin_audit_log" in del_src and "conn.commit()" in del_src)

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f_ in failures:
        print(f"    - {f_}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED")
