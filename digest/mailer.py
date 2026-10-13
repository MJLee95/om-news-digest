"""Send the digest through Gmail SMTP using an app password."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send(subject: str, text: str, html: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
    recipient = os.environ.get("DIGEST_RECIPIENT") or sender

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(sender, password)
        s.send_message(msg)
