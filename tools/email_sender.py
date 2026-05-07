"""Email tool — SMTP send for notifications and transactional emails."""
from __future__ import annotations
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    html: bool = False,
) -> Dict:
    """Send an email via SMTP.

    Config via env vars:
        SMTP_HOST (default: smtp.gmail.com)
        SMTP_PORT (default: 587)
        SMTP_USER (your email)
        SMTP_PASS (app password)
        SMTP_FROM (sender address)
    """
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("SMTP_FROM", user)

    if not user or not password:
        return {
            "success": False,
            "error": "SMTP not configured — set SMTP_USER and SMTP_PASS",
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
