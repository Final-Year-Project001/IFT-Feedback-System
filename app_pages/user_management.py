"""
app_pages/user_management.py
---------------------------
Administrative account directory, password resets, and the guarded
permanent-deletion flow (F-04 .. F-07).

Design constraints this page is built around:

* **Deletion is never one click.** Selecting a user and pressing a red button
  is exactly the kind of action that gets mis-fired, so the delete path takes
  a deliberate route every time: a scrollable preview of everything that will
  be destroyed, a type-the-exact-username gate, an extra `DELETE ADMIN`
  phrase for administrator accounts, an explicit acknowledgement checkbox, and
  a Delete button that stays disabled until every one of those is satisfied.
* **The server refuses too.** `db.delete_user_account` blocks self-deletion and
  last-admin deletion regardless of what the UI allows, so a stale browser tab
  or a scripted call cannot get around the confirmation.
* **Nothing is unrecoverable.** Every deletion writes a full JSON snapshot into
  `admin_audit_log`, which is what the Restore action on this same page reads.
  Deleting the audit trail is itself an auditable event, not a silent one.
"""

from __future__ import annotations

import streamlit as st

import db
import st_compat
from components import (
    esc, html_alert, html_metric, page_header, section_header, empty_state,
    park_result_dialog, progress_bar,
)
from icons import i

# Extra phrase an administrator must also type when deleting an *admin*
# account. Students are mis-deletable; losing the last administrator locks
# everyone out of the entire system, so that case gets a second gate.
ADMIN_DELETE_PHRASE = "DELETE ADMIN"


# ══════════════════════════════════════════════════════════════════════
#  ACCOUNT DIRECTORY
# ══════════════════════════════════════════════════════════════════════

def _flash():
    """Shows and clears a message parked by an action on this page."""
    msg = st.session_state.pop("um_flash", None)
    if msg:
        getattr(st, st.session_state.pop("um_flash_kind", "success"))(msg)


def _park(message: str, kind: str = "success"):
    st.session_state["um_flash"] = message
    st.session_state["um_flash_kind"] = kind


def _render_directory():
    """Search / filter / sort controls plus the account table."""
    st.markdown('<div class="um-filter-bar">', unsafe_allow_html=True)
    c_search, c_role, c_sort = st.columns([2, 1, 1.4])
    with c_search:
        search = st.text_input(
            "Search accounts",
            key="um_search",
            placeholder="Username, full name or email…",
            label_visibility="collapsed",
        )
    with c_role:
        role = st.selectbox(
            "Role", ["all", "admin", "student"],
            format_func=lambda r: {"all": "All roles", "admin": "Administrators",
                                   "student": "Students"}[r],
            key="um_role",
            label_visibility="collapsed",
        )
    with c_sort:
        sort = st.selectbox(
            "Sort", ["created_desc", "created_asc", "username_asc", "name_asc", "feedback_desc"],
            format_func=lambda s: {
                "created_desc": "Newest first",
                "created_asc": "Oldest first",
                "username_asc": "Username A–Z",
                "name_asc": "Name A–Z",
                "feedback_desc": "Most feedback",
            }[s],
            key="um_sort",
            label_visibility="collapsed",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    df = db.list_users(search=search, role=role, sort=sort)
    if df.empty:
        empty_state(
            "search", "No Matching Accounts",
            "Adjust the search text or role filter to find an account.",
        )
        return None

    st.caption(
        f"{len(df)} account{'s' if len(df) != 1 else ''} shown · "
        f"{int(df['feedback_count'].sum())} feedback record(s) linked to these accounts"
    )

    table = df[[
        "username", "full_name", "email", "role", "level",
        "feedback_count", "admin_corrections", "last_submission", "created_at",
    ]].rename(columns={
        "username": "Username", "full_name": "Full Name", "email": "Email",
        "role": "Role", "level": "Level", "feedback_count": "Feedback",
        "admin_corrections": "Corrections", "last_submission": "Last Submission",
        "created_at": "Created",
    })
    st_compat.dataframe(
        table, width="stretch", hide_index=True,
        column_config={
            "Feedback": st.column_config.NumberColumn(format="%d"),
            "Corrections": st.column_config.NumberColumn(format="%d"),
        },
    )

    if "um_target" not in st.session_state or st.session_state["um_target"] not in set(df["username"]):
        st.session_state["um_target"] = df["username"].iloc[0]
    return df


def _target_controls(df):
    """Account selector for the action panel below the table."""
    options = df["username"].tolist()
    st.markdown(
        '<div style="font-size:.78rem;font-weight:700;color:var(--text-1);'
        'margin:1rem 0 .35rem;">Selected account</div>',
        unsafe_allow_html=True,
    )
    idx = options.index(st.session_state["um_target"]) if st.session_state["um_target"] in options else 0
    st.selectbox(
        "Selected account", options, index=idx, key="um_target",
        label_visibility="collapsed",
    )


# ══════════════════════════════════════════════════════════════════════
#  PASSWORD RESET (F-06)
# ══════════════════════════════════════════════════════════════════════

def _render_password_reset(username: str):
    section_header("shield-check", "Reset Password")
    st.caption(
        "Sets a new password directly. The user is not emailed and no reset code is "
        "issued — hand them the new password over a channel you trust."
    )
    with st.form(f"um_pw_{username}", clear_on_submit=True):
        new_pw = st.text_input("New password", type="password",
                               key=f"um_pw_new_{username}")
        confirm_pw = st.text_input("Confirm new password", type="password",
                                   key=f"um_pw_confirm_{username}")
        submitted = st_compat.form_submit_button("Change password", type="primary")
    if submitted:
        if new_pw != confirm_pw:
            st.error("The two passwords do not match.")
        elif len(new_pw or "") < 8:
            st.error("The new password must be at least 8 characters long.")
        else:
            ok, msg = db.admin_set_password(username, new_pw)
            if ok:
                _park(msg, "success")
                st.rerun()
            else:
                st.error(msg)


# ══════════════════════════════════════════════════════════════════════
#  DANGER ZONE — DELETION PREVIEW (F-04)
# ══════════════════════════════════════════════════════════════════════

def _preview_row(key: str, value) -> str:
    return (
        f'<div class="confirm-row">'
        f'<span class="confirm-row-key">{esc(key)}</span>'
        f'<span class="confirm-row-val">{esc(value)}</span>'
        f"</div>"
    )


def _render_deletion_preview(preview: dict, acting_user: str):
    """The scrollable 'here is exactly what will be destroyed' panel."""
    n_fb = preview["feedback_count"]
    n_corr = preview["admin_corrections"]
    cat_summary = ", ".join(f"{c} ({k})" for c, k in
                            sorted(preview["categories"].items(), key=lambda kv: -kv[1])) or "—"
    sess_summary = ", ".join(preview["sessions"]) or "—"

    st.markdown(
        '<div class="confirm-summary">'
        + _preview_row("Account", f'{preview["username"]} · {preview["full_name"]}')
        + _preview_row("Email", preview["email"] or "—")
        + _preview_row("Role", preview["role"])
        + _preview_row("Level", preview["level"] or "—")
        + _preview_row("Registered", preview["created_at"] or "—")
        + _preview_row("Feedback records", f"{n_fb} (all removed)")
        + _preview_row("Categories affected", cat_summary)
        + _preview_row("Sessions affected", sess_summary)
        + _preview_row("Admin corrections lost", f"{n_corr} (these are the training labels)")
        + _preview_row("First submission", preview["first_submission"] or "—")
        + _preview_row("Last submission", preview["last_submission"] or "—")
        + _preview_row("Pending reset codes", f"{preview['pending_resets']} (revoked)")
        + "</div>",
        unsafe_allow_html=True,
    )

    if n_fb:
        html_alert(
            f"{n_fb} feedback record(s) will be permanently deleted. Every dashboard, "
            "chart, CSV export, session statistic and the supervised model's training "
            "set changes as a result — this cannot be undone from the reporting pages.",
            "warning",
        )
    else:
        html_alert("This account has no feedback records, so only the login will be removed.", "info")

    if n_corr:
        html_alert(
            f"{n_corr} of those records carry an administrator's sentiment correction. "
            "Those corrections are ground truth for train_model.py and will not be "
            "recoverable except through Restore.",
            "warning",
        )

    if preview["is_self"]:
        html_alert(
            "This is the account you are signed in with. Self-deletion is blocked — ask "
            "another administrator to do it, or sign in as someone else first.",
            "error",
        )

    if preview["is_last_admin"]:
        html_alert(
            "This is the only administrator account. Deleting it locks every "
            "administrative feature out of the system, so the server will refuse the "
            "request. Create a second administrator first.",
            "error",
        )

    if preview["is_seeded_admin"]:
        html_alert(
            "This is a seeded administrator from config.py. It is not re-created on the "
            "next start-up, but restoring it afterwards would bring back its original "
            "config password.",
            "warning",
        )


def _render_danger_zone(preview: dict, acting_user: str):
    section_header("alert-triangle", "Danger Zone")
    st.markdown(
        '<div class="danger-zone">'
        '<div class="danger-banner">'
        f'{i("alert-triangle", 18, "#dc2626")}'
        "<div><strong>Permanent deletion.</strong> This removes the login and "
        "cascades to every record the account owns. It is not a soft delete and it "
        "is not a ban.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        _render_deletion_preview(preview, acting_user)

    blocked = preview["is_self"] or preview["is_last_admin"] or preview["role"] == "admin"
    st.markdown("<div style='height:.4rem;'></div>", unsafe_allow_html=True)
    if blocked:
        if preview["role"] == "admin":
            html_alert(
                "Administrator accounts cannot be deleted through the UI. "
                "The admin password is hardcoded in config.py — edit it directly "
                "if you need to change administrator access.",
                "error",
            )
        st_compat.button(
            "Delete account…",
            icon=":material/delete:",
            type="primary",
            disabled=True,
            width="stretch",
            key=f"um_delete_{preview['username']}",
        )
        return

    reason = st.text_input(
        "Reason for deletion (recorded in the audit log)",
        key=f"um_reason_{preview['username']}",
        placeholder="e.g. duplicate account created during registration testing",
    )

    if st_compat.button(
        "Review and delete…",
        icon=":material/delete:",
        width="stretch",
        key=f"um_delete_{preview['username']}",
    ):
        st.session_state["um_pending_delete"] = preview["username"]
        st.session_state["um_pending_reason"] = reason
        st.session_state.pop("um_typed_username", None)
        st.session_state.pop("um_typed_admin_phrase", None)
        st.session_state.pop("um_acknowledged", None)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  TWO-TIER CONFIRMATION DIALOG (F-05)
# ══════════════════════════════════════════════════════════════════════

def _render_confirm_dialog(target: str, acting_user: str, reason: str):
    """The modal. Returns True only when the operator has satisfied every gate."""
    preview = db.get_user_deletion_preview(target, acting_user=acting_user)
    if preview is None:
        st.session_state.pop("um_pending_delete", None)
        html_alert("That account no longer exists.", "warning")
        return False

    is_admin = preview["role"] == "admin"
    blocked = preview["is_self"] or preview["is_last_admin"] or is_admin

    @st_compat.dialog("Confirm permanent deletion", width="large")
    def _dialog():
        st.markdown(
            f'<div class="danger-banner">'
            f'{i("alert-triangle", 18, "#dc2626")}'
            f"<div>This removes <strong>{esc(preview['username'])}</strong> and "
            f"<strong>{esc(preview['feedback_count'])}</strong> feedback record(s) "
            "permanently. There is no undo in this dialog.</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="confirm-summary">'
            + _preview_row("Account", f'{preview["username"]} · {preview["full_name"]}')
            + _preview_row("Feedback records removed", preview["feedback_count"])
            + _preview_row("Admin corrections removed", preview["admin_corrections"])
            + _preview_row("Pending reset codes revoked", preview["pending_resets"])
            + _preview_row("Reason", reason or "— (none given)")
            + _preview_row("Performed by", acting_user)
            + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="confirm-instruction">To continue, type '
            f'<code>{esc(preview["username"])}</code> exactly.</div>',
            unsafe_allow_html=True,
        )
        typed = st.text_input(
            f'Type "{preview["username"]}" to confirm',
            key="um_typed_username", placeholder=preview["username"], label_visibility="collapsed",
        )
        username_ok = typed == preview["username"]

        admin_phrase_ok = True
        if is_admin:
            st.markdown(
                f'<div class="confirm-instruction">This is an <strong>administrator</strong> '
                f'account. Also type <code>{ADMIN_DELETE_PHRASE}</code>.</div>',
                unsafe_allow_html=True,
            )
            typed_phrase = st.text_input(
                f'Type "{ADMIN_DELETE_PHRASE}" to confirm',
                key="um_typed_admin_phrase", placeholder=ADMIN_DELETE_PHRASE,
                label_visibility="collapsed",
            )
            admin_phrase_ok = typed_phrase.strip() == ADMIN_DELETE_PHRASE

        acknowledged = st.checkbox(
            "I understand this permanently deletes the account, its feedback, and any "
            "admin sentiment corrections, and that restoring later is a separate manual step.",
            key="um_acknowledged",
        )

        pending_reasons = []
        if blocked:
            pending_reasons.append(
                "this is your own account" if preview["is_self"]
                else "this is the last administrator account"
            )
        if not username_ok:
            pending_reasons.append("the username does not match yet")
        if is_admin and not admin_phrase_ok:
            pending_reasons.append(f'"{ADMIN_DELETE_PHRASE}" has not been typed')
        if not acknowledged:
            pending_reasons.append("the acknowledgement box is unticked")

        c1, c2 = st.columns(2)
        with c1:
            confirm = st_compat.button(
                "Delete permanently",
                icon=":material/delete:",
                type="primary",
                disabled=bool(pending_reasons),
                width="stretch",
                key="um_confirm_delete",
            )
        with c2:
            if st_compat.button("Cancel", width="stretch", key="um_cancel_delete"):
                st.session_state.pop("um_pending_delete", None)
                st.rerun()

        if pending_reasons:
            st.caption("Still required: " + "; ".join(pending_reasons) + ".")
        elif confirm:
            st.session_state["um_delete_now"] = True
            st.rerun()

    _dialog()
    return bool(st.session_state.get("um_delete_now"))


# ══════════════════════════════════════════════════════════════════════
#  AUDIT TRAIL + RESTORE (F-07)
# ══════════════════════════════════════════════════════════════════════

def _countdown_class(days_left: int) -> str:
    """Tone for the retention countdown, escalating as the window closes.

    Severity is driven by days remaining rather than by absolute age, because
    what the number is for is deciding whether to act now. Two days and zero
    days are both "urgent" in the way that matters, whatever the dates are.
    """
    if days_left <= 1:
        return "is-critical"   # last chance; the next sweep removes the row
    if days_left <= 2:
        return "is-urgent"
    return "is-normal"


def _countdown_text(days_left: int) -> str:
    """Human wording for the countdown, stated as whole days.

    Never says "0 days left" on its own, which reads as broken rather than as
    imminent; the last day is named instead.
    """
    if days_left <= 0:
        return "Last day — removed after today"
    if days_left == 1:
        return "1 day left to restore"
    return f"{days_left} days left to restore"


def _render_audit_log():
    section_header("history", "Deletion Audit Trail")
    st.caption(
        f"Deletions and restorations from the last {db.AUDIT_RETENTION_DAYS} days. "
        "A deletion stays here — with the full snapshot Restore needs — until "
        f"that window closes, then it is permanently removed so this page keeps "
        "showing what is current rather than growing forever. Restore an account "
        f"within {db.AUDIT_RETENTION_DAYS} days or accept that it is gone. Each "
        "entry below counts down the days it has left."
    )
    log = db.list_audit_log(limit=50)
    if log.empty:
        # Distinguish "nothing has happened" from "everything aged out", because
        # they look identical once rows are purged and an administrator
        # wondering "did my deletion get lost?" deserves a real answer.
        empty_state(
            "history",
            f"Nothing in the Last {db.AUDIT_RETENTION_DAYS} Days",
            f"Deletions and restorations are kept for {db.AUDIT_RETENTION_DAYS} days "
            f"and then removed, so this panel is empty until something is deleted — "
            "or until older entries have aged out.",
        )
        return

    for _, row in log.iterrows():
        action = row["action"]
        is_delete = action == "DELETE_USER"
        # `restored_at` is set by `restore_user` on the deletion it acted on, so
        # this distinguishes "this deletion was undone" from "this username was
        # taken by a different, later registration" — which is all the old
        # username-in-the-users-table check could see, and which made a
        # successful restore render as "Cannot restore: registered again".
        already_restored = bool(row.get("restored_at"))
        icon_name = "trash-2" if is_delete else "rotate-ccw"
        # Whole days before this entry — and the restore data it carries — are
        # purged for good. Shown on every row, restored ones included, because a
        # restored entry is still a row that will disappear.
        days_left = int(row.get("days_remaining") or 0)
        # The tint is a design-system token rather than a literal hex, for two
        # reasons. `--green-text` is the AA-safe step: the icon is a 15px glyph
        # and needs 3:1 (WCAG 1.4.11), which the fill green `#059669` only just
        # clears at 3.77:1, so a literal here would be one accidental change
        # away from failing. And `var()` resolves inside an inline style, so the
        # chip's `color-mix(..., currentColor, ...)` in the stylesheet derives
        # its background from whatever the token evaluates to — re-tinting the
        # palette needs no change here.
        #
        # The glyph itself is left on `currentColor` (the `icon()` default) so
        # it inherits from the wrapper's inline colour rather than repeating
        # the value a second time in a second place.
        tint = "var(--red)" if is_delete else "var(--green-text)"
        when = str(row["performed_at"] or "")[:16]
        target = row["target_username"]

        st.markdown(
            f'<div class="audit-log-row">'
            f'<div class="audit-log-icon" style="color:{tint};">{i(icon_name, 15)}</div>'
            f'<div class="audit-log-body">'
            f'<div class="audit-log-title">'
            f'{"Deleted" if is_delete else "Restored"} <strong>{esc(target)}</strong>'
            f'<span class="audit-log-meta">by {esc(row["performed_by"] or "unknown")}'
            f' · {esc(when)}</span></div>'
            f'<div class="audit-log-reason">{esc(row["reason"] or "No reason recorded")}</div>'
            f'</div>'
            f'<div class="audit-log-stats">'
            f'<span>{esc(row["feedback_rows_deleted"])} feedback</span>'
            f'<span class="audit-log-countdown {esc(_countdown_class(days_left))}">'
            f'{esc(_countdown_text(days_left))}</span>'
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Only a DELETE is restorable, and only while the username is free.
        # A deletion whose window has closed is no longer a row at all (F-08),
        # so there is no "expired" case to render here — anything still listed
        # is inside the window and restorable.
        if not is_delete or not row["snapshot"]:
            continue

        # Already undone. The entry itself stays, because an audit trail that
        # rewrote itself would be worthless — but every trace of the restore
        # control is cleared, so nothing is left on screen implying the account
        # is still missing.
        if already_restored:
            st.caption(
                f"Restored on {str(row['restored_at'])[:16].replace('T', ' ')} — this "
                "deletion has been undone and the account is active again, so there "
                "is nothing left to restore. The entry is kept as a record and is "
                f"removed with the rest of the audit trail in "
                f"{db.AUDIT_RETENTION_DAYS} days."
            )
            continue

        if db.username_exists(target):
            # Name the cause. The old wording — "'X' is in use again, so this
            # deletion cannot be restored" — was accurate but left an
            # administrator who deleted an account a week ago with no way to
            # connect it to a re-registration that happened since. It reads as
            # a retention-window problem, which is the one thing it is not: the
            # row is well inside the 5 days, and no amount of waiting will
            # change the outcome. Spelling out that the name is taken again
            # makes the caption self-explanatory and unblocks the decision
            # (rename the new account, or leave it).
            st.caption(
                f"Cannot restore — '{target}' has been registered again since "
                "this deletion. The audit entry itself is still inside the "
                f"{db.AUDIT_RETENTION_DAYS}-day window."
            )
            continue
        if st_compat.button(
            f"Restore {target}", icon=":material/undo:",
            key=f"um_restore_{int(row['id'])}",
        ):
            # Arms a confirmation instead of restoring outright. A restore
            # rewrites the live account row from the snapshot, and this list can
            # hold several identically shaped Restore buttons at once — which is
            # precisely where a single stray press acts on the wrong account.
            st.session_state["um_pending_restore"] = int(row["id"])
            st.session_state["um_pending_restore_name"] = target
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  SENTIMENT MODEL TRAINING
# ══════════════════════════════════════════════════════════════════════

# Per-class colours for the training-readiness row. Reused from the engine
# card on the dashboard rather than introducing a second palette: these are the
# same three sentiment classes, and a reader who learns "green means Positive"
# on the dashboard should not have to learn it again here.
_CLASS_TINT = {
    "Positive": ("#d1fae5", "#a7f3d0", "#047857"),
    "Neutral": ("#e0f2fe", "#bae6fd", "#0e7490"),
    "Negative": ("#fee2e2", "#fecaca", "#b91c1c"),
}


def _render_model_training(acting_user: str):
    """Lets an administrator turn their corrections into a live model.

    Why this is here at all
    ----------------------
    The whole supervised half of the sentiment engine was unreachable without
    a shell. `train_model.py` is a CLI, so on Streamlit Community Cloud — where
    there is no shell, no SSH and no cron — the model could never be trained at
    all. Every admin correction an examiner made fed a database column that
    nothing read. The engine advertised a trained-classifier stage and would
    never run one.

    Why it is two clicks
    --------------------
    Training overwrites the model the app is currently classifying with, and
    `min` accuracy is not enforced: a thin correction set produces a model that
    scores below 60% and is *still* loaded, because a worse-than-nothing
    classifier is better than one an admin cannot create at all. That trade is
    fine once and annoying if it happens by accident, so the button arms a
    confirmation that restates the sample count and the last model's accuracy
    before anything is written. It follows the same rule as the deletion flow
    on this page: no irreversible action is one press.

    Why the readiness is shown first
    --------------------------------
    `training_readiness()` is a pure read, so the card can answer "can I train,
    and if not, how far off am I?" on every render. The old code only discovered
    the threshold by running the trainer and reading its output — which meant
    finding out you were 12 corrections short *after* pressing the button.
    """
    section_header("cpu", "Sentiment Model Training")
    st.markdown("<div style='height:.55rem;'></div>", unsafe_allow_html=True)

    # Imported here, not at module scope. `train_model` imports scikit-learn
    # eagerly, which costs a second or two of import time and a few hundred MB
    # of resident memory on a free Cloud container — paid on *every* page of the
    # app to serve a button that most sessions never press. Lazy import means
    # the cost is paid by the run that actually trains.
    try:
        import train_model
    except Exception as exc:  # pragma: no cover - import-time environment fault
        html_alert(
            f"The trainer could not be loaded ({type(exc).__name__}: {exc}). "
            "Sentiment analysis continues to use the built-in rule engine.",
            "error",
        )
        return

    try:
        info = train_model.training_readiness()
    except Exception as exc:
        # A read-only open can fail on a locked or read-only filesystem, and
        # the Cloud container is sometimes exactly that. Saying so beats
        # rendering a card full of zeroes that look like "no corrections yet".
        html_alert(
            f"Training readiness could not be read ({type(exc).__name__}: {exc}). "
            "Sentiment analysis continues to use the built-in rule engine.",
            "error",
        )
        return

    required = info["required"]
    usable = info["usable"]
    ready = info["ready"]

    from sentiment import engine_status  # local: keeps the module import light

    try:
        status = engine_status()
    except Exception as exc:
        status = {"trained_model_available": False, "trained_model_meta": {},
                  "engine_problems": [f"engine status unavailable: {exc}"]}

    meta = status.get("trained_model_meta") or {}
    has_model = bool(status.get("trained_model_available"))

    # ── Current model ────────────────────────────────────────────────
    if has_model:
        acc = meta.get("accuracy")
        f1 = meta.get("macro_f1")
        acc_txt = f"{float(acc):.0%}" if isinstance(acc, (int, float)) else "—"
        f1_txt = f"{float(f1):.0%}" if isinstance(f1, (int, float)) else "—"
        state_line = (
            f"Live now · {esc(str(meta.get('engine_type', 'trained classifier')))} "
            f"· trained {esc(str(meta.get('trained_at', 'unknown'))[:10])} "
            f"on {esc(str(meta.get('n_samples', '?')))} samples"
        )
        engine_bg, engine_border, engine_color = "#d1fae5", "#a7f3d0", "#047857"
    else:
        acc_txt = f1_txt = "—"
        state_line = ("No trained model is loaded. Sentiment labels currently come "
                      "from the VADER Academic Pro rule engine, which is fully "
                      "functional — training is an improvement, not a prerequisite.")
        engine_bg, engine_border, engine_color = "#f1f5f9", "#cbd5e1", "#475569"

    dist = info["distribution"]
    # Every placeholder in this builder is esc()'d, class names included. The
    # class names come from `training_readiness`'s own LABELS constant and could
    # never hold markup, but `esc()` on a value that provably cannot need it
    # costs nothing and keeps the XSS gate reading *this* line as the proof —
    # rather than an allowlist entry that a future edit could invalidate
    # silently. See tests/test_xss_static.py.
    dist_cells = "".join(
        f'<div class="engine-trained-stat">'
        f'<div class="engine-trained-val" style="color:{esc(_CLASS_TINT[cls][2])};">'
        f'{esc(dist.get(cls, 0))}</div>'
        f'<div class="engine-trained-lbl">{esc(cls)}</div>'
        f"</div>"
        for cls in ("Positive", "Neutral", "Negative")
    )

    problems = status.get("engine_problems") or []
    problem_html = "".join(
        f'<div class="engine-error-pill">{i("alert-triangle", 13, "#dc2626")} '
        f"{esc(str(p)[:160])}</div>"
        for p in problems
    )

    st.markdown(
        f'<div class="engine-status-card">'
        f'<div class="engine-status-header">'
        f'<div class="engine-status-left">'
        f'<div class="engine-status-icon" style="background:{engine_bg};'
        f'border-color:{engine_border};">{i("cpu", 22, engine_color)}</div>'
        f"<div>"
        f'<div class="engine-status-title">Supervised Sentiment Classifier</div>'
        f'<div class="engine-active-pill" style="background:{engine_bg};'
        f'border-color:{engine_border};color:{engine_color};">'
        f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
        f'background:{engine_color};margin-right:.4rem;flex-shrink:0;"></span>'
        f'{"Model active" if has_model else "Rule engine only"}'
        f"</div>"
        f"</div>"
        f"</div>"
        f'<div class="engine-conf-badge">'
        f'{i("shield", 13, "#7c3aed")} Held-out Accuracy: '
        f"<strong>{acc_txt}</strong> · Macro F1: <strong>{f1_txt}</strong>"
        f"</div>"
        f"</div>"
        f'<div class="engine-trained-row">'
        f'<div class="engine-trained-stat">'
        f'<div class="engine-trained-val" style="color:#2563eb;">{esc(usable)}</div>'
        f'<div class="engine-trained-lbl">Corrections Ready</div>'
        f"</div>"
        f'<div class="engine-trained-stat">'
        f'<div class="engine-trained-val" style="color:#7c3aed;">{esc(required)}</div>'
        f'<div class="engine-trained-lbl">Required</div>'
        f"</div>"
        f"{dist_cells}"
        f"</div>"
        f"{problem_html}"
        f'<div class="engine-metric-box" style="margin-top:.7rem;">'
        f'<div class="engine-metric-lbl" style="text-align:left;">{state_line}</div>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

    # ── Readiness ────────────────────────────────────────────────────
    if ready:
        html_alert(
            f"{usable} verified correction{'s' if usable != 1 else ''} are ready — "
            f"enough to train ({required} required). Training reads every corrected "
            "comment across all sessions, holds out 20% to measure itself, and "
            "keeps the current model as sentiment_classifier.prev.pkl.",
            "success",
        )
    else:
        progress_bar("Corrections toward a trainable model", usable, required,
                     color="#2563eb")
        st.markdown("<div style='height:.45rem;'></div>", unsafe_allow_html=True)
        html_alert(
            f"{usable} of {required} corrections recorded — "
            f"{info['remaining']} more to go. Open Full Dashboard, review the "
            "comments, and set the sentiment where the engine got it wrong. "
            "The rule engine keeps working meanwhile; nothing is blocked.",
            "info",
        )

    # The threshold counts *usable* corrections, but a 40-comment set split
    # 38/1/1 cannot be stratified and cannot be evaluated per class. Saying so
    # before the admin spends an afternoon is the difference between "add 3
    # more comments" and "rebuild my whole correction set".
    advisory = []
    if info["missing_classes"]:
        advisory.append(
            "no corrections yet for " + ", ".join(info["missing_classes"])
        )
    if info["singleton_classes"]:
        advisory.append(
            "only one correction for " + ", ".join(info["singleton_classes"])
            + " — a class needs at least two to be held out and scored"
        )
    if advisory:
        st.markdown("<div style='height:.35rem;'></div>", unsafe_allow_html=True)
        html_alert("Class balance: " + "; ".join(advisory) + ".", "warning")

    st.markdown("<div style='height:.55rem;'></div>", unsafe_allow_html=True)

    # ── The action ───────────────────────────────────────────────────
    if not ready:
        # Disabled with the reason on screen, rather than a button that fails
        # when pressed. A button that greys out and says nothing is the single
        # most common way a UI hides a rule from its user.
        st_compat.button(
            "Train model now", icon=":material/model_training:",
            key="um_train_disabled", disabled=True, use_container_width=True,
        )
        st.caption(
            f"Unavailable until {required} corrections exist "
            f"({usable} so far). Every correction you make on the Full Dashboard "
            "counts toward this."
        )
        return

    if st.session_state.get("um_train_armed"):
        html_alert(
            f"Train now from {usable} corrections? The model currently scoring "
            "your feedback will be replaced. The previous one is kept as "
            "sentiment_classifier.prev.pkl, and the engine falls back to the rule "
            "pipeline if the new one cannot be loaded.",
            "warning",
        )
        a1, a2 = st.columns(2, gap="medium")
        with a1:
            if st_compat.button(
                "Cancel", key="um_train_cancel", use_container_width=True,
            ):
                st.session_state.pop("um_train_armed", None)
                st.rerun()
        with a2:
            if st_compat.button(
                "Yes, train the model", key="um_train_go", type="primary",
                icon=":material/check:", use_container_width=True,
            ):
                st.session_state.pop("um_train_armed", None)
                _run_training()
        return

    if st_compat.button(
        "Train model now", icon=":material/model_training:",
        key="um_train_arm", use_container_width=True,
    ):
        st.session_state["um_train_armed"] = True
        st.rerun()


def _run_training():
    """Trains in-process, then parks the outcome as a result dialog.

    Runs in the Streamlit script thread rather than a subprocess. Cloud
    containers have no shell to spawn, and a subprocess would also mean the
    freshly written `.pkl` lands while this process still holds the old one in
    `st.cache_resource` — so the button would report success and change
    nothing. `invalidate_trained_model` closes that gap; see its docstring.
    """
    import train_model
    from sentiment import invalidate_trained_model

    with st.spinner("Training the sentiment classifier…"):
        try:
            result = train_model.train()
        except Exception as exc:
            # `train` catches its own I/O and backend failures, so reaching
            # here means something it did not anticipate. Swallowing it into a
            # red dialog beats the traceback, which would take down the whole
            # admin page and read as a crash of the application itself.
            result = {
                "ok": False,
                "message": f"Training failed unexpectedly "
                           f"({type(exc).__name__}: {exc}).",
                "log": [],
            }

    if result.get("ok"):
        invalidate_trained_model()
        notes = " ".join(result.get("notes") or [])
        # The note and the standing guarantee are *combined*, not alternatives.
        # `notes or default` meant a low-accuracy warning replaced the sentence
        # explaining that scores are unaffected — so the admin learned their
        # quality problem and not the fact that it cannot corrupt the numbers
        # they are already reporting on. That is backwards: the weak-model case
        # is exactly when "it changes the label, never the score" matters most.
        details = " ".join(part for part in (notes, (
            "The model supplies the sentiment label only. Scores, polarity "
            "splits and confidences still come from the rule engine, so "
            "existing charts and averages are unaffected."
        )) if part)
        park_result_dialog(
            f"Trained on {result['samples']} corrections · "
            f"held-out accuracy {result['accuracy']:.0%} · "
            f"macro F1 {result['macro_f1']:.0%}. It is live now.",
            kind="success",
            title="Sentiment Model Trained",
            details=details,
            button_label="Done",
        )
    else:
        park_result_dialog(
            result.get("message") or "Training did not complete.",
            kind="error",
            title="Training Not Completed",
            details=" ".join(result.get("notes") or []) or None,
            button_label="Close",
        )
    st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  PAGE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
#  RESTORE CONFIRMATION DIALOG
# ══════════════════════════════════════════════════════════════════════

def _render_restore_dialog(audit_id: int, username: str, acting_user: str,
                           days_left: int):
    """The modal. Sets `um_restore_now` only when the operator confirms.

    Deliberately lighter than the deletion dialog: that one guards an
    irreversible act, this one guards a recoverable one. There is no typed
    username and no acknowledgement box, because the restore puts the account
    back the way it was rather than destroying anything — an administrator
    reversing a mistake should not have to type their way past a warning that
    overstates the risk.

    What it does spell out is the one thing that is genuinely surprising: the
    restore overwrites the current state of the account with the snapshot, and
    password-reset codes are not restored.
    """
    row = db.get_db().execute(
        "SELECT performed_at, feedback_rows_deleted, reason FROM admin_audit_log WHERE id = ?",
        (int(audit_id),),
    ).fetchone()
    deleted_at = str(row[0])[:16] if row else "an earlier date"
    fb_count = int(row[1]) if row else 0
    reason = (row[2] if row else "") or "No reason recorded"

    @st_compat.dialog("Confirm account restore", width="large")
    def _dialog():
        st.markdown(
            f'<div class="confirm-summary">'
            f'<div class="confirm-row">'
            f'<span class="confirm-row-key">Account</span>'
            f'<span class="confirm-row-val">{esc(username)}</span></div>'
            f'<div class="confirm-row">'
            f'<span class="confirm-row-key">Deleted on</span>'
            f'<span class="confirm-row-val">{esc(deleted_at)}</span></div>'
            f'<div class="confirm-row">'
            f'<span class="confirm-row-key">Reason recorded</span>'
            f'<span class="confirm-row-val">{esc(reason)}</span></div>'
            f'<div class="confirm-row">'
            f'<span class="confirm-row-key">Feedback restored</span>'
            f'<span class="confirm-row-val">{esc(fb_count)}</span></div>'
            f'<div class="confirm-row">'
            f'<span class="confirm-row-key">Days left to restore</span>'
            f'<span class="confirm-row-val">{esc(_countdown_text(days_left))}</span></div>'
            f'<div class="confirm-row">'
            f'<span class="confirm-row-key">Restored by</span>'
            f'<span class="confirm-row-val">{esc(acting_user)}</span></div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        html_alert(
            "The account returns with its original password, role, level and "
            "feedback. Any password-reset code issued to it is not restored — the "
            "student must request a new one.",
            "info",
        )

        c1, c2 = st.columns(2)
        with c1:
            confirm = st_compat.button(
                "Restore this account", icon=":material/undo:",
                type="primary", width="stretch", key="um_confirm_restore",
            )
        with c2:
            if st_compat.button("Cancel", width="stretch", key="um_cancel_restore"):
                st.session_state.pop("um_pending_restore", None)
                st.session_state.pop("um_pending_restore_name", None)
                st.rerun()

        if confirm:
            st.session_state["um_restore_now"] = True
            st.rerun()

    _dialog()
    return bool(st.session_state.get("um_restore_now"))


def show_user_management(acting_user: str, user: dict | None = None):
    """Renders the administrative user management screen."""
    page_header(
        "user-cog", "User Management",
        "Review every account, reset passwords, and permanently remove users with "
        "their feedback — every destructive action is written to the audit trail.",
        badge_text="Admin View",
    )
    _flash()

    df = _render_directory()
    if df is None:
        return
    _target_controls(df)

    target = st.session_state["um_target"]
    preview = db.get_user_deletion_preview(target, acting_user=acting_user)
    if preview is None:
        html_alert("That account no longer exists — refresh the list.", "warning")
        return

    total_fb = int(df["feedback_count"].sum())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        html_metric("users", len(df), "Accounts shown", "blue")
    with c2:
        html_metric("user", int((df["role"] == "student").sum()), "Students", "green")
    with c3:
        html_metric("shield", int((df["role"] == "admin").sum()), "Administrators", "purple")
    with c4:
        html_metric("inbox", total_fb, "Linked feedback", "gold")

    st.markdown("<div style='height:.6rem;'></div>", unsafe_allow_html=True)
    left, right = st.columns([1, 1], gap="large")
    with left:
        _render_password_reset(target)
    with right:
        html_alert(
            f"Managing <strong>{esc(target)}</strong> "
            f"({esc(preview['role'])}{' · ' + esc(preview['level']) if preview['level'] else ''}). "
            f"{esc(preview['feedback_count'])} feedback record(s) are linked to this account.",
            "info", raw=True,
        )

    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    _render_danger_zone(preview, acting_user)

    st.markdown("<div style='height:.75rem;'></div>", unsafe_allow_html=True)
    _render_audit_log()

    st.markdown("<div style='height:.75rem;'></div>", unsafe_allow_html=True)
    _render_model_training(acting_user)

    # ── Run the confirmation modal and, only if it fully succeeds, delete ──
    pending = st.session_state.get("um_pending_delete")
    if pending:
        confirmed = _render_confirm_dialog(
            pending, acting_user, st.session_state.get("um_pending_reason", "")
        )
        if confirmed:
            ok, msg, _stats = db.delete_user_account(
                pending,
                deleted_by=acting_user,
                reason=st.session_state.get("um_pending_reason", ""),
            )
            for key in ("um_pending_delete", "um_pending_reason", "um_delete_now",
                        "um_typed_username", "um_typed_admin_phrase", "um_acknowledged",
                        "um_target"):
                st.session_state.pop(key, None)
            _park(msg, "success" if ok else "error")
            st.rerun()

    # ── Restore: same two-step shape as the delete modal above ──
    pending_restore = st.session_state.get("um_pending_restore")
    if pending_restore:
        # Read the countdown from the live row rather than trusting whatever was
        # parked when the button was armed, so the dialog cannot quote a stale
        # "days left" after the page has been open a while.
        _entry = db.list_audit_log(limit=50)
        _entry = _entry[_entry["id"] == int(pending_restore)]
        _days_left = int(_entry["days_remaining"].iloc[0]) if len(_entry) else 0
        confirmed = _render_restore_dialog(
            int(pending_restore),
            st.session_state.get("um_pending_restore_name", "this account"),
            acting_user,
            _days_left,
        )
        if confirmed:
            ok, msg = db.restore_user(int(pending_restore), restored_by=acting_user)
            for key in ("um_pending_restore", "um_pending_restore_name",
                        "um_restore_now", "um_target"):
                st.session_state.pop(key, None)
            _park(msg, "success" if ok else "error")
            st.rerun()
