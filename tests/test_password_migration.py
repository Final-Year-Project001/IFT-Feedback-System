"""Regression gate for the mandatory password-change hold (legacy SHA-256 rows).

Why this file exists at all
---------------------------
Accounts created by the first release of this project store an *unsalted*
SHA-256 digest. `db.verify_password` still accepts one — otherwise those
accounts would be locked out of a system they were already using — so the
exposure is silent: nothing fails, the row just stays cheap to attack with
precomputed tables for as long as nobody changes the password.

The first fix for this re-hashed the hash on a successful login. That upgraded
the storage and changed nothing about the account's security in practice: the
user kept the same password they had already reused everywhere else, and
"fixing the hash" looked like a completed migration while the weak secret
lived on. Worse, it destroyed the only signal that there was anything to do —
once re-hashed, nothing could tell that this account had ever been legacy.

So login no longer upgrades anything. The user authenticates, is then held on
a mandatory change screen, and picks a new password themselves. That fixes
storage *and* habit, and it needs no admin action to remember.

The three things most likely to rot, all covered below:

1. Login must not go back to silently re-hashing. If it does, the hold never
   appears, because the row is already PBKDF2 by the time `main()` checks it.
2. `db.password_is_legacy` must agree with `db.verify_password` about what
   "legacy" means, including on rows with a missing or empty hash.
3. The hold must be *structural*. A banner with a "remind me later" is not a
   hold; `main()` has to return before the sidebar renders, so there is
   nothing to navigate to.

Runs against a COPY of the live database. Real accounts are never touched.

Run: .venv\\Scripts\\python.exe tests\\test_password_migration.py
"""
import hashlib
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_pwm_")
# Not `shutil.copy2`: the live file is in WAL mode, so a plain file copy drops
# every commit since the last checkpoint. This suite's central claim is about
# which hash format a row holds, and a stale copy has different rows entirely.
COPY = snapshot_live_db(TMP)

import streamlit as st  # noqa: E402

import db  # noqa: E402

db.DB_PATH = COPY
st.cache_resource.clear()
db.get_db.clear()

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(ROOT, "app.py")

LEGACY_USER = "legacymig"
LEGACY_PASS = "legacySecret123"
LEGACY_HASH = hashlib.sha256(LEGACY_PASS.encode("utf-8")).hexdigest()
NEW_PASS = "aBrandNewPassphrase9"

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}"
          f"{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


def reset_legacy_row():
    conn = db.get_db()
    conn.execute(
        "INSERT OR REPLACE INTO users "
        "(username, email, full_name, password_hash, role, level, created_at) "
        "VALUES (?,?,?,?,?,?,datetime('now'))",
        (LEGACY_USER, "legacy@test.local", "Legacy Tester",
         LEGACY_HASH, "admin", "staff"),
    )
    conn.commit()


def signed_in_at(**extra):
    """An AppTest already past authentication but on a legacy row."""
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.session_state["password_correct"] = True
    at.session_state["username"] = LEGACY_USER
    at.session_state["user"] = {
        "name": "Legacy Tester", "role": "admin", "level": "staff",
        "email": "legacy@test.local",
    }
    for k, v in extra.items():
        at.session_state[k] = v
    return at


def body_text(at):
    """Everything the page actually renders, minus the injected stylesheet.

    The `<style>` blocks are excluded on purpose. `body_text` is used to assert
    that a given admin screen did *not* render, by looking for its navigation
    label — and the global stylesheet is present on every page, including the
    held screen. A CSS comment that happens to name a page therefore reads as
    that page having rendered.

    That is not hypothetical: adding one line to `styles.py` mentioning
    "Decision Insights" made this suite fail with the dashboard nowhere in
    sight. A stylesheet is document furniture, not rendered content, so it is
    filtered out here and the navigation checks mean what they say.
    """
    parts = [m.value for m in at.markdown
             if not str(m.value).lstrip().startswith("<style")]
    parts += [e.value for e in at.error]
    parts += [w.value for w in at.warning]
    parts += [s.value for s in at.success]
    parts += [ti.label for ti in at.text_input]
    return " ".join(str(p) for p in parts)


def errors_of(at):
    return [str(e.value) for e in at.error]


reset_legacy_row()

# ══════════════════════════════════════════════════════════════════════
section("1. Login must not silently re-hash a legacy row")
# ══════════════════════════════════════════════════════════════════════

ok, user = db.verify_login(LEGACY_USER, LEGACY_PASS)
check("a legacy password still authenticates", ok and user is not None)

stored = db.get_user(LEGACY_USER)["password_hash"]
check("the stored hash is STILL the legacy SHA-256 digest after login",
      stored == LEGACY_HASH, f"got {stored[:28]}...")
check("password_is_legacy therefore reports True",
      db.password_is_legacy(LEGACY_USER))
check("a wrong password is still rejected",
      not db.verify_login(LEGACY_USER, "not-the-password")[0])
check("the email path does not upgrade either",
      db.verify_login_by_email("legacy@test.local", LEGACY_PASS)[0]
      and db.get_user(LEGACY_USER)["password_hash"] == LEGACY_HASH)

# ══════════════════════════════════════════════════════════════════════
section("2. password_is_legacy's edges")
# ══════════════════════════════════════════════════════════════════════

check("an unknown username is not legacy, and does not crash",
      not db.password_is_legacy("no-such-account-xyz"))
check("an empty username is handled",
      not db.password_is_legacy(""))
check("a None username is handled",
      not db.password_is_legacy(None))

conn = db.get_db()
conn.execute(
    "INSERT OR REPLACE INTO users "
    "(username, email, full_name, password_hash, role, level, created_at) "
    "VALUES ('nullhash','n@t.local','Null Hash','','student','100 Level',"
    "datetime('now'))"
)
conn.execute(
    "INSERT OR REPLACE INTO users "
    "(username, email, full_name, password_hash, role, level, created_at) "
    "VALUES ('modern','m@t.local','Modern User',?,'student','100 Level',"
    "datetime('now'))",
    (db.hash_password("alreadyMigrated1"),),
)
conn.commit()

check("an empty stored hash is not legacy (nothing can verify against it)",
      not db.password_is_legacy("nullhash"))
check("a PBKDF2 row is not legacy",
      not db.password_is_legacy("modern"))
check("and that row still authenticates",
      db.verify_login("modern", "alreadyMigrated1")[0])

# ══════════════════════════════════════════════════════════════════════
section("3. main() holds the user — structurally")
# ══════════════════════════════════════════════════════════════════════

# No `must_change_password` flag set at all. The gate must derive it from the
# row, so a session restored from a browser token (or any path that never went
# through `_establish_session`) is held too.
at = signed_in_at().run()
check("the mandatory screen renders with no flag pre-set",
      "Choose a New Password" in body_text(at), body_text(at)[:150])
check("it explains the reason in plain language",
      "salted hashing" in body_text(at))
check("the sidebar is NOT offered, so there is nothing to navigate to",
      "Full Dashboard" not in body_text(at)
      and "Decision Insights" not in body_text(at))
check("no admin page body rendered behind it",
      "Deletion Audit Trail" not in body_text(at))
check("no uncaught exception", not at.exception,
      [str(e.value) for e in at.exception])

# The decision must come from the row and ONLY from the row. An earlier
# version also honoured a session_state flag, so a stale flag kept holding an
# account that had already been upgraded — a loop the user could not leave,
# because completing the screen was the thing that cleared the flag.
conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
             (db.hash_password("alreadyMigrated1"), LEGACY_USER))
conn.commit()
at = signed_in_at(must_change_password=True).run()
check("a stale session flag cannot hold an already-upgraded account",
      "Choose a New Password" not in body_text(at), body_text(at)[:150])
app_src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
check("main() never reads a session flag to decide the hold",
      "must_change_password" not in app_src.split("def main():", 1)[1])
check("nor does _restore_session",
      "must_change_password" not in app_src.split("def _restore_session", 1)[1]
      .split("def _forget_session", 1)[0])
check("and the flag is not written anywhere in the codebase",
      not any(
          "must_change_password" in open(p, encoding="utf-8", errors="replace").read()
          for p in [
              os.path.join(ROOT, f)
              for f in os.listdir(ROOT) if f.endswith(".py")
          ]
      ))
reset_legacy_row()

# ══════════════════════════════════════════════════════════════════════
section("4. completing the change clears the hold")
# ══════════════════════════════════════════════════════════════════════

at = signed_in_at().run()
# Two password fields: new + confirm.
fields = [ti for ti in at.text_input if "assword" in (ti.label or "")]
check("the form asks for a new password and a confirmation",
      len(fields) >= 2, [ti.label for ti in at.text_input])

fields[0].set_value(NEW_PASS)
fields[1].set_value(NEW_PASS)
submit = [b for b in at.button if "Continue" in (b.label or "")]
check("there is a submit button", bool(submit),
      [b.label for b in at.button])
submit[0].click()
at.run()

stored = db.get_user(LEGACY_USER)["password_hash"]
check("the stored hash is now PBKDF2", stored.startswith("pbkdf2:sha256:"),
      stored[:30])
check("the salt is per-row, not shared",
      db.get_user(LEGACY_USER)["password_hash"].split("$")[1]
      != db.hash_password(NEW_PASS).split("$")[1])
check("password_is_legacy now reports False",
      not db.password_is_legacy(LEGACY_USER))
check("the new password authenticates",
      db.verify_login(LEGACY_USER, NEW_PASS)[0])
check("the old one no longer does",
      not db.verify_login(LEGACY_USER, LEGACY_PASS)[0])
check("the screen is gone on the run right after the change",
      "Choose a New Password" not in body_text(at), body_text(at)[:150])

after = signed_in_at().run()
check("a fresh session on the upgraded row is not held",
      "Choose a New Password" not in body_text(after))
check("and the dashboard is reachable again",
      "Full Dashboard" in body_text(after) or "Overview" in body_text(after),
      body_text(after)[:150])

# ══════════════════════════════════════════════════════════════════════
section("5. re-using the current password is refused")
# ══════════════════════════════════════════════════════════════════════

reset_legacy_row()
at = signed_in_at().run()
fields = [ti for ti in at.text_input if "assword" in (ti.label or "")]
fields[0].set_value(LEGACY_PASS)
fields[1].set_value(LEGACY_PASS)
[b for b in at.button if "Continue" in (b.label or "")][0].click()
at.run()

check("submitting the same password is rejected",
      any("different one" in e for e in errors_of(at)), errors_of(at))
check("and the row is left untouched",
      db.get_user(LEGACY_USER)["password_hash"] == LEGACY_HASH)

# ══════════════════════════════════════════════════════════════════════
section("6. validation errors stay inline, never modal")
# ══════════════════════════════════════════════════════════════════════

at = signed_in_at().run()
fields = [ti for ti in at.text_input if "assword" in (ti.label or "")]
fields[0].set_value("short")
fields[1].set_value("short")
[b for b in at.button if "Continue" in (b.label or "")][0].click()
at.run()
check("a 5-character password is refused", any("8 characters" in e
                                               for e in errors_of(at)),
      errors_of(at))

at = signed_in_at().run()
fields = [ti for ti in at.text_input if "assword" in (ti.label or "")]
fields[0].set_value("longEnoughPassword1")
fields[1].set_value("longEnoughPassword2")
[b for b in at.button if "Continue" in (b.label or "")][0].click()
at.run()
check("a mismatched confirmation is refused", any("do not match" in e
                                                  for e in errors_of(at)),
      errors_of(at))
check("neither attempt wrote a new hash",
      db.get_user(LEGACY_USER)["password_hash"] == LEGACY_HASH)

# ══════════════════════════════════════════════════════════════════════
section("7. students are held too, not just admins")
# ══════════════════════════════════════════════════════════════════════

conn.execute("UPDATE users SET role='student' WHERE username=?", (LEGACY_USER,))
conn.commit()
at = AppTest.from_file(str(APP), default_timeout=120)
at.session_state["password_correct"] = True
at.session_state["username"] = LEGACY_USER
at.session_state["user"] = {
    "name": "Legacy Tester", "role": "student", "level": "100 Level",
    "email": "legacy@test.local",
}
at.run()
check("a legacy student is held as well",
      "Choose a New Password" in body_text(at), body_text(at)[:150])
check("and offered no student navigation",
      "My Statistics" not in body_text(at))

shutil.rmtree(TMP, ignore_errors=True)

print()
print("=" * 74)
print(f"  {len(failures)} failure(s)" if failures else "  all checks passed")
for f in failures:
    print(f"    - {f}")
print("=" * 74)
sys.exit(1 if failures else 0)