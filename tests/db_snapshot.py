"""tests/db_snapshot.py
-------------------
A consistent, read-only copy of the live database for the test suites.

Why this file exists
--------------------
Every suite that touches data used to do this:

    shutil.copy2(os.path.join(ROOT, "futo_feedback.db"), COPY)

`db.get_db()` puts the live file into **WAL** mode, and WAL works by writing
committed transactions to a separate `-wal` sidecar until a checkpoint folds
them back into the main file. `shutil.copy2` copies one file. So the copy
contains the database *as of the last checkpoint* and silently discards
everything written since — which on a busy development database can be
hundreds of kilobytes of real rows.

It fails in the worst possible way: the copy is a valid, self-consistent SQLite
database. Nothing errors. The suite just quietly asserts against a snapshot
from an arbitrary point in the past.

Observed while building the training-trigger suite, on the real file:

    via sqlite3 (follows the WAL):  admin001 -> pbkdf2:sha256:100000$92e4…
    via shutil.copy2 of the .db:    admin001 -> ef92b778…  (legacy SHA-256)
    via shutil.copy2 of the .db:    DeAnalyst  present
    feedback rows:  naive copy = 4   actual = 0

The copied database was so stale that it showed two accounts where there is
one, an admin whose password hash had since been upgraded, and four feedback
records that had since been deleted. A test asserting "the cascade removed
every feedback row" would have passed against rows that did not exist.

How this fixes it
-----------------
SQLite's own online backup API. It reads the source through the normal
connection (so the WAL is followed) and writes a complete, checkpointed
destination. It opens the source read-only in the sense that matters: no write
ever reaches the live file, and it does not run the schema migration, the WAL
switch, or the retention sweep that `db.get_db()` performs.

Usage:

    from db_snapshot import snapshot_live_db
    COPY = snapshot_live_db()          # -> a path in a fresh temp dir
    db.DB_PATH = COPY
"""
from __future__ import annotations

import io
import os
import shutil
import sqlite3
import sys
import tempfile

# Matches every other file in this directory; the console is cp1252 and the
# class-distribution bars in `train_model` are not.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "futo_feedback.db")


def snapshot_live_db(dest_dir: str | None = None, live: str | None = None) -> str:
    """Copies the live database to a temp file and returns the new path.

    Raises `FileNotFoundError` if the live database is absent rather than
    silently creating an empty one: an empty copy passes "the schema is valid"
    checks for the wrong reason and fails everything else with a confusing
    "no such table" error.
    """
    source = live or LIVE_DB
    if not os.path.exists(source):
        raise FileNotFoundError(
            f"No database at {source!r}. The suites copy the real one so they "
            f"never touch live data — they cannot run against a fresh checkout "
            f"until `db.get_db()` has created it once."
        )
    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="futo_snapshot_")
    dest = os.path.join(dest_dir, "copy.db")

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30.0)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # A leftover `-wal` from a previous run at the same path would shadow the
    # copy. `mkdtemp` makes that impossible, but the cleanup is one line and
    # turns a future reuse of this helper from a silent wrong-data bug into a
    # non-event.
    for suffix in ("-wal", "-shm"):
        side = dest + suffix
        if os.path.exists(side):
            try:
                os.remove(side)
            except OSError:
                pass
    return dest


def teardown(path: str, temp_dir: str | None = None) -> None:
    """Removes a snapshot and, when given, the directory that held it."""
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return
    base = os.path.dirname(path)
    if base and os.path.isdir(base) and os.path.basename(base).startswith("futo_"):
        shutil.rmtree(base, ignore_errors=True)
