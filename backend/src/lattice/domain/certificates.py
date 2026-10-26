"""Certificate rules: public ids, the recipient's name and how a certificate is worded.

A certificate attests that a learner passed every exercise in a branch. It snapshots the facts it
attests, so later content changes never alter it.
"""

from __future__ import annotations

import secrets
import unicodedata
from datetime import date

RECIPIENT_NAME_MAX = 60
ISSUER = "Forgeway"
_ID_BYTES = 16  # 128 bits of randomness
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_FORBIDDEN_CATEGORIES = {"Cc", "Zl", "Zp"}  # control characters and line or paragraph breaks


class InvalidRecipientNameError(ValueError):
    """The name is empty, too long or contains control characters."""


def new_public_id() -> str:
    """A random, URL-safe id with 128 bits of entropy (22 characters). Never derived from data."""
    return secrets.token_urlsafe(_ID_BYTES)


def _has_forbidden(text: str) -> bool:
    return any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in text)


def clean_recipient_name(raw: str) -> str:
    """Trim the name and check it is 1 to 60 characters with no control characters."""
    name = raw.strip()
    if not name:
        raise InvalidRecipientNameError("The name cannot be empty.")
    if len(name) > RECIPIENT_NAME_MAX:
        raise InvalidRecipientNameError(f"The name can be at most {RECIPIENT_NAME_MAX} characters.")
    if _has_forbidden(name):
        raise InvalidRecipientNameError("The name cannot contain control characters.")
    return name


def snapshot_name(display_name: str) -> str:
    """The recipient name to snapshot from an account's display name, always valid."""
    kept = "".join(ch for ch in display_name if not _has_forbidden(ch))
    return kept.strip()[:RECIPIENT_NAME_MAX].strip() or "Forgeway learner"


def certification_name(branch_title: str) -> str:
    """The name of the certification, as LinkedIn shows it."""
    return f"{ISSUER} — {branch_title}"


def format_issue_date(day: date) -> str:
    """UK long form, independent of the process locale: 25 October 2026."""
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"
