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

import time

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

# How long an action confirmation stays on screen. Long enough to read a
# two-line message about what was just deleted or restored, short enough that it
# is not still there when the administrator moves on to the next thing.
_FLASH_SECONDS = 10


def _park(message: str, kind: str = "success"):
    st.session_state["um_flash"] = message
    st.session_state["um_flash_kind"] = kind
    # Stamped rather than left to a rerun to clear, because the clearing is timed
    # and a rerun is not: session_state has no expiry of its own.
    st.session_state["um_flash_at"] = time.time()


def _flash_remaining(now: float | None = None) -> float | None:
    """Seconds left before the parked confirmation clears. None if none is parked.

    Split out from `_flash` and given an injectable clock so the timing can be
    tested directly: `_flash` is wrapped in a Streamlit fragment, and a
    fragment-wrapped function cannot simply be called to exercise it.
    """
    if not st.session_state.get("um_flash"):
        return None
    now = time.time() if now is None else now
    parked = float(st.session_state.get("um_flash_at") or now)
    return _FLASH_SECONDS - (now - parked)


def _clear_flash() -> None:
    for key in ("um_flash", "um_flash_kind", "um_flash_at"):
        st.session_state.pop(key, None)


@st_compat.autorun_fragment("10s")
def _flash():
    """Shows the confirmation parked by an action, and clears it after 10s.

    Wrapped in a timed fragment because Streamlit has no timer of its own, and a
    message parked in session_state otherwise stays up until the next click —
    which is most of a session. Only this fragment re-runs, not the page.

    Returns quietly when nothing is parked, so the recurring tick costs almost
    nothing once the message has gone.
    """
    remaining = _flash_remaining()
    if remaining is None:
        return
    if remaining <= 0:
        _clear_flash()
        st_compat.rerun_fragment()
        return
    kind = st.session_state.get("um_flash_kind", "success")
    getattr(st, kind)(st.session_state["um_flash"])
    count = int(remaining) + 1
    st.caption(
        f"This message clears on its own in {count} second"
        f"{'s' if count != 1 else ''}."
    )


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
            "A correction overrides the rating on that record's charts, and it will not be "
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
    section_header("history", "Deletions Awaiting Restoration")
    st.caption(
        f"Every account deleted in the last {db.AUDIT_RETENTION_DAYS} days that "
        "can still be put back, each counting down the days it has left. An entry "
        "disappears the moment it is restored, so nothing is left behind to imply "
        "the work is still outstanding, and is deleted for good once its window "
        f"closes. Restore within {db.AUDIT_RETENTION_DAYS} days or accept that "
        "the account is gone."
    )
    # Only outstanding work is rendered. Restored deletions and restoration rows
    # are excluded by the query rather than filtered out per row below, so the
    # page cannot fall into rendering a state it was not written for.
    log = db.list_pending_deletions(limit=50)
    if log.empty:
        # Distinguish "nothing has happened" from "everything dealt with", because
        # they look identical once rows are purged and an administrator wondering
        # "did my deletion get lost?" deserves a real answer.
        empty_state(
            "history",
            "Nothing Awaiting Restoration",
            "No deleted account is currently restorable. An entry appears here "
            "the moment an account is deleted, and leaves again when it is "
            f"restored or after {db.AUDIT_RETENTION_DAYS} days.",
        )
        return

    for _, row in log.iterrows():
        # Every row here is a deletion awaiting restoration. `list_pending_deletions`
        # has already removed restored deletions, restoration rows and rows with no
        # snapshot, so the per-row branches that used to handle those states are
        # gone rather than left as dead code: a page that renders states its query
        # can no longer produce is a page nobody is testing.
        target = row["target_username"]
        when = str(row["performed_at"] or "")[:16]
        days_left = int(row.get("days_remaining") or 0)
        # The tint is a design-system token rather than a literal hex, for two
        # reasons. `--red` is the AA-safe step for the text, and `var()` resolves
        # inside an inline style, so the chip's `color-mix(..., currentColor, ...)`
        # in the stylesheet derives its background from whatever the token
        # evaluates to — re-tinting the palette needs no change here.
        #
        # The glyph is left on `currentColor` (the `icon()` default) so it inherits
        # from the wrapper's inline colour rather than repeating the value in a
        # second place.
        tint = "var(--red)"

        st.markdown(
            f'<div class="audit-log-row">'
            f'<div class="audit-log-icon" style="color:{tint};">{i("trash-2", 15)}</div>'
            f'<div class="audit-log-body">'
            f'<div class="audit-log-title">'
            f'Deleted <strong>{esc(target)}</strong>'
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

        # One case the query cannot filter out: the username may have been
        # re-registered since the deletion, in which case restoring would collide
        # with a live account. Name the cause rather than offering a button that
        # is guaranteed to be refused.
        if db.username_exists(target):
            # The old wording was accurate but unhelpful — it reads as a
            # retention-window problem, which is the one thing it is not: the row
            # is well inside the window and no amount of waiting will change the
            # outcome. Saying the name was taken again unblocks the decision
            # (rename the new account, or leave it).
            st.caption(
                f"Cannot restore — '{target}' has been registered again since "
                "this deletion, so putting it back would collide with that live "
                "account. The entry itself is still inside the "
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
