"""The transactional email port: what is sent, not how."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str  # plain text; every message is readable without HTML
    html: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None:
        """Deliver `message` or raise. Callers decide whether a failure matters."""
        ...
