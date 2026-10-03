"""Keep the SQLite database alive across ephemeral container restarts.

WHY THIS EXISTS
---------------
Streamlit Community Cloud runs the app on a rental container whose disk is wiped
whenever it sleeps, restarts or is redeployed. The database is a single file, so
"wiped disk" means "no data" — and on the next boot `db.seed_admins` recreates a
brand-new database containing only the default administrator. Everything a user
submitted is gone, with no error anywhere.

This module keeps a second copy of that file in a private GitHub repository, so a
wiped container can fetch its data back instead of starting empty.

    container starts  ──►  has no database?  ──yes──►  download from GitHub
                                                        │
    page loads         ──►  cheap fingerprint check       │
                             │                            │
                    file changed? ──yes──►  background thread
                                        checkpoints the WAL,
                                        uploads to GitHub

WHAT IT IS NOT
--------------
This is not a database server, and it is not safe for heavy concurrent use. Two
people saving in the same few seconds can cost one upload. For a university
project, a demo, or a classroom it is entirely adequate; for a production system
with real concurrent writers, use a hosted Postgres instead. The trade-off is
stated here rather than discovered later.

DESIGN CONSTRAINTS
------------------
* **Off unless configured.** With no backup settings present this module does
  nothing at all, so local development and the whole existing test suite behave
  exactly as before. That is the property that makes it safe to ship.
* **Never raises into the app.** A storage problem must not take the site down.
  Failures are recorded once and reported in the sidebar, then ignored.
* **Never blocks a page load.** All network I/O happens on a background thread;
  the per-page hook is a stat() and a size comparison.
* **WAL-aware.** SQLite in WAL mode keeps recent commits in the `-wal` sidecar
  rather than the main file. Uploading the main file without checkpointing first
  silently ships a database that is missing everything written in the last few
  minutes. This module checkpoints before every upload and clears stale sidecars
  after a restore. This is the same trap that already bit `db_snapshot.py` once.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
import threading
import time

__all__ = [
    "is_enabled", "restore_if_missing", "note_activity", "status",
    "database_fingerprint", "looks_like_sqlite", "backup_filename",
    "DEFAULT_INTERVAL_SECONDS",
]

# How long to wait after the file changes before uploading. Long enough that a
# burst of writes results in one upload, short enough that a container that dies
# immediately afterwards loses very little.
DEFAULT_INTERVAL_SECONDS = 20

# The GitHub contents API serves files up to 1 MB this way; our database is a few
# kilobytes, but feedback accumulates and the blob API is the safe fallback.
_CONTENTS_LIMIT = 1_000_000

_GITHUB_API = "https://api.github.com"

# SQLite files begin with this exact string. Restoring a truncated or wrong file
# would destroy the local database, so it is verified before anything is
# overwritten.
_SQLITE_MAGIC = b"SQLite format 3\x00"


# ── configuration ───────────────────────────────────────────────────────────

def _setting(name: str):
    """Read a setting from Streamlit secrets first, then the environment.

    Secrets come first because on Cloud that is where they are set, and the
    environment fallback is what makes the same code testable from a terminal.
    Returns None rather than raising when neither is available.
    """
    try:
        import streamlit as st
        secrets = getattr(st, "secrets", None)
        if secrets is not None:
            for container in (secrets, getattr(secrets, "db_backup", None)):
                if container is None:
                    continue
                try:
                    if name in container:
                        value = container[name]
                        if value not in (None, ""):
                            return str(value).strip()
                except Exception:
                    continue
    except Exception:
        pass
    value = os.environ.get(name, "").strip()
    return value or None


def backup_filename() -> str:
    """The name this database is stored under inside the backup repository."""
    return _setting("FUTO_DB_BACKUP_PATH") or "futo_feedback.db"


def _repo() -> str | None:
    """The `owner/name` of the backup repository."""
    return _setting("FUTO_DB_BACKUP_REPO")


def _token() -> str | None:
    return _setting("FUTO_DB_BACKUP_TOKEN")


def _branch() -> str:
    return _setting("FUTO_DB_BACKUP_BRANCH") or "main"


def _interval() -> int:
    raw = _setting("FUTO_DB_BACKUP_INTERVAL")
    try:
        value = int(raw) if raw else DEFAULT_INTERVAL_SECONDS
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS
    # A zero or negative interval would spin the uploader flat out.
    return max(5, value)


def is_enabled() -> bool:
    """True only when both a repository and a token are configured."""
    return bool(_repo() and _token())


# ── local file helpers ──────────────────────────────────────────────────────

def database_path() -> str:
    """The live database file, as `db.py` defines it.

    Imported lazily so that merely importing this module does not import the
    database layer, which keeps the test suite fast and side-effect free.
    """
    import db
    return db.DB_PATH


def database_fingerprint(path: str) -> tuple | None:
    """A cheap identity for the file's current contents.

    Size and modification time together are enough for "has anything been
    written since I last looked". Hashing the whole file on every page load would
    be wasteful, and the file is only ever appended to or rewritten in place, so
    the pair cannot miss a change.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, int(st.st_mtime))


def looks_like_sqlite(path: str) -> bool:
    """True when `path` begins with SQLite's file signature."""
    try:
        with open(path, "rb") as fh:
            return fh.read(len(_SQLITE_MAGIC)) == _SQLITE_MAGIC
    except OSError:
        return False


def _sidecars(path: str) -> list[str]:
    return [path + "-wal", path + "-shm"]


def checkpoint(path: str) -> None:
    """Fold the write-ahead log back into the main file.

    Without this the upload would contain a database missing everything written
    since the last checkpoint — the failure is silent, and the restored copy
    simply lacks the most recent submissions.
    """
    try:
        conn = sqlite3.connect(path, timeout=30.0)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # A checkpoint failure is not fatal: the main file is still a valid
        # database, and the upload is an improvement either way.
        pass


def integrity_ok(path: str) -> bool:
    """True when SQLite's own integrity check passes on the file."""
    try:
        conn = sqlite3.connect(path, timeout=30.0)
        try:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            return bool(row) and str(row[0]).lower() == "ok"
        finally:
            conn.close()
    except Exception:
        return False


# ── GitHub transfer ─────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "futo-feedback-db-backup",
    }


def _contents_url(repo: str, ref: str) -> str:
    return f"{_GITHUB_API}/repos/{repo}/contents/{backup_filename()}?ref={ref}"


def _download(requests_mod, repo: str, ref: str, timeout: int = 60):
    """Return (bytes, sha) for the stored database, or (None, None)."""
    resp = requests_mod.get(_contents_url(repo, ref), headers=_headers(),
                            timeout=timeout)
    if resp.status_code == 404:
        return None, None
    resp.raise_for_status()
    payload = resp.json()

    encoded = payload.get("content") or ""
    if payload.get("encoding") == "base64" and encoded:
        # The contents API wraps long text; strip the newlines it inserts.
        return base64.b64decode(encoded.replace("\n", "")), payload.get("sha")

    # Fall back to the blob API for anything the contents API will not inline.
    sha = payload.get("sha")
    if not sha:
        return None, None
    blob = requests_mod.get(f"{_GITHUB_API}/repos/{repo}/git/blobs/{sha}",
                            headers=_headers(), timeout=timeout)
    blob.raise_for_status()
    return base64.b64decode(blob.json()["content"]), sha


def _upload(requests_mod, repo: str, ref: str, data: bytes, sha, timeout: int = 60):
    """Write the database to the backup repository. Returns the new sha."""
    body = {
        "message": "chore: sync feedback database",
        "content": base64.b64encode(data).decode(),
        "branch": ref,
    }
    if sha:
        body["sha"] = sha
    resp = requests_mod.put(_contents_url(repo, ref), headers=_headers(),
                            json=body, timeout=timeout)
    if resp.status_code in (409, 422) and sha:
        # Someone else uploaded between our download and this write. Retrying
        # without a sha would silently overwrite their copy, so give up and let
        # the next cycle reconcile rather than lose data.
        return None
    resp.raise_for_status()
    return (resp.json().get("content") or {}).get("sha")


# ── state ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_state = {
    "fingerprint": None,   # last uploaded / restored fingerprint
    "remote_sha": None,    # sha of the copy in GitHub
    "last_error": None,    # one message, shown in the sidebar
    "restored": False,
    "uploads": 0,
    "last_upload_at": None,
    "pending_since": None,
    "thread": None,
}


def status() -> dict:
    """A snapshot for display. Safe to call from anywhere."""
    with _lock:
        return dict(_state)


def _fail(message: str) -> None:
    with _lock:
        if _state["last_error"] != message:
            _state["last_error"] = message


def _clear_error() -> None:
    with _lock:
        _state["last_error"] = None


# ── public entry points ─────────────────────────────────────────────────────

def restore_if_missing(requests_mod=None) -> bool:
    """Fetch the stored database if this container has none.

    Called once at startup, before the app touches the database. Returns True if
    a restore happened. Any failure leaves the local file untouched.
    """
    if not is_enabled():
        return False
    path = database_path()
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with _lock:
            _state["restored"] = True   # container that kept its disk
        return False

    if requests_mod is None:
        import requests as requests_mod  # noqa: N813

    repo, ref = _repo(), _branch()
    try:
        data, sha = _download(requests_mod, repo, ref)
    except Exception as exc:
        _fail(f"Could not reach the backup repository ({type(exc).__name__}). "
              f"Starting with an empty database.")
        return False

    if not data:
        _fail("No backup found yet — this is the first run, so the database "
              "starts empty and will be backed up shortly.")
        return False

    # Verify before overwriting anything. A truncated download must never be able
    # to replace a working local database.
    tmp = path + ".restore"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
    except OSError as exc:
        _fail(f"Could not write the restored database ({exc}).")
        return False

    if not looks_like_sqlite(tmp) or not integrity_ok(tmp):
        os.unlink(tmp)
        _fail("The backup was not a valid database, so it was ignored rather "
              "than risk overwriting good data.")
        return False

    # Any sidecar left over from a previous process belongs to the database we
    # are replacing and must go, or SQLite will try to replay a stale log.
    for extra in _sidecars(path):
        try:
            os.unlink(extra)
        except OSError:
            pass
    os.replace(tmp, path)

    with _lock:
        _state["remote_sha"] = sha
        _state["fingerprint"] = database_fingerprint(path)
        _state["restored"] = True
    _clear_error()
    return True


def _sync_once(requests_mod) -> None:
    """One upload, if the file has changed since we last uploaded."""
    path = database_path()
    current = database_fingerprint(path)
    if current is None:
        return
    with _lock:
        if current == _state["fingerprint"]:
            return
        pending = _state["pending_since"]
        if pending is not None and time.time() - pending < _interval():
            return
        _state["pending_since"] = time.time()

    checkpoint(path)
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        _fail(f"Could not read the database for backup ({exc}).")
        return

    repo, ref = _repo(), _branch()
    try:
        with _lock:
            known_sha = _state["remote_sha"]
        # Re-read the current sha each time so the first upload after a restart
        # updates the existing file rather than failing on a sha mismatch.
        try:
            _, known_sha = _download(requests_mod, repo, ref)
        except Exception:
            pass
        new_sha = _upload(requests_mod, repo, ref, data, known_sha)
    except Exception as exc:
        _fail(f"Database backup failed ({type(exc).__name__}). Your data is "
              f"still safe on this machine, but it will not survive a restart "
              f"until this succeeds.")
        return

    if new_sha is None:
        _fail("Another copy was uploaded at the same time; this one was held "
              "back rather than overwrite it.")
        return

    with _lock:
        _state["remote_sha"] = new_sha
        _state["fingerprint"] = current
        _state["last_upload_at"] = time.time()
        _state["pending_since"] = None
        _state["uploads"] += 1
    _clear_error()


def _worker() -> None:
    import requests as requests_mod
    while True:
        time.sleep(_interval())
        try:
            if is_enabled():
                _sync_once(requests_mod)
        except Exception as exc:
            _fail(f"Database backup stopped unexpectedly ({type(exc).__name__}).")


def note_activity() -> None:
    """Called on every page load. Cheap, and never touches the network.

    Starts the background uploader on first use, so `db.py` needs only this one
    call and no knowledge of how backup works.
    """
    if not is_enabled():
        return
    with _lock:
        thread = _state["thread"]
        if thread is not None and thread.is_alive():
            return
        _state["thread"] = threading.Thread(
            target=_worker, name="futo-db-backup", daemon=True)
        _state["thread"].start()


def _flush_for_tests(requests_mod) -> None:
    """Force an immediate sync regardless of the debounce. Test seam only."""
    with _lock:
        _state["pending_since"] = 0.0
        _state["fingerprint"] = None
    _sync_once(requests_mod)