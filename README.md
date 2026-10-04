# FUTO IFT Smart Feedback System

A role-aware, sentiment-powered feedback platform for the FUTO Department
of Information Technology, built with Streamlit, SQLite **or PostgreSQL**,
Pandas, Plotly, scikit-learn and smtplib.

**New here?** Start with **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** — a full
step-by-step walkthrough from installing Python to deploying the app,
written for copy-paste-along development. It covers account
registration, setting up email, and training the sentiment model in
detail — this README is just the map.

**Looking for how it actually works?** Read
**[docs/SYSTEM_ARCHITECTURE.md](./docs/SYSTEM_ARCHITECTURE.md)** — the full
technical reference: architecture and sequence diagrams, the complete database
schema, every key flow (sign-in, delete/restore, sessions, email, sentiment),
the security model, the retention rules, and a changelog of what changed and why.

> **The database is PostgreSQL in production.** Streamlit Community Cloud's disk
> is wiped on redeploy, so the SQLite file cannot be relied on there. The same
> codebase runs on either — SQLite stays the default everywhere else, so no
> local workflow changes. See
> [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) to deploy, or §5 of the
> architecture document for how the translation layer works.

## Quick start

Requires **Python 3.12 or newer** (developed and verified on 3.13).

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell or cmd)
python -m venv .venv
.venv\Scripts\activate

# then, in the activated environment
pip install -r requirements.txt
python download_nltk_data.py
streamlit run app.py
```

`download_nltk_data.py` exits non-zero if anything fails to download, so a
quiet success really is a success — do not just skim past its output.

### If the animations are missing

The app cancels every looping animation when the operating system asks for
reduced motion — `prefers-reduced-motion: reduce`, which is **Settings →
Accessibility → Visual effects → Animation effects** on Windows, "Reduce motion"
on macOS, and similar on iOS/Android. That is the correct default and most people
want it, but it is an OS-level switch that is easy to set once and forget, and
nothing on screen explains why the site looks static.

To override it without touching the OS setting, append a query parameter to any
URL in the app:

| Parameter | Effect |
|---|---|
| `?motion=on` | restore the animations even where the OS asks for reduced motion |
| `?motion=off` | cancel them even where the OS allows them |

No preference is stored; the parameter travels with the session, so it survives a
refresh. The override lives in `app.py` rather than in the stylesheet because a
CSS media query cannot read a query parameter.

There is **no shared demo login** — every student registers their own
account from the login screen ("Create an Account"). One admin account is
auto-created on first run from `config.py` → `ADMIN_SEED_ACCOUNTS`
(`admin001` / `password123` by default — **change this before any real
deployment**, from *User Management* in the app; see below).

## Project structure

```
app.py                  entry point — routing, sidebar, CSS injection,
                         session token + auth gate, the web_sessions table
config.py                categories, checklist options, accounts, session, sentiment/email settings
auth.py                  login/registration validation + session-based lockout
db.py                    persistence — users, password_resets, feedback, admin_notes,
                         academic_sessions, admin_audit_log, admin_deletion_tombstones
                         + the guarded deletion/restore engine
db_backend.py            PostgreSQL translation layer + connection recovery
                         (completely inert unless FUTO_POSTGRES_URL is set)
sentiment.py             domain-lexicon rule engine (VADER Academic Pro) + optional trained classifier
train_model.py           trains a classifier on admin-corrected labels
download_nltk_data.py    one-time script: downloads the NLTK corpora
email_service.py         SMTP email (registration, OTP, submission, completion, password-changed)
charts.py                Plotly chart builders
components.py            shared HTML widgets (cards, alerts, headers) + esc() + html_alert()
icons.py                 Lucide icon helper (inline SVG, no CDN) + sentiment icon/color mapping
st_compat.py             Streamlit version shim — every call site goes through it
styles.py                all CSS — light theme
storage.py               optional external backup (no-op unless configured)
.streamlit/secrets.toml.example   copy to secrets.toml and fill in SMTP details
docs/SYSTEM_ARCHITECTURE.md      full technical reference + diagrams
app_pages/                   one file per screen (login, home, feedback_form,
                           my_stats, admin_overview, full_dashboard,
                           decision_insights, user_management)
tests/                       verification suite — run it with run_all.py
```

## Core capabilities

- **Unique, recoverable student accounts.** Real `users` table with
  hashed passwords and unique usernames/emails, self-registration, and
  a "Forgot Password?" flow via emailed one-time code (hashed at rest,
  15-minute expiry, 5-attempt lockout, deliberately vague error
  messages so the form can't be used to enumerate valid accounts). A
  30-second lockout kicks in after repeated failures.
- **Admin user management.** A searchable, sortable, role-filtered
  directory of every account. Admins can reset any account's password,
  and can permanently delete an account *and all of that student's
  feedback* — behind a two-stage confirmation that requires typing the
  exact username (plus `DELETE ADMIN` for admin accounts). Deletion is
  server-side guarded: you cannot delete yourself, you cannot delete
  the last remaining admin, and you cannot delete any admin account.
  Every action is written to an audit log with
  a full JSON snapshot of the deleted rows, so a mistaken deletion can be
  undone from the same page — for **5 days**. After that the entry is
  permanently removed (the account's details, its password hash and the full
  text of its feedback comments), so the deletion becomes irreversible and
  leaves no record behind. The panel lists only deletions that are **still
  awaiting restoration**, each with a countdown of the days it has left; a
  restored deletion leaves the panel immediately rather than lingering as
  unfinished work, and a confirmation that clears itself after ten seconds
  reports what happened. Copy the
> page or the database first if you need the history to outlive the window.
- **Administrator-managed academic sessions.** Create a session, promote one to
  be the active default, or delete one — from *Full Dashboard → Academic
  Sessions Management*. The active default supplies the `session` column's
  default for new submissions. Deleting one is refused for the active default
  and for the last remaining session, and it never deletes that session's
  feedback: the rows stay and remain visible under *All Sessions (Aggregate)*,
  they simply stop being offered as a filter. Every deletion is audited.
- **Sessions that survive a refresh.** Signing in stores the session in a
  `web_sessions` row keyed by a token carried in the URL, so reloading or
  reopening the tab keeps you signed in for up to seven days of inactivity
  (the window slides on every load). Deleting an account revokes it at once.
- **A deterministic, domain-tuned sentiment engine.** A 220+ term
  academic lexicon with multi-word-expression rewriting, a negation-aware
  pre-pass, intensifier boosting and contrastive-clause weighting. No
  randomness: the same comment always scores identically. Optional
  supervised classifier, trained on admin-corrected feedback, supplies
  the *label only* — the score, the polarity split, the cues and the
  confidence always come from the rules, so a comment reads the same
  whether or not a model exists on disk. The admin diagnostics card
  reports which engine actually ran and, if a model failed to load, why.
  Corrections you make in *Decision Insights* accumulate, and once enough
  exist an administrator can train the classifier without leaving the app
  (*User Management → Supervised Sentiment Classifier*). Training runs in
  the server process — there is no shell on Streamlit Community Cloud — so
  the freshly written model is picked up immediately, and a result dialog
  reports the held-out accuracy, the macro F1 and how many corrections it
  learned from. A weak model warns but still loads; it can only change the
  label, never the score.
- **Transactional email.** Registration confirmation, password-reset
  codes, per-submission acknowledgement, an "all categories complete"
  thank-you, and a password-changed notice — all gracefully optional;
  the app is fully functional with email left unconfigured.
- **Real, level-scoped curriculum data.** Course Content (and the
  optional course field on Teaching Style) show only the courses that
  match the student's own registered academic level, sourced from the
  Department Handbook's official syllabus tables — not a generic list
  shown to everyone. Facilities and Curriculum stay level-agnostic on
  purpose (a broken projector affects every level equally).
- **Academic session scoping.** Every submission carries a session, and
  the sidebar selector decides which one the app is looking at. The
  active default is managed in the app under *Full Dashboard → Academic
  Sessions Management*, not by editing a constant.- **Admin action notes** on Decision Insights — a persisted,
  attributable note per category, closing the "feedback → visible
  action" loop.
- **CSV export** on the admin Full Dashboard.
- **Role-aware login** — full marketing-style page for students; a
  deliberately plain, centered card for admins.
- **Light, professional theme** with real Lucide SVG icons inlined at
  render time — no CDN, no icon-font ligature hacks, no network
  dependency for the UI to look right.
- **XSS-safe rendering** — all user-supplied free text is HTML-escaped
  before being rendered, both in the app (`components.esc()`, and
  `components.html_alert()` which escapes by default) and in outbound
  emails (`email_service._esc()`).
- **Defensive schema migration** — if `futo_feedback.db` already exists
  from an earlier version of this project, missing columns and tables are
  added automatically on startup, and orphaned feedback rows are
  reconciled, rather than crashing.

See `SETUP_GUIDE.md` for the full walkthrough of each of these,
including exact steps for registration, SMTP setup, session management,
and training the sentiment model on your own data.

## Verifying the build

```
.venv\Scripts\python.exe tests\run_all.py      # Windows
python tests/run_all.py                        # macOS / Linux
```

`run_all.py` runs 20 suites in separate subprocesses — so one script crashing
or exiting non-zero cannot take the rest of the run with it — and prints a
pass/fail count per suite. Add `-v` for full output. Exit code `0` means
everything passed. It takes about five minutes, most of it the end-to-end
suites that drive the real app through Streamlit's `AppTest` harness.

Those copy the live database to a temporary directory and repoint `db` at
it, so **the suite never writes to your real data**. Nothing else in `tests/`
modifies anything either; the checks that need the trained model skip
themselves cleanly if `model/sentiment_classifier.pkl` does not exist yet.

Three suites are *self-tests* of the checkers rather than of the app, and they
sit next to the checker they verify:

| Suite | Guards |
| --- | --- |
| `test_xss_static.py` | every `{...}` in an HTML string is escaped, or carries a written justification |
| `test_xss_static_selftest.py` | proves the gate above actually flags real holes |
| `test_undefined_names.py` | no module references a name it never binds |
| `test_undefined_names_selftest.py` | proves the scanner above detects real NameErrors |
| `test_streamlit_calls.py` | duplicate kwargs, shim bypasses, and — Check 4 — every `:material/…:` name against Streamlit's own validator and every `i(…)` slug against `icons.py` |
| `test_streamlit_calls_selftest.py` | proves the icon sweep above still fails on a fake Material name and a missing Lucide slug |
| `test_css.py` | brace balance, real `data-testid`s, motion tokens, the type floor, contrast, responsive coverage, that every class written into HTML actually has a rule, that no gradient-text rule uses the `background` shorthand in a way that unclips it, and that the sidebar nav never depends on DOM position or on `:has()` |
| `test_dept_name_integrity.py` | no pronoun-shaped `IFT` has crept back into any source, doc or config file |
| `test_xss_runtime.py` | seeds `<script>` and `onerror` payloads into the comment, lecturer name, course name and location, then renders every page in both roles and proves none reaches a page raw |

A checker that reports "clean" is only worth something if you have watched it
fail on a real bug, which is what the self-tests are for. Each caught a
genuine defect in its own checker the first time it ran, so treat a failure in
any of them as a real signal rather than noise.

`test_xss_runtime.py` is the runtime counterpart to `test_xss_static.py`: the
static gate reasons about the source, this one puts the payload in the
database and renders the pages, so a value that is escaped in one branch and
not another cannot hide. It only audits fragments actually rendered with
`unsafe_allow_html=True` — a plain `st.markdown` escapes its own text, and
flagging it would be a false positive.

`test_css.py` is the one to know about if you touch `styles.py`. Several of its
checks exist because a real defect got past the checks that were there at the
time: the sidebar's "ugly transparent oval" was caused by an unscoped
`[data-testid="stRadio"]` rule that reached the navigation from the login
page's own switcher CSS, and the deletion audit trail shipped with seven
classes and no stylesheet rules at all. It also verifies against the installed
Streamlit frontend bundle rather than against a hard-coded list, so a selector
for a widget that does not exist is caught before deploy.

## Known limitations / suggested next steps

- **Legacy password hashes are migrated by a forced reset, not silently.**
  Anything created or reset now uses `pbkdf2:sha256:100000` with a
  per-user random salt, and passwords set by the very first release of this
  project (a bare unsalted SHA-256 hex digest) still sign in — but a
  legacy account is held on a mandatory *Set a new password* screen the
  moment it signs in, before any page renders, and cannot continue until it
  has chosen a PBKDF2 password. The screen refuses to accept the current
  password again, so the migration always happens. `db.password_is_legacy`
  reads the stored hash to decide; there is no session flag to clear and no
  silent rewrite. Until every legacy account has been through that gate,
  those rows have no salt: two accounts with the same password produce
  identical hashes, and a stolen database can be attacked with precomputed
  tables far more cheaply than the PBKDF2 rows next to it.
- No PDF export (CSV export is implemented; PDF would layer on top of
  a PDF toolchain of your choice).
- No 2FA for admin accounts.
- No foreign keys between `users` and `feedback`, so deleting a user does
  not cascade automatically. The app deletes the children explicitly in
  a single transaction and reconciles orphans on startup — but if you
  write your own SQL against this schema, you own the cascade too.
- **A deleted username is retained forever** in `admin_deletion_tombstones`,
  which is what stops `seed_admins` recreating a deleted seeded admin with
  its default password. The tombstone has no expiry, and for an ordinary
  student it is never actually consulted — only the seeded admin names are —
  so it is a permanent record of a username whose other data is gone after
  5 days. Restricting tombstones to seeded admin accounts only is a small
  change if that trade-off is not wanted.
- **Streamlit Community Cloud's filesystem isn't persistent across
  redeploys**, so the SQLite file cannot be used there. This is why the
  production deployment sets the `FUTO_POSTGRES_URL` secret and runs on
  PostgreSQL — see `DEPLOYMENT_GUIDE.md`. On SQLite, a redeploy still starts
  from an empty database and re-seeds `admin001` / `password123`.
- The trained classifier is lost on redeploy:
  `model/sentiment_classifier.pkl` is gitignored and is derived from
  corrections that live in the database. It is **not** needed for the app
  to function — the rule engine always produces the score — and an
  administrator can retrain it from *User Management → Supervised
  Sentiment Classifier* once corrections accumulate again.
- Back up with `sqlite3 futo_feedback.db ".backup backup/<name>.db"`, not
  by copying the raw file: the database runs in WAL mode, and copying
  only `futo_feedback.db` can silently miss committed transactions still
  held in `futo_feedback.db-wal`. On a PostgreSQL deployment use `pg_dump`
  instead.

---

## Need the detail?

**[docs/SYSTEM_ARCHITECTURE.md](./docs/SYSTEM_ARCHITECTURE.md)** covers the
architecture and sequence diagrams, the full database schema (all 8 tables,
all 4 indexes, and which relationships are enforced and which are only
conventional), the dual-backend translation layer, every key flow, the security
model, the retention rules, and a changelog of what changed and why.
