"""Prove a real PostgreSQL database works, before a presentation depends on it.

Run this ONCE, after creating a free hosted database and setting the URL. It is
the only way to know the translation is correct against a real server rather
than merely plausible — which is the whole point, because a database layer that
looks right and has never been executed is the single largest risk in this
deployment.

    set FUTO_POSTGRES_URL=postgresql://user:pass@host:5432/dbname
    .venv\\Scripts\\python.exe verify_postgres.py

It creates a scratch table, exercises the same operations the app depends on,
and leaves nothing behind. Nothing here touches the app's real data.
"""
from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_backend  # noqa: E402

results = []


def step(label, fn):
    try:
        detail = fn()
        results.append((label, True, detail or ""))
        print(f"  [PASS] {label}" + (f"  -- {detail}" if detail else ""))
    except Exception as exc:
        results.append((label, False, f"{type(exc).__name__}: {exc}"))
        print(f"  [FAIL] {label}  -- {type(exc).__name__}: {exc}")


def main() -> int:
    print("=" * 74)
    print("  PostgreSQL verification")
    print("=" * 74)

    url = db_backend.connection_url()
    if not url:
        print("\n  FUTO_POSTGRES_URL is not set.\n")
        print("  Create a free database and set it, for example:\n")
        print("    Supabase  https://supabase.com  -> New project -> Database")
        print("    Neon      https://neon.tech     -> Create a project\n")
        print("  Then, in this terminal:\n")
        print("    set FUTO_POSTGRES_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME\n")
        return 2

    # Never print the credentials back at the user.
    print(f"\n  Target: {url.split('@')[-1]}  (credentials hidden)\n")

    probe = db_backend.probe(url)
    if not probe["ok"]:
        print(f"  [FAIL] cannot reach the database -- {probe['detail']}\n")
        print("  Things to check:")
        print("    - the host and port are right and the database exists")
        print("    - the password is correct")
        print("    - the provider's 'connection pooler' URL is often required")
        print("      for hosted databases rather than the direct one")
        print("    - your IP is allowed, if the provider asks")
        return 1
    print(f"  [PASS] connected -- {probe['detail']}")
    print(f"         database: {probe.get('database')}\n")

    conn = db_backend.connect()

    def ddl():
        conn.execute("DROP TABLE IF EXISTS _verify_probe")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _verify_probe ("
            "id SERIAL PRIMARY KEY, "
            "username TEXT NOT NULL UNIQUE, "
            "score REAL, "
            "created_at TEXT NOT NULL)")
        conn.commit()
        return "created a scratch table with SERIAL and a UNIQUE constraint"

    step("schema DDL translates and runs (SERIAL, UNIQUE)", ddl)

    def insert():
        conn.execute(
            "INSERT INTO _verify_probe (username, score, created_at) "
            "VALUES (?,?,?)", ("alice", 4.5, "2026-01-01 09:00:00"))
        conn.commit()
        row = conn.execute(
            "SELECT username, score FROM _verify_probe WHERE username = ?",
            ("alice",)).fetchone()
        if row != ("alice", 4.5):
            raise AssertionError(f"round-trip mismatch: {row}")
        return f"inserted and read back {row}"

    step("parameterised INSERT and SELECT round-trip", insert)

    def conflict_update():
        conn.execute(
            "INSERT INTO _verify_probe (username, score, created_at) "
            "VALUES (?,?,?) ON CONFLICT (username) DO UPDATE "
            "SET score = EXCLUDED.score", ("alice", 9.5, "2026-01-01 09:00:00"))
        conn.commit()
        score = conn.execute(
            "SELECT score FROM _verify_probe WHERE username = ?",
            ("alice",)).fetchone()[0]
        if abs(score - 9.5) > 1e-9:
            raise AssertionError(f"upsert did not update: {score}")
        return "ON CONFLICT DO UPDATE behaves like INSERT OR REPLACE"

    step("upsert conflict clause", conflict_update)

    def conflict_nothing():
        conn.execute(
            "INSERT INTO _verify_probe (username, score, created_at) "
            "VALUES (?,?,?) ON CONFLICT DO NOTHING", ("alice", 1.0, "x"))
        conn.commit()
        score = conn.execute(
            "SELECT score FROM _verify_probe WHERE username = ?",
            ("alice",)).fetchone()[0]
        if abs(score - 9.5) > 1e-9:
            raise AssertionError("DO NOTHING overwrote the existing row")
        return "ON CONFLICT DO NOTHING leaves the existing row alone"

    step("insert-if-absent conflict clause", conflict_nothing)

    def rowcount_delete():
        conn.execute("INSERT INTO _verify_probe (username, score, created_at) "
                     "VALUES (?,?,?)", ("bob", 1.0, "x"))
        conn.commit()
        cur = conn.execute("DELETE FROM _verify_probe WHERE username = ?",
                           ("bob",))
        conn.commit()
        # The retention sweep returns this number, so it must be trustworthy.
        if cur.rowcount != 1:
            raise AssertionError(f"rowcount was {cur.rowcount}, expected 1")
        return "rowcount reports the number of deleted rows"

    step("rowcount is correct (the retention sweep depends on it)", rowcount_delete)

    def literal_q():
        conn.execute(
            "INSERT INTO _verify_probe (username, score, created_at) "
            "VALUES (?,?,?) ON CONFLICT DO NOTHING",
            ("carol", 2.0, "why?"))
        conn.commit()
        got = conn.execute(
            "SELECT created_at FROM _verify_probe WHERE username = ?",
            ("carol",)).fetchone()[0]
        if got != "why?":
            raise AssertionError(f"literal '?' was mangled into {got!r}")
        return "a question mark inside a value survives binding"

    step("question marks inside data are not mangled", literal_q)

    def cleanup():
        conn.execute("DROP TABLE IF EXISTS _verify_probe")
        conn.commit()
        conn.close()
        return "scratch table removed"

    step("cleanup", cleanup)

    print()
    failed = [r for r in results if not r[1]]
    if failed:
        print(f"  {len(failed)} STEP(S) FAILED — do NOT rely on this database yet.")
        print()
        print("  The full error text follows, which is what to paste into a")
        print("  search engine or an issue tracker:\n")
        for label, _, detail in failed:
            print(f"  --- {label} ---")
            print(f"  {detail}\n")
        return 1

    print("  EVERY STEP PASSED.")
    print()
    print("  This database is ready to use. Add the same URL as a Streamlit")
    print("  secret named FUTO_POSTGRES_URL, then redeploy.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)