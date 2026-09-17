"""Sends notifications about tasks and filed documents.

Every notification is always recorded in-app (a `Notification` row, visible
in the frontend's Tasks view) -- that channel needs no configuration and
always "delivers" successfully by definition. Email and Slack are optional
extra channels, active only when their environment variables are set:

- Email: SMTP_HOST (also SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
  SMTP_USE_TLS -- all optional with sane defaults). `recipient` is used as
  the To: address, so it needs to be an email address for this channel to
  do anything.
- Slack: SLACK_WEBHOOK_URL (an incoming webhook URL). Posts the message to
  that webhook; `recipient` is included in the message text since a single
  webhook usually maps to one channel, not a directory of users.

A failure on an external channel is caught and stored on the Notification
row (`delivered=False`, `error=...`) rather than raising -- a Slack outage
should never block approving a document.
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from sqlalchemy.orm import Session

from .models import Notification


def _send_email(recipient: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return  # email channel not configured -- silently skip

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM", "relook@localhost")
    msg["To"] = recipient
    msg.set_content(body)

    port = int(os.environ.get("SMTP_PORT", "587"))
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() != "false"

    with smtplib.SMTP(host, port, timeout=10) as server:
        if use_tls:
            server.starttls()
        user = os.environ.get("SMTP_USER")
        password = os.environ.get("SMTP_PASSWORD")
        if user and password:
            server.login(user, password)
        server.send_message(msg)


def _send_slack(recipient: str, message: str) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return  # slack channel not configured -- silently skip

    payload = json.dumps({"text": f"[{recipient}] {message}"}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Slack webhook returned HTTP {resp.status}")


def notify(
    db: Session,
    *,
    document_id: int,
    recipient: str,
    message: str,
    subject: str = "ReLook notification",
    task_id: int | None = None,
) -> None:
    """Records an in-app notification and best-effort delivers it over any
    configured external channels. Never raises -- delivery failures are
    stored on the row, not propagated to the caller."""
    print(f"[notify] {recipient}: {message}")

    db.add(
        Notification(
            document_id=document_id,
            task_id=task_id,
            recipient=recipient,
            message=message,
            channel="in_app",
            delivered=True,
        )
    )

    if os.environ.get("SMTP_HOST"):
        error = None
        try:
            _send_email(recipient, subject, message)
        except Exception as e:  # noqa: BLE001 -- best-effort, never block the caller
            error = str(e)
        db.add(
            Notification(
                document_id=document_id,
                task_id=task_id,
                recipient=recipient,
                message=message,
                channel="email",
                delivered=error is None,
                error=error,
            )
        )

    if os.environ.get("SLACK_WEBHOOK_URL"):
        error = None
        try:
            _send_slack(recipient, message)
        except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
            error = str(e)
        db.add(
            Notification(
                document_id=document_id,
                task_id=task_id,
                recipient=recipient,
                message=message,
                channel="slack",
                delivered=error is None,
                error=error,
            )
        )
