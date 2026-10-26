"""`EmailSender` implementations: a console log for development and Resend's HTTP API."""

from __future__ import annotations

import json
import logging
import urllib.request
from collections import deque
from threading import Lock

from lattice.domain.email import EmailMessage, EmailSender

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
OUTBOX_SIZE = 200


class ConsoleEmailSender:
    """Logs each message instead of sending it, and keeps the latest in memory.

    The in-memory outbox lets end-to-end tests follow links from email; it is only ever exposed
    over HTTP when `Settings.email_outbox_exposed` is true.
    """

    def __init__(self) -> None:
        self._outbox: deque[EmailMessage] = deque(maxlen=OUTBOX_SIZE)
        self._lock = Lock()

    def send(self, message: EmailMessage) -> None:
        with self._lock:
            self._outbox.append(message)
        logger.info("email (console)", extra={"to": message.to, "subject": message.subject})
        logger.info("%s", message.text)

    def latest(self, to: str) -> EmailMessage | None:
        """The newest message sent to `to`, if any."""
        with self._lock:
            return next((m for m in reversed(self._outbox) if m.to == to), None)


class ResendEmailSender:
    """Sends through Resend (https://resend.com/docs/api-reference/emails/send-email)."""

    def __init__(self, api_key: str, sender: str, timeout_s: float = 10.0) -> None:
        self._api_key = api_key
        self._sender = sender
        self._timeout_s = timeout_s

    def send(self, message: EmailMessage) -> None:
        body = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        }
        request = urllib.request.Request(
            RESEND_URL,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "forgeway",
            },
        )
        with urllib.request.urlopen(request, timeout=self._timeout_s) as response:  # noqa: S310
            if response.status >= 300:
                raise RuntimeError(f"Resend answered {response.status}")


def build_sender(provider: str, api_key: str | None, sender: str) -> EmailSender:
    if provider == "resend":
        if not api_key:
            raise ValueError("the resend provider needs an API key")
        return ResendEmailSender(api_key, sender)
    return ConsoleEmailSender()
