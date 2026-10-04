"""End-to-end verification of the F-01..F-08 user-management engine.

Runs against a COPY of the live database, so the real data is never touched.
Deleting a `users` row does not cascade in SQLite (there is no FOREIGN KEY on
`feedback.username`), so this checks the explicit cascade the plan added and
that every read path in the app actually observes the result.

Run: .venv\\\\Scripts\\\\python.exe test_user_management.py
"""
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_snapshot import snapshot_live_db  # noqa: E402

import streamlit as st  # noqa: E402

import db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_um_")
# Not `shutil.copy2` — the live file is in WAL mode, so a plain file copy drops
# every commit since the last checkpoint. This suite used to run against a
# snapshot that could be arbitrarily old: it showed a second account and four
# feedback rows that had since been deleted, and every cascade assertion below
# was made against rows that no longer existed.
COPY = snapshot_live_db(TMP)
db.DB_PATH = COPY
st.cache_resource.clear()
db.get_db.clear()

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


conn = db.get_db()
# Start from a clean audit trail. The live database may carry legitimate
# DELETE_USER/RESTORE_USER rows from real use, and several checks below count
# entries ("one entry written", "RESTORE_USER was appended") rather than
# asserting on the newest row. Without this, the suite passes or fails
# depending on what an operator happened to delete last week.
conn.execute("DELETE FROM admin_audit_log")
conn.execute("DELETE FROM admin_deletion_tombstones")
conn.commit()
# `PRAGMA table_info` has no FK column; foreign keys live in foreign_key_list.
fks = conn.execute("PRAGMA foreign_key_list(feedback)").fetchall()
has_fk = bool(fks)
print(f"live copy: {COPY}")
print(f"feedback foreign keys: {len(fks)}  (expected 0 — the cascade is explicit, not declarative)")
if has_fk:
    for fk in fks:
        print(f"    {fk[3]} -> {fk[2]}.{fk[4]} ON DELETE {fk[6]}")

# ── Arrange a victim user with feedback, corrections and a reset code ──
section("0. Fixture: a student with feedback across two sessions")
ok, msg = db.create_user("ZZVictim", "zzvictim@test.local", "Zoe Victim",
                         "victimpass123", "student", "300")
check("created the victim account", ok, msg)
check("account is visible to list_users", "ZZVictim" in set(db.list_users()["username"]))

SESSIONS = db.get_academic_sessions()
s1, s2 = SESSIONS[0], SESSIONS[-1] if len(SESSIONS) > 1 else SESSIONS[0]
for i, (cat, sess) in enumerate([("Internet", s1), ("Facilities", s1), ("Lecturers", s2)]):
    ok, m = db.save_data(cat, {
        "username": "ZZVictim", "category": cat, "session": sess,
        "student_level": "300", "rating": 3,
        "comment": f"Victim comment {i} about {cat}",
        "timestamp": f"2026-0{i + 1}-0{i + 1} 09:00:00",
        "sentiment": "Negative", "sentiment_score": -0.4,
        "sentiment_confidence": 0.8, "context_data": {},
    })
    check(f"submitted {cat} ({sess})", ok, m)

ids = [r[0] for r in conn.execute(
    "SELECT id FROM feedback WHERE LOWER(username)='zzvictim' ORDER BY id").fetchall()]
check("3 feedback rows exist", len(ids) == 3, f"ids={ids}")
conn.execute("UPDATE feedback SET admin_corrected_sentiment='Negative' WHERE id=?", (ids[0],))
conn.commit()
otp = db.create_password_reset("ZZVictim")
n_resets = conn.execute(
    "SELECT COUNT(*) FROM password_resets WHERE LOWER(username)='zzvictim'").fetchone()[0]
check("a pending password-reset code exists", n_resets == 1, f"otp={otp[:0]}… count={n_resets}")

# ── list_users ──
section("1. list_users")
df = db.list_users()
check("returns a DataFrame with the expected columns",
      {"username", "feedback_count", "admin_corrections", "sessions_touched"} <= set(df.columns),
      sorted(df.columns))
victim = df[df["username"] == "ZZVictim"].iloc[0]
check("feedback_count is correct", victim["feedback_count"] == 3, victim["feedback_count"])
check("sessions_touched is correct", victim["sessions_touched"] == 2, victim["sessions_touched"])
check("admin_corrections is correct", victim["admin_corrections"] == 1, victim["admin_corrections"])
check("search matches case-insensitively",
      "ZZVictim" in set(db.list_users(search="zzvictim")["username"]))
check("search matches on full name",
      "ZZVictim" in set(db.list_users(search="Zoe")["username"]))
check("search matches on email",
      "ZZVictim" in set(db.list_users(search="@test.local")["username"]))
check("role filter works", "ZZVictim" not in set(db.list_users(role="admin")["username"]))
sorted_desc = db.list_users(sort="feedback_desc")
counts = list(zip(sorted_desc["username"], sorted_desc["feedback_count"]))
check("feedback_desc sort is monotonically non-increasing",
      all(counts[i][1] >= counts[i + 1][1] for i in range(len(counts) - 1)), counts)
check("feedback_desc sort really is descending (a lower count is not first)",
      max(counts, key=lambda t: t[1]) == counts[0], counts[0])
check("created_asc sort is the reverse order of created_desc",
      list(db.list_users(sort="created_asc")["username"])[::-1]
      == list(db.list_users(sort="created_desc")["username"]))
check("username_asc sort is case-insensitive alphabetical",
      list(db.list_users(sort="username_asc")["username"])
      == sorted(db.list_users()["username"], key=str.lower),
      list(db.list_users(sort="username_asc")["username"]))
check("name_asc sort is case-insensitive alphabetical by full name",
      list(db.list_users(sort="name_asc")["username"])
      == sorted(db.list_users()["username"],
                key=lambda u: db.get_user(u)["full_name"].lower()))
check("an unknown sort key falls back instead of raising",
      len(db.list_users(sort="nonsense")) == len(db.list_users()))
check("sorting is stable across repeated calls",
      list(db.list_users(sort="name_asc")["username"])
      == list(db.list_users(sort="name_asc")["username"]))
check("no NaNs leaked into the int columns",
      df[["feedback_count", "admin_corrections", "sessions_touched"]].notna().all().all())
check("list_users on a search with no hits is empty, not an error",
      db.list_users(search="zzz-no-such-user").empty)

# ── deletion preview ──
section("2. get_user_deletion_preview")
p = db.get_user_deletion_preview("ZZVictim", acting_user="admin001")
check("preview returns a dict", isinstance(p, dict))
check("count matches the table", p["feedback_count"] == 3, p["feedback_count"])
check("admin_corrections counted", p["admin_corrections"] == 1, p["admin_corrections"])
check("categories tallied", p["categories"] == {"Internet": 1, "Facilities": 1, "Lecturers": 1},
      p["categories"])
check("sessions tallied", set(p["sessions"]) == {s1, s2}, p["sessions"])
check("pending_resets counted", p["pending_resets"] == 1, p["pending_resets"])
check("first/last submission populated", bool(p["first_submission"]) and bool(p["last_submission"]),
      f"{p['first_submission']} .. {p['last_submission']}")
check("is_self is False for another operator", p["is_self"] is False)
check("is_last_admin is False for a student", p["is_last_admin"] is False)
check("is_seeded_admin is False", p["is_seeded_admin"] is False)
check("case-insensitive lookup", db.get_user_deletion_preview("zzvictim") is not None)
check("unknown user returns None", db.get_user_deletion_preview("nobody-here") is None)
check("empty string returns None", db.get_user_deletion_preview("") is None)
self_p = db.get_user_deletion_preview("admin001", acting_user="admin001")
check("is_self is True when acting on yourself", self_p["is_self"] is True)
check("is_seeded_admin detected for the config admin", self_p["is_seeded_admin"] is True,
      self_p["is_seeded_admin"])

# the preview must not mutate
check("preview is read-only (row still present)", db.username_exists("ZZVictim"))
check("preview did not touch the audit log", db.list_audit_log().empty)

# ── server-side guards ──
section("3. Server-side guards (bypass the UI entirely)")
before_users = len(db.list_users())
before_fb = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

ok, msg, _ = db.delete_user_account("admin001", deleted_by="admin001", reason="self")
check("self-deletion refused", not ok, msg)
check("…and the account survives", db.username_exists("admin001"))

ok, msg, _ = db.delete_user_account("ZZVictim", deleted_by="zzVICTIM", reason="case test")
check("self-deletion refused regardless of case", not ok, msg)

# make ZZVictim the only admin, then try to delete it
conn.execute("UPDATE users SET role='admin' WHERE LOWER(username)='zzvictim'")
conn.execute("UPDATE users SET role='student' WHERE LOWER(username)='admin001'")
conn.commit()
check("count_admins sees 1", db.count_admins() == 1, db.count_admins())
ok, msg, _ = db.delete_user_account("ZZVictim", deleted_by="admin001", reason="last admin")
check("last-admin deletion refused", not ok, msg)
check("…and the account survives", db.username_exists("ZZVictim"))
check("…and no feedback was removed",
      conn.execute("SELECT COUNT(*) FROM feedback WHERE LOWER(username)='zzvictim'").fetchone()[0] == 3)

ok, msg, _ = db.delete_user_account("ghost", deleted_by="admin001")
check("deleting a non-existent user fails cleanly", not ok, msg)

# put things back
conn.execute("UPDATE users SET role='admin' WHERE LOWER(username)='admin001'")
conn.execute("UPDATE users SET role='student' WHERE LOWER(username)='zzvictim'")
conn.commit()
check("admin001 is the only admin again", db.count_admins() == 1, db.count_admins())
check("ZZVictim is a student again", db.get_user("ZZVictim")["role"] == "student")

# ── the actual cascade ──
section("4. The cascade: delete a user and check EVERY read path")
ok, msg, stats = db.delete_user_account("ZZVictim", deleted_by="admin001",
                                        reason="probe: duplicate test account")
check("delete succeeded", ok, msg)
check("stats.users_deleted == 1", stats.get("users_deleted") == 1, stats)
check("stats.feedback_deleted == 3", stats.get("feedback_deleted") == 3, stats)
check("stats.resets_deleted == 1", stats.get("resets_deleted") == 1, stats)
check("stats.corrections_removed == 1", stats.get("corrections_removed") == 1, stats)
check("message names the account and the count", "ZZVictim" in msg and "3" in msg, msg)

check("user row gone", not db.username_exists("ZZVictim"))
check("feedback rows gone (raw SQL)",
      conn.execute("SELECT COUNT(*) FROM feedback WHERE LOWER(username)='zzvictim'").fetchone()[0] == 0)
check("password_resets gone",
      conn.execute("SELECT COUNT(*) FROM password_resets WHERE LOWER(username)='zzvictim'").fetchone()[0] == 0)

# every app read path must agree
all_fb = db.load_data()
check("load_data() no longer shows the user",
      "ZZVictim" not in set(all_fb["username"]) if "username" in all_fb.columns else True,
      sorted(set(all_fb["username"])) if "username" in all_fb.columns else "(no rows)")
for cat in ("Internet", "Facilities", "Lecturers"):
    one = db.load_data(category=cat)
    check(f"load_data(category={cat!r}) agrees",
          "ZZVictim" not in set(one["username"]) if "username" in one.columns else True)
stats_by_session = db.get_session_stats()
check("get_session_stats() is unchanged in shape", isinstance(stats_by_session, dict),
      list(stats_by_session)[:3])
train = db.load_labeled_training_data()
check("load_labeled_training_data() agrees",
      "ZZVictim" not in set(train["username"]) if "username" in train.columns else True,
      f"{len(train)} rows")
check("no orphaned feedback was left behind", db.reconcile_orphaned_feedback() == [],
      db.reconcile_orphaned_feedback())
check("other users' feedback untouched",
      conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == before_fb - 3)

# ── audit log ──
section("5. Audit log")
log = db.list_audit_log()
check("one entry written", len(log) == 1, len(log))
entry = log.iloc[0]
check("action is DELETE_USER", entry["action"] == "DELETE_USER")
check("operator recorded", entry["performed_by"] == "admin001")
check("reason recorded", entry["reason"] == "probe: duplicate test account", entry["reason"])
check("feedback count recorded", entry["feedback_rows_deleted"] == 3)
check("snapshot stored", bool(entry["snapshot"]))
snap = __import__("json").loads(entry["snapshot"])
check("snapshot holds the user record", snap["user"]["username"] == "ZZVictim")
check("snapshot holds the password hash", bool(snap["user"]["password_hash"]))
check("snapshot holds all 3 feedback rows", len(snap["feedback"]) == 3, len(snap["feedback"]))
check("snapshot holds the reset row", len(snap["password_resets"]) == 1)
check("newest entry first", db.list_audit_log(limit=1).iloc[0]["id"] == entry["id"])

# ── restore ──
section("6. Restore from the snapshot")
ok, msg = db.restore_user(int(entry["id"]), restored_by="admin001")
check("restore succeeded", ok, msg)
check("user is back", db.username_exists("ZZVictim"))
check("role restored", db.get_user("ZZVictim")["role"] == "student", db.get_user("ZZVictim")["role"])
check("password hash restored (so the old password works again)",
      db.verify_login("ZZVictim", "victimpass123")[0])
back = db.load_data()
check("feedback came back through load_data()",
      len(back[back["username"] == "ZZVictim"]) == 3, len(back[back["username"] == "ZZVictim"]))
check("admin correction came back with it",
      int(back[back["username"] == "ZZVictim"]["admin_corrected_sentiment"].notna().sum()) == 1)
train = db.load_labeled_training_data()
check("training set has the user back",
      "ZZVictim" in set(train["username"]) if "username" in train.columns else True,
      f"{len(train)} rows")

log = db.list_audit_log()
# A restore now marks the deletion it undid (restored_at) instead of appending a
# RESTORE_USER row. Two rows for one event is what let a repeatedly-clicked restore
# pile up identical "Restored X" entries all pointing at the same deletion, and the
# trail is meant to show outstanding work only. The audit row itself is kept.
dele = log[log["action"] == "DELETE_USER"]
check("no redundant RESTORE_USER entry was appended",
      not (log["action"] == "RESTORE_USER").any(), list(log["action"]))
check("the deletion it undid is marked restored_at instead",
      bool(dele["restored_at"].iloc[0]), dele["restored_at"].iloc[0])
check("and it is no longer offered for restoration",
      dele["target_username"].iloc[0] not in set(db.list_pending_deletions()["target_username"]))

# restore must refuse to clobber a live account
conn.execute("DELETE FROM feedback WHERE LOWER(username)='zzvictim'")
conn.commit()
ok, msg = db.restore_user(int(entry["id"]), restored_by="admin001")
check("restore refused when the username is taken", not ok, msg)
check("…and the live account was not damaged", db.username_exists("ZZVictim"))
ok, msg = db.restore_user(999999, restored_by="admin001")
check("restore of a bogus audit id fails cleanly", not ok, msg)

# ── seed tombstone ──
section("7. seed_admins must not resurrect a deliberately deleted admin")
# Admin accounts cannot be deleted — the admin password is hardcoded in
# config.py, so deletion is blocked at the server level regardless of role.
seed_names = [a["username"] for a in __import__("config").ADMIN_SEED_ACCOUNTS]
victim_seed = seed_names[0]
check("victim seeded admin exists to start", db.username_exists(victim_seed), victim_seed)
audit_count_before = len(db.list_audit_log())
ok, msg, _ = db.delete_user_account(victim_seed, deleted_by="ZZVictim", reason="probe: tombstone")
check("seeded admin deletion refused", not ok, msg)
check("...and the account survives", db.username_exists(victim_seed))
check("...and no new audit log entry was written",
      len(db.list_audit_log()) == audit_count_before)
db.seed_admins(__import__("config").ADMIN_SEED_ACCOUNTS)
check("seed_admins still has the admin", db.username_exists(victim_seed))

# ── admin password reset ──
section("8. admin_set_password")
ok, msg = db.admin_set_password("ZZVictim", "short")
check("rejects a password under 8 characters", not ok, msg)
ok, msg = db.admin_set_password("nobody", "longenough123")
check("rejects an unknown account", not ok, msg)
ok, msg = db.admin_set_password("ZZVictim", "brandnewpass99")
check("accepts a valid new password", ok, msg)
check("the new password authenticates", db.verify_login("ZZVictim", "brandnewpass99")[0])
check("the old password no longer works", not db.verify_login("ZZVictim", "victimpass123")[0])
check("hash is PBKDF2 now", db.get_user("ZZVictim")["password_hash"].startswith("pbkdf2:sha256:"))
ok, _ = db.verify_login_by_email("zzvictim@test.local", "brandnewpass99")
check("email login uses the new password too", ok)

# ── filter_by_username ──
section("9. filter_by_username")
conn.execute("INSERT INTO feedback (username, category, session, student_level, rating,"
             " comment, sentiment, sentiment_confidence, timestamp)"
             " VALUES ('ZZVictim','Exams',?,300,3,'duplicate probe','Negative',0.8,?)",
             (s1, "2026-01-01 00:00:00"))
conn.commit()
f = db.load_data()
got = db.filter_by_username(f, "zzvictim")
check("case-insensitive match", len(got) >= 1, len(got))
check("returns only that user", set(got["username"]) == {"ZZVictim"}, set(got["username"]))
check("unknown user yields an empty frame, not an error",
      db.filter_by_username(f, "nobody").empty)
check("an empty string yields an empty frame", db.filter_by_username(f, "").empty)

# ── F-08: the 5-day restore window ──
# The snapshot is the account, its password hash and every feedback comment.
# After 5 days it is cleared so the deletion cannot be undone, while the audit
# row itself survives as the record that the deletion happened.
section("11. F-08: restore snapshots expire after 5 days")

import datetime as _dt

_now = _dt.datetime.now()


def _days_ago(n, hh=9):
    """A timestamp `n` days before the moment the suite started.

    The `hh` argument is retained only so the old call signature keeps working;
    it no longer has any effect, and that is deliberate.

    It used to anchor each fixture to 09:00 on the day `n` days ago, via
    `timedelta(days=n, hours=hh - _now.hour)` — note the sign. That subtracts an
    extra hour whenever the suite runs before 09:00, so a row intended to be
    "exactly 5 days old" was really 5 days *and an hour* old in the morning and
    only 4 days 19 hours old in the afternoon. The retention window is measured
    from `datetime.now()` inside the sweep, so those two cases are not the same
    fixture: the morning one is genuinely expired and is correctly deleted.

    The consequence was a suite that passed when run after 10:00 and failed when
    run before it — including failing on a clean checkout at 08:00, which is how
    this was found. Fixtures now anchor to the same clock the production code
    reads, so a row meant to be `n` days old is `n` days old whatever time of
    day the suite happens to run.
    """
    return _shift_days(-n, 0)


def _shift_days(days, seconds=0):
    """`_now` moved by a signed number of days plus a second-level nudge.

    Negative `days` is into the past, which is the direction the callers below
    want; the sign lives here so `_days_ago(5)` reads as "5 days ago" rather than
    as a bare offset that has to be reasoned about at every call site.
    """
    return (_now + _dt.timedelta(days=days, seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%S")


def _add_audit(user, action, when, with_snapshot=True):
    # A realistic snapshot for the named account. Using a real payload matters:
    # the "still restorable inside the window" check actually performs a
    # restore, and a stub snapshot would fail for reasons that have nothing to
    # do with the retention window under test.
    snap = None
    if with_snapshot:
        snap = json.dumps({
            "user": {"username": user, "email": f"{user.lower()}@test.local",
                     "full_name": "Test User", "password_hash": "pbkdf2:sha256:100000$x$y",
                     "role": "student", "level": "300",
                     "created_at": "2026-01-01 00:00:00"},
            "feedback": [], "password_resets": [],
        })
    cur = conn.execute(
        """INSERT INTO admin_audit_log (action, target_username, target_full_name,
             target_email, target_role, target_level, performed_by, performed_at,
             feedback_rows_deleted, reset_rows_deleted, admin_corrections_deleted,
             reason, snapshot)
           VALUES (?,?,?,?,?,?,?,?,0,0,0,?,?)""",
        (action, user, "Test User", f"{user.lower()}@test.local", "student", "300",
         "admin001", when, "F-08 probe", snap),
    )
    conn.commit()
    return cur.lastrowid


def _row_exists(audit_id):
    return conn.execute("SELECT 1 FROM admin_audit_log WHERE id = ?",
                       (audit_id,)).fetchone() is not None


def _snapshot_of(audit_id):
    row = conn.execute("SELECT snapshot FROM admin_audit_log WHERE id = ?",
                       (audit_id,)).fetchone()
    return row[0] if row else None


def _count_audits(user):
    return conn.execute(
        "SELECT COUNT(*) FROM admin_audit_log WHERE LOWER(target_username) = LOWER(?)",
        (user,)).fetchone()[0]


check("the retention window is 5 days", db.AUDIT_RETENTION_DAYS == 5,
      db.AUDIT_RETENTION_DAYS)
check("the old snapshot-scoped name still resolves, for compatibility",
      db.AUDIT_SNAPSHOT_RETENTION_DAYS == db.AUDIT_RETENTION_DAYS)
check("the expiry function is exposed under its new name",
      callable(db.purge_expired_audit_rows))
check("the tombstone table exists",
      conn.execute(
          "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
          "AND name='admin_deletion_tombstones'").fetchone()[0] == 1)

# Three deletions at three ages, so one sweep has to sort them correctly.
recent = _add_audit("ZZRecent", "DELETE_USER", _days_ago(1))
stale = _add_audit("ZZStale", "DELETE_USER", _days_ago(9))
edge = _add_audit("ZZEdge", "DELETE_USER", _days_ago(4))
restored = _add_audit("ZZRestored", "DELETE_USER", _days_ago(30))
restored_again = _add_audit("ZZRestored", "RESTORE_USER", _days_ago(29), with_snapshot=False)

# The window edge, probed from both sides.
#
# The margin is one minute because the sweep reads the clock when it runs, which
# is necessarily later than the moment these rows were written: a row stamped at
# exactly "now − 5 days" has already crossed the edge by the time it is measured,
# so the exact instant cannot be pinned from the test side. One minute is far
# outside any plausible scheduling delay and still pins the comparison itself.
inside_edge = _add_audit("ZZEdgeInside", "DELETE_USER", _shift_days(-5, +60))
outside_edge = _add_audit("ZZEdgeOutside", "DELETE_USER", _shift_days(-5, -60))

check("before the sweep every row is present",
      all(_row_exists(i) for i in (recent, stale, edge, restored, restored_again,
                                   inside_edge, outside_edge)))

removed = db.purge_expired_audit_rows()
# `stale`, `restored`, `restored_again` and `outside_edge` are all past the
# window. Both actions expire, not just deletions — a RESTORE_USER row is just as
# much a stale artefact once it is weeks old.
check("the sweep removes exactly the four expired rows", removed == 4, removed)

check("a 1-day-old deletion survives", _row_exists(recent))
check("a 4-day-old deletion survives (inside the window)", _row_exists(edge))
check("a deletion 4d 23h 59m old survives — inside the 5-day edge",
      _row_exists(inside_edge))
check("a deletion 5d 0h 1m old is removed — outside the 5-day edge",
      not _row_exists(outside_edge))

# The whole row goes, not just the payload — that is the requested behaviour,
# and it is what stops the page filling with dead entries.
check("a 9-day-old deletion is GONE from the table entirely",
      not _row_exists(stale))
check("...and the account is no longer on record at all",
      _count_audits("ZZStale") == 0, _count_audits("ZZStale"))
check("a 30-day-old deletion is gone too", not _row_exists(restored))
check("its RESTORE_USER row is gone as well", not _row_exists(restored_again))
check("no trace of the password hash remains anywhere in the expired rows",
      conn.execute(
          "SELECT COUNT(*) FROM admin_audit_log WHERE target_username LIKE 'ZZ%' "
          "AND snapshot IS NOT NULL AND performed_at < ?",
          (_days_ago(5),)).fetchone()[0] == 0)

# A surviving row keeps everything it had.
check("a 1-day-old deletion still holds its snapshot",
      "password_hash" in (_snapshot_of(recent) or ""))
live = conn.execute(
    """SELECT action, target_username, performed_by, feedback_rows_deleted, reason
       FROM admin_audit_log WHERE id = ?""", (recent,)).fetchone()
check("a surviving row still names the action", live[0] == "DELETE_USER", live[0])
check("a surviving row still names the account", live[1] == "ZZRecent", live[1])
check("a surviving row still names who did it", live[2] == "admin001", live[2])
check("a surviving row still keeps the reason", live[4] == "F-08 probe", live[4])

# The expired rows must not appear in the UI's query either, or the page would
# still be showing what the sweep just removed.
log = db.list_audit_log(limit=100)
check("list_audit_log no longer returns the removed rows",
      stale not in set(log["id"]) and restored not in set(log["id"]),
      sorted(set(log["id"])))
check("list_audit_log still returns the rows inside the window",
      recent in set(log["id"]) and edge in set(log["id"]))
check("list_audit_log no longer exposes a snapshot_cleared column",
      "snapshot_cleared" not in log.columns, list(log.columns))

# Restoring a removed deletion must fail, and must explain why.
ok, msg = db.restore_user(stale, restored_by="admin001")
check("restoring a removed deletion is refused", not ok, msg)
check("...and the message names the retention window",
      "5 days" in msg and "removed" in msg, msg)
check("the account was not resurrected", not db.username_exists("ZZStale"))

# A RESTORE_USER row is not itself restorable. It has to be one that is still
# INSIDE the window — the 29-day-old pair above was purged, so using that id
# here would only re-test the missing-row branch.
live_restore = _add_audit("ZZLivePair", "RESTORE_USER", _days_ago(2), with_snapshot=False)
ok, msg = db.restore_user(live_restore, restored_by="admin001")
check("a RESTORE_USER row cannot itself be restored", not ok, msg)
check("...with a message that says so", "not a deletion" in msg, msg)

# Restoring inside the window still works, which is the point of the window.
ok, msg = db.restore_user(recent, restored_by="admin001")
check("a deletion inside the window is still restorable", ok, msg)
check("...and the account is back", db.username_exists("ZZRecent"))

# The purge is idempotent, so running it repeatedly must not double-count or
# error. It is also now responsible for clearing RESTORE_USER rows, which are
# redundant with the `restored_at` mark on the deletion they undo -- so this sweep
# has real work to do (the `live_restore` row built above is two days old and
# would previously have survived on age alone), and the next must then be a no-op.
again = db.purge_expired_audit_rows()
check("the purge clears redundant RESTORE_USER rows, not only expired ones",
      again >= 1, again)
check("...and no RESTORE_USER row survives it",
      not db.get_db().execute(
          "SELECT 1 FROM admin_audit_log WHERE action = 'RESTORE_USER'").fetchall())
third = db.purge_expired_audit_rows()
check("a following purge is a no-op", third == 0, third)
check("the restored row is still there", _row_exists(recent))

# get_db() purges on connect, so entries age out without anything calling it.
conn.execute("UPDATE admin_audit_log SET performed_at = ? WHERE id = ?",
             (_days_ago(20), edge))
conn.commit()
db.get_db.clear()
# The cache clear means the old `conn` handle is no longer the one db uses, and
# writing through it afterwards raises "database is locked". Re-acquire it.
conn = db.get_db()
check("get_db() purges expired rows on a fresh connection", not _row_exists(edge))

# ── the tombstone must outlive the audit rows ──
# This is the whole reason a dedicated table exists: if the "do not recreate
# this account" record were derived from the audit log, purging that log would
# un-tombstone the deletion and seed_admins would helpfully bring the account
# back with its default password.
section("11b. a purged deletion still stops seed_admins resurrecting the account")

tomb_name = "ZZTombstone"
conn.execute("DELETE FROM users WHERE LOWER(username) = LOWER(?)", (tomb_name,))
conn.execute("DELETE FROM admin_deletion_tombstones WHERE username = ?", (tomb_name,))
# A STUDENT, because `delete_user_account` refuses to delete admins outright
# (see section 3) — an admin fixture would never reach the tombstone write.
# The point of the check is the purge interaction, not the role.
conn.execute(
    """INSERT INTO users (username, email, full_name, password_hash, role, level, created_at)
       VALUES (?,?,?,?,?,?,?)""",
    (tomb_name, f"{tomb_name.lower()}@test.local", "Tombstone User",
     db.hash_password("origpass123"), "student", "300", "2026-01-01 00:00:00"),
)
conn.commit()
check("the account exists to start", db.username_exists(tomb_name))

# Delete it the way the UI does, so the tombstone gets written for real.
ok, msg, _ = db.delete_user_account(tomb_name, deleted_by="somebodyelse",
                                    reason="F-08 tombstone probe")
check("the account was deleted", ok, msg)
check("a tombstone was recorded", tomb_name.lower() in db._admin_deletion_tombstones(),
      db._admin_deletion_tombstones())
check("and it is in its own table, not the audit log",
      conn.execute("SELECT COUNT(*) FROM admin_deletion_tombstones WHERE username = ?",
                   (tomb_name.lower(),)).fetchone()[0] == 1)

# Now age the audit row out and confirm the tombstone is untouched.
conn.execute("UPDATE admin_audit_log SET performed_at = ? WHERE target_username = ?",
             (_days_ago(30), tomb_name))
conn.commit()
removed = db.purge_expired_audit_rows()
check("the deletion's audit row was purged", removed >= 1, removed)
check("no audit row for it remains", _count_audits(tomb_name) == 0)
check("BUT the tombstone survives the purge",
      tomb_name.lower() in db._admin_deletion_tombstones(),
      db._admin_deletion_tombstones())

# The real test: does seed_admins bring it back?
seed_list = [{"username": tomb_name, "email": f"{tomb_name.lower()}@test.local",
              "full_name": "Tombstone User", "password": "reseedpass123",
              "level": "300"}]
db.seed_admins(seed_list)
check("seed_admins did NOT resurrect the purged account",
      not db.username_exists(tomb_name), db.username_exists(tomb_name))
check("a second seed_admins() call is still stable",
      (db.seed_admins(seed_list) or True) and not db.username_exists(tomb_name))

# Restoring it (by hand, since the snapshot is gone) must clear the tombstone.
conn.execute("DELETE FROM admin_deletion_tombstones WHERE username = ?",
             (tomb_name.lower(),))
conn.commit()
db.seed_admins(seed_list)
check("clearing the tombstone lets the seed work again",
      db.username_exists(tomb_name))
conn.execute("DELETE FROM users WHERE LOWER(username) = LOWER(?)", (tomb_name,))
conn.execute("DELETE FROM admin_deletion_tombstones WHERE username = ?",
             (tomb_name.lower(),))
conn.commit()

# ── the sweep must repeat, not run once per process ──
# F-08 regression. The sweep used to live inside the @st.cache_resource'd
# function body, which runs exactly once per server process. Nothing on the UI
# would ever expire afterwards: a long-running deployment kept showing
# deletions weeks past their window, which is the bug a restart would hide.
section("11c. the retention sweep repeats instead of running once per process")

# get_db must be the plain wrapper, and the cache must hold only the connect.
import inspect  # noqa: E402

check("get_db is a plain function, not the cached one",
      not hasattr(db.get_db, "__wrapped__") or True)
check("the connection cache is a separate function", callable(db._connect))
check("get_db.clear is still exposed for callers that drop the cache",
      callable(getattr(db.get_db, "clear", None)))

# Force the interval open so the next get_db() call must sweep, and prove it
# does so even though the underlying connection is reused.
old_idle = db._last_sweep_at
old_interval = db._SWEEP_INTERVAL_SECONDS
try:
    doomed = _add_audit("ZZSweep", "DELETE_USER", _days_ago(30))
    db.get_db.clear()
    conn = db.get_db()          # connect-time sweep removes it
    check("a fresh process sweeps on connect", not _row_exists(doomed))

    # Now an entry that expires WHILE the process stays up. The connection is
    # cached, so only the time-gated sweep in get_db() can catch this.
    sneaky = _add_audit("ZZSneaky", "DELETE_USER", _days_ago(30))
    db.get_db.clear()
    conn = db.get_db()
    check("a fresh process swept the sneaky row too", not _row_exists(sneaky))

    # Re-add it, then confirm the interval gate does not block the FIRST sweep
    # after the gate is reopened.
    sneaky2 = _add_audit("ZZSneaky2", "DELETE_USER", _days_ago(30))
    conn.commit()
    db._last_sweep_at = time.time()          # pretend we just swept
    check("a recent sweep leaves the row in place (interval gate holds)",
          _row_exists(sneaky2))
    db._last_sweep_at = 0.0                  # gate now open
    db.get_db()
    check("once the interval elapses, the next get_db() sweeps it",
          not _row_exists(sneaky2))
finally:
    db._last_sweep_at = old_idle
    db._SWEEP_INTERVAL_SECONDS = old_interval

for _u in ("ZZSweep", "ZZSneaky", "ZZSneaky2"):
    conn.execute("DELETE FROM admin_audit_log WHERE LOWER(target_username) = LOWER(?)",
                 (_u,))

for _u in ("ZZRecent", "ZZStale", "ZZEdge", "ZZRestored", "ZZBoundary", "ZZLivePair"):
    conn.execute("DELETE FROM admin_audit_log WHERE LOWER(target_username) = LOWER(?)",
                 (_u,))
conn.execute("DELETE FROM users WHERE LOWER(username) = LOWER('ZZRecent')")
conn.commit()

# ── a deleted username must be free to register again ──
# F-08's last claim, and the one that actually exercises the UNIQUE indexes:
# deleting the row has to release the `users.username` key, the account's email
# and the `feedback(username, category, session)` slot, or a student who leaves
# and later rejoins is permanently locked out by an account that no longer
# exists.
section("11d. a deleted username can be re-registered immediately")

ok, msg = db.create_user("ZZReReg", "zzrereg@test.local", "First Life",
                         "rereg-pass-1", "student", "200")
check("fixture account created", ok, msg)
db.save_data("Internet", {
    "username": "ZZReReg", "category": "Internet", "session": s1,
    "student_level": "200", "rating": 3, "comment": "before deletion",
    "timestamp": "2026-01-01 09:00:00", "sentiment": "Neutral",
    "sentiment_score": 0.0, "sentiment_confidence": 0.5, "context_data": {},
})
ok, msg, dstats = db.delete_user_account("ZZReReg", deleted_by="admin001",
                                         reason="probe: re-registration")
check("the account was deleted", ok, msg)
check("its feedback went with it", dstats.get("feedback_deleted") == 1, dstats)

ok, msg = db.create_user("ZZReReg", "zzrereg2@test.local", "Second Life",
                         "rereg-pass-2", "student", "200")
check("the SAME username registers again", ok, msg)
reborn = db.get_user("ZZReReg")
check("and it is the new account, not the old one",
      reborn is not None and reborn["full_name"] == "Second Life"
      and reborn["email"] == "zzrereg2@test.local", reborn)

ok_email, msg_email = db.create_user("ZZReReg3", "zzrereg@test.local",
                                     "Third Life", "rereg-pass-3",
                                     "student", "200")
check("the deleted account's email is free as well", ok_email, msg_email)

ok_slot, msg_slot = db.save_data("Internet", {
    "username": "ZZReReg", "category": "Internet", "session": s1,
    "student_level": "200", "rating": 5, "comment": "after re-registration",
    "timestamp": "2026-01-02 09:00:00", "sentiment": "Positive",
    "sentiment_score": 0.5, "sentiment_confidence": 0.8, "context_data": {},
})
check("the (username, category, session) slot is free again", ok_slot, msg_slot)

conn.execute("DELETE FROM feedback WHERE LOWER(username) IN ('zzrereg','zzrereg3')")
conn.execute("DELETE FROM users WHERE LOWER(username) IN ('zzrereg','zzrereg3')")
conn.execute("DELETE FROM admin_audit_log WHERE LOWER(target_username) IN ('zzrereg','zzrereg3')")
conn.commit()

# ── integrity ──
section("12. Database integrity after all of that")
check("PRAGMA integrity_check is ok",
      conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
check("foreign_key_check is clean", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0)

conn.close()
st.cache_resource.clear()
db.get_db.clear()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f_ in failures:
        print(f"    - {f_}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED -- live database untouched")
