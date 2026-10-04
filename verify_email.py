"""
verify_email.py
---------------
Prove the SMTP settings actually deliver mail, before a demonstration depends
on it.

    .venv\\Scripts\\python.exe verify_email.py                 # to the mailbox itself
    .venv\\Scripts\\python.exe verify_email.py someone@x.com   # to a real inbox

WHY THIS EXISTS
---------------
`is_email_configured()` only checks that four settings are non-empty. It cannot
tell you whether the host name is right, whether the port is blocked, or whether
the password is a real app password rather than a normal account password — and
those are the three failures that actually happen. On Streamlit Community Cloud
the only feedback loop for that is "ask a student to try it during the demo".

This script talks to the SMTP server directly and reports which of the three it
is, so the answer arrives before the presentation instead of during it.

It sends one real email. Credentials are read through `email_service._setting`,
which means it reads `.streamlit/secrets.toml` and the environment exactly the
way the deployed app does — so passing here is evidence about the same values the
app will use.

IT NEEDS THE SECRET KEYS
-----------------------
    SMTP_HOST       smtp.gmail.com
    SMTP_PORT       587          (465 = implicit TLS, 587 = STARTTLS)
    SMTP_USERNAME   the sending mailbox
    SMTP_PASSWORD   an APP password, not the account password
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import email_service as E  # noqa: E402

results = []


def step(label, fn):
    try:
        detail = fn()
        results.append((label, True, detail or ""))
        print(f"  [PASS] {label}" + (f"  -- {detail}" if detail else ""))
    except Exception as exc:
        results.append((label, False, f"{type(exc).__name__}: {exc}"))
        print(f"  [FAIL] {label}  -- {type(exc).__name__}: {exc}")


def diagnose(exc: Exception) -> str:
    """Turn a raw SMTP failure into the one thing the reader has to change."""
    text = str(exc).lower()
    if "authentication" in text or "auth failed" in text or "535" in text:
        return (
            "the server rejected the credentials. For Gmail this is almost always "
            "an APP password that has been revoked, was copied with a stray space, "
            "or was replaced when 2-Step Verification was re-run. Create a new one "
            "at https://myaccount.google.com/apppasswords"
        )
    if "getaddrinfo" in text or "name or service not known" in text or "nodename" in text:
        return f"SMTP_HOST is wrong or unresolvable from this machine. Check '{E._setting('SMTP_HOST')}'."
    if "connection refused" in text:
        return "the host is reachable but that port is closed. Try SMTP_PORT = 465 instead of 587."
    if "timed out" in text or "timeout" in text:
        return (
            "the connection timed out — almost always a firewall or antivirus 'web "
            "protection' blocking outbound mail. Try a different network, or SMTP_PORT = 465."
        )
    if "ssl" in text or "certificate" in text or "handshake" in text:
        return "the TLS handshake failed. On port 465 this means implicit TLS; on 587 it means STARTTLS was blocked."
    if "refused" in text and "530" in str(exc):
        return (
            "the server requires authentication it did not get. Check SMTP_USERNAME, "
            "and that SMTP_FROM_EMAIL (if set) is the same address."
        )
    return "unrecognised failure — read the message above"


def main() -> int:
    print("=" * 74)
    print("  Email (SMTP) verification")
    print("=" * 74)

    host = E._setting("SMTP_HOST")
    username = E._setting("SMTP_USERNAME")
    password = E._setting("SMTP_PASSWORD")
    port_raw = E._setting("SMTP_PORT")

    print(f"\n  reading configuration the way the app does "
          f"(secrets first, then environment)\n")
    for name, value in (("SMTP_HOST", host), ("SMTP_PORT", port_raw),
                        ("SMTP_USERNAME", username), ("SMTP_PASSWORD", password)):
        if value is None:
            print(f"    {name:<16} NOT SET")
        else:
            # Never print a secret, not even masked-length information that
            # invites a screenshot to leak it.
            shown = "<set, hidden>" if "PASSWORD" in name else f'"{value}"'
            print(f"    {name:<16} {shown}")

    if not E.is_email_configured():
        print("\n  SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD must all be set.")
        print("  Add them to .streamlit/secrets.toml, or to the Streamlit Cloud")
        print("  dashboard under Settings -> Secrets, then run this again.\n")
        return 2

    port = int(port_raw or 587)
    recipient = sys.argv[1].strip() if len(sys.argv) > 1 else (username or "")
    if not recipient:
        print("\n  No recipient: pass one, e.g. verify_email.py you@gmail.com\n")
        return 2

    print(f"\n  sending a test message to {recipient} via {host}:{port}\n")

    def check_configured():
        return f"{host}:{port} as {username}"

    def check_connect():
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as s:
                s.ehlo()
                return "TLS handshake OK (implicit)"
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            s.starttls(context=context)
            s.ehlo()
            return "TLS handshake OK (STARTTLS)"

    def check_login():
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as s:
                s.login(username, password)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls(context=context)
                s.login(username, password)
        return "credentials accepted"

    def check_send():
        ok, msg = E.send_otp_email(recipient, "SMTP verification", "000000", 15)
        if not ok:
            raise RuntimeError(msg)
        return f"message accepted for delivery to {recipient}"

    step("configuration is complete", check_configured)
    step("can reach the server and negotiate TLS", check_connect)
    step("the server accepts the credentials", check_login)
    step("a real message was sent", check_send)

    failed = [r for r in results if not r[1]]
    print()
    if failed:
        print("  WHAT TO CHANGE")
        print("  " + "-" * 60)
        for label, _, detail in failed:
            print(f"  {label}")
            print(f"    -> {diagnose(Exception(detail))}")
        print()
        return 1

    print("  All checks passed. Delivery is working — do the same under")
    print("  Streamlit Cloud -> Settings -> Secrets and restart the app.\n")
    print("  Note: 'accepted for delivery' is the server's promise, not proof the")
    print("  message arrived. If it does not appear, check spam/quarantine and any")
    print("  organisational filter.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())