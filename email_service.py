"""
email_service.py
-----------------
All outbound email lives here: account registration confirmation,
password-reset one-time codes, and feedback-submission/completion
acknowledgements.

Configuration — set these in `.streamlit/secrets.toml` (preferred) or as
environment variables (see SETUP_GUIDE.md § "Setting up email"):

    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       e.g. 587
    SMTP_USERNAME   the mailbox that sends the emails
    SMTP_PASSWORD   an app password (NOT your normal account password)
    SMTP_FROM_EMAIL defaults to SMTP_USERNAME if not set

If these aren't configured, `is_email_configured()` returns False and
every send_* function below returns (False, "not configured") instead of
raising — the app keeps working (OTP/registration/completion emails are
simply skipped, and the UI tells the person to note down the on-screen
OTP / to contact an admin instead).
"""

from __future__ import annotations

import html
import os
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st

from config import EMAIL_FROM_NAME


def _esc(text) -> str:
    """User-supplied text (name, category, username) must be escaped before
    going into the HTML email body — same reasoning as components.esc()."""
    return html.escape(str(text)) if text is not None else ""


# Alternative spellings accepted for the same setting.
#
# `SMTP_USER` is what DEPLOYMENT_GUIDE.md § 8.4 instructed people to create,
# while this module only ever read `SMTP_USERNAME`. Nothing warned about it: the
# key was accepted by Streamlit's secrets box, stored happily, and then ignored —
# so the app reported "Email delivery is not configured on this deployment"
# forever, no matter how carefully the instructions had been followed. The
# canonical name is tried first.
#
# Accepting both means a secret already entered under the documented name starts
# working on the next deploy, instead of requiring everyone to go and retype it.
_SETTING_ALIASES = {
    "SMTP_USERNAME": ("SMTP_USERNAME", "SMTP_USER"),
}


def _setting(key: str) -> str | None:
    """First non-empty value among `key` and any accepted alias of it.

    Secrets are still consulted before the environment. Each candidate is skipped
    when present but blank, so an empty placeholder cannot shadow a real value
    further down the list — the previous version returned the blank and stopped.
    """
    for name in _SETTING_ALIASES.get(key, (key,)):
        try:
            if name in st.secrets:
                value = st.secrets[name]
                if value is not None and str(value).strip():
                    return value
        except Exception:
            pass
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            return value
    return None


def is_email_configured() -> bool:
    return bool(_setting("SMTP_HOST") and _setting("SMTP_USERNAME") and _setting("SMTP_PASSWORD"))


# What a correct deployment must define, in the order the report reads best.
REQUIRED_SETTINGS = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD")
OPTIONAL_SETTINGS = ("SMTP_PORT", "SMTP_FROM_EMAIL")


def email_status() -> dict:
    """Which settings are present, which are missing, and where each came from.

    Names only — never a value, and never even the length of one. This is built
    to be shown to an administrator on a screen that may be shared or
    photographed, so there is nothing here worth stealing: only whether each key
    resolved, and whether from Streamlit's secrets box or the process environment.

    It exists because the previous failure mode was pure guesswork. A wrong or
    absent key produced one identical sentence — "email delivery is not
    configured" — on a public login page, telling whoever had to fix it nothing
    at all. Hours went into re-checking the SMTP host before it emerged that the
    deployment guide itself named the username key `SMTP_USER` while the code read
    `SMTP_USERNAME`. A report that names the missing key ends that immediately.
    """
    present, missing, sources = [], [], {}
    for key in REQUIRED_SETTINGS:
        if not _setting(key):
            missing.append(key)
            continue
        present.append(key)
        for candidate in _SETTING_ALIASES.get(key, (key,)):
            try:
                if candidate in st.secrets and st.secrets[candidate]:
                    sources[key] = f"secrets ({candidate})"
                    break
            except Exception:
                pass
            if os.environ.get(candidate):
                sources[key] = f"environment ({candidate})"
                break
        else:
            sources[key] = "resolved"
    return {
        "configured": not missing,
        "present": present,
        "missing": missing,
        "optional_missing": [k for k in OPTIONAL_SETTINGS if not _setting(k)],
        "sources": sources,
    }


def email_status_report() -> str:
    """A one-paragraph, log-safe summary of `email_status()`."""
    status = email_status()
    found = "; ".join(f"{k} from {v}" for k, v in status["sources"].items())
    if status["configured"]:
        extra = ("; optional not set: " + ", ".join(status["optional_missing"])
                 if status["optional_missing"] else "")
        return f"Email configured. {found}{extra}"
    return (
        "Email NOT configured. Missing required setting(s): "
        + ", ".join(status["missing"])
        + ". Already found: "
        + (found or "nothing")
        + ". Add the missing key(s) under Settings -> Secrets, then restart the app."
    )


def show_otp_on_screen() -> bool:
    """Whether the one-time reset code may ever be displayed in the page.

    Off unless explicitly switched on, and that default is the whole point.

    The code is the only thing standing between "know someone's email address"
    and "reset their password". When it is shown on screen, verification becomes
    meaningless: an attacker types the victim's address, reads the code off their
    own screen, and sets a new password. That is not a degraded experience, it
    is unrestricted account takeover — including of administrator accounts.

    So this fails CLOSED. If the deployment cannot deliver mail, password
    recovery is unavailable rather than insecure, and the page says so and
    points at the department instead.

    Turn it on deliberately (a secret or env var, `SHOW_OTP_ON_SCREEN`) only to
    demo the flow on a throwaway database with fake accounts. Never on the real
    one — and note it stays on even after SMTP starts working, because the
    fallback is also reached when a send *fails*, which is precisely when an
    attacker would be hoping to trigger it.
    """
    raw = _setting("SHOW_OTP_ON_SCREEN")
    return str(raw if raw is not None else "").strip().lower() in (
        "1", "true", "yes", "on")


def _send(to_email: str, subject: str, html_body: str, text_body: str) -> tuple[bool, str]:
    if not is_email_configured():
        return False, "Email is not configured on this deployment."

    host = _setting("SMTP_HOST")
    port = int(_setting("SMTP_PORT") or 587)
    username = _setting("SMTP_USERNAME")
    password = _setting("SMTP_PASSWORD")
    from_email = _setting("SMTP_FROM_EMAIL") or username

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{EMAIL_FROM_NAME} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Port 465 means "implicit TLS" (encrypted from the very first byte);
    # any other port (587 is standard) means "plaintext then STARTTLS
    # upgrade partway through." These are two different connection
    # sequences, not just a number — using the wrong one for a given
    # port is itself a common cause of "connection unexpectedly closed."
    # Some networks/firewalls block one of the two but not the other, so
    # SMTP_PORT = "465" is worth trying if 587 keeps failing (see
    # SETUP_GUIDE.md's email troubleshooting section).
    context = ssl.create_default_context()

    def _attempt():
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls(context=context)
                server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())

    last_error = None
    for attempt in (1, 2, 3):  # network blips during the TLS/login handshake
        try:                  # are common and often succeed on a later try
            _attempt()
            return True, "Sent."
        except Exception as exc:  # noqa: BLE001 — email must never crash the app
            last_error = exc
            if attempt < 3:
                time.sleep(1.5)

    # A timeout / "connection unexpectedly closed" almost always means the
    # network path to the SMTP server is blocked somewhere — a firewall,
    # antivirus "web protection," a campus/mobile network that blocks
    # outbound mail ports, or a VPN — not a wrong username/password (a bad
    # login gets a clear "authentication failed" response from the server
    # instead). Say so explicitly, since the raw exception text alone
    # doesn't make that distinction obvious.
    error_text = str(last_error)
    if isinstance(last_error, (TimeoutError, ConnectionError)) or "timed out" in error_text.lower() or "timeout" in error_text.lower():
        return False, (
            f"Could not reach the mail server ({error_text}). This almost always means the "
            f"network this app is running on is blocking outbound email — not a wrong password. "
            f"Try SMTP_PORT = \"465\" instead of 587 in secrets.toml, try a different network "
            f"(e.g. a mobile hotspot instead of home/campus Wi-Fi), and check whether antivirus "
            f"'web protection' is intercepting the connection. See SETUP_GUIDE.md's email "
            f"troubleshooting section for a command-line test you can run to confirm this."
        )
    return False, f"Could not send email: {last_error}"


def _wrap(title: str, body_html: str) -> str:
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;
                border:1px solid #e6eaf1;border-radius:12px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#2563eb,#7c3aed);padding:20px 24px;">
        <span style="color:#fff;font-weight:700;font-size:16px;">FUTO IFT Feedback System</span>
      </div>
      <div style="padding:24px;color:#0f172a;">
        <h2 style="margin:0 0 12px;font-size:18px;">{title}</h2>
        {body_html}
      </div>
      <div style="padding:14px 24px;background:#f8fafc;color:#94a3b8;font-size:11px;">
        Federal University of Technology, Owerri · Department of Information Technology
      </div>
    </div>
    """


def send_registration_email(to_email: str, full_name: str, username: str) -> tuple[bool, str]:
    body = f"""
    <p>Hi {_esc(full_name)},</p>
    <p>Your student account has been created successfully. You can now sign in with:</p>
    <p style="background:#f8fafc;padding:10px 14px;border-radius:8px;font-family:monospace;">
       Username: <b>{_esc(username)}</b></p>
    <p>If you did not create this account, please contact the IFT Department.</p>
    """
    return _send(to_email, "Welcome — your account is ready",
                 _wrap("Account created", body),
                 f"Hi {full_name}, your account (username: {username}) has been created.")


def send_otp_email(to_email: str, full_name: str, otp: str, expiry_minutes: int) -> tuple[bool, str]:
    body = f"""
    <p>Hi {_esc(full_name)},</p>
    <p>Use this code to reset your password. It expires in {int(expiry_minutes)} minutes.</p>
    <p style="background:#f8fafc;padding:14px;border-radius:8px;font-family:monospace;
              font-size:28px;letter-spacing:6px;text-align:center;font-weight:700;">{_esc(otp)}</p>
    <p>If you did not request a password reset, you can safely ignore this email.</p>
    """
    return _send(to_email, f"Your password reset code: {otp}",
                 _wrap("Password reset code", body),
                 f"Hi {full_name}, your password reset code is {otp}. It expires in {expiry_minutes} minutes.")


def send_password_changed_email(to_email: str, full_name: str) -> tuple[bool, str]:
    """Sent right after a password reset actually completes — a standard
    security notification distinct from the OTP email above (that one is
    sent when a reset is *requested*; this one confirms it *succeeded*,
    so the account owner finds out even if they weren't the one who did it)."""
    body = f"""
    <p>Hi {_esc(full_name)},</p>
    <p>This is a confirmation that your password was just changed.</p>
    <p>If this was you, no further action is needed. If you did <b>not</b> change your
       password, please contact the IFT Department immediately.</p>
    """
    return _send(to_email, "Your password was changed",
                 _wrap("Password changed", body),
                 f"Hi {full_name}, this confirms your password was just changed. "
                 f"If this wasn't you, contact the IFT Department immediately.")


def send_submission_email(to_email: str, full_name: str, category: str) -> tuple[bool, str]:
    body = f"""
    <p>Hi {_esc(full_name)},</p>
    <p>We've received your feedback for <b>{_esc(category)}</b>. Thank you for helping the
       department improve the IFT programme.</p>
    """
    return _send(to_email, f"Feedback received — {category}",
                 _wrap("Feedback received", body),
                 f"Hi {full_name}, we've received your feedback for {category}.")


def send_completion_email(to_email: str, full_name: str, session: str) -> tuple[bool, str]:
    body = f"""
    <p>Hi {_esc(full_name)},</p>
    <p>You've now submitted feedback across <b>all four categories</b> for the
       {_esc(session)} academic session — thank you for your complete and thoughtful input.</p>
    """
    return _send(to_email, "All feedback categories complete — thank you!",
                 _wrap("All categories complete", body),
                 f"Hi {full_name}, you've completed all feedback categories for {session}. Thank you!")
