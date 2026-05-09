"""Email tool — SMTP send for notifications and transactional emails.

Config via env vars or credential vault:
    SMTP_HOST (default: smtp.gmail.com)
    SMTP_PORT (default: 587)
    SMTP_USER (your email / Gmail address)
    SMTP_PASS (app password — generate at https://myaccount.google.com/apppasswords)
    SMTP_FROM (sender address)

The credential vault's 'google/email' and 'google/app_password' keys
are automatically mapped to SMTP_USER and SMTP_PASS on sync.
"""
from __future__ import annotations
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

from tools.vault_aware_api import get_key


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    html: bool = False,
) -> Dict:
    """Send an email via SMTP. Vault-aware: checks google/email + google/app_password."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))

    user = get_key(
        vault_category="google", vault_key="email",
        env_var="SMTP_USER",
    )
    password = get_key(
        vault_category="google", vault_key="app_password",
        env_var="SMTP_PASS",
    )
    sender = get_key(
        vault_category="google", vault_key="email",
        env_var="SMTP_FROM",
    ) or user

    if not user or not password:
        return {
            "success": False,
            "error": (
                "SMTP not configured. Store in vault:\n"
                "  vault.set('google', 'email', 'you@gmail.com')\n"
                "  vault.set('google', 'app_password', 'xxxx xxxx xxxx xxxx')"
            ),
            "message_id": None,
        }

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type))

    recipients = [to]
    if cc:
        recipients.append(cc)
    if bcc:
        recipients.append(bcc)

    try:
        server = smtplib.SMTP(host, port, timeout=15)
        server.starttls()
        server.login(user, password)
        server.sendmail(sender, recipients, msg.as_string())
        message_id = msg["Message-ID"] if "Message-ID" in msg else None
        server.quit()
        return {"success": True, "message_id": message_id, "recipients": len(recipients)}
    except Exception as e:
        return {"success": False, "error": str(e), "message_id": None}
