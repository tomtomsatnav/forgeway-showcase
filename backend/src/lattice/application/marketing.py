"""Marketing email under PECR reg 22: who may receive it, its unsubscribe link, unsubscribing.

No marketing is sent yet; this is the plumbing every future offer or win-back email must use.
The owner chose the soft opt-in: offers go only to customers (anyone who has started a trial or
a subscription), and only if they have not refused, which they can do at sign-up, at checkout,
in their profile and through the link in every marketing email. Service emails (receipts,
reminders, password resets) never carry promotion and never use this module.

The waitlist's single "Pro is open" email is the other exception the owner allowed: send it with
`with_unsubscribe`, and only to entries whose learner has not opted out.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy.orm import Session

from lattice.application.errors import InvalidInputError
from lattice.domain.email import EmailMessage
from lattice.infrastructure.db.models import AccountToken, LearnerProfile, Subscription, User

# Long enough that an old email's link still works; an expired one says how else to opt out.
UNSUBSCRIBE_TTL = timedelta(days=365)
_OTHER_WAYS = (
    "Turn off offers in your profile (Settings), or email privacy@forgeway.dev and we will do it "
    "for you."
)


def may_send_offers(session: Session, user: User) -> bool:
    """Whether `user` may be sent an offer: a verified customer who has not opted out."""
    profile = session.get(LearnerProfile, user.id)
    subscription = session.get(Subscription, user.id)
    return (
        user.email_verified_at is not None
        and profile is not None
        and not profile.marketing_opt_out
        and subscription is not None
        and subscription.trial_used
    )


def unsubscribe_link(
    session: Session, user: User, base_url: str, now: datetime | None = None
) -> str:
    """A new unsubscribe link for `user`, valid for `UNSUBSCRIBE_TTL`. Earlier links keep
    working, so every email ever sent can still be used to unsubscribe."""
    token = secrets.token_urlsafe(32)
    now = now or datetime.now(UTC)
    session.add(
        AccountToken(
            token_hash=_hash(token),
            user_id=user.id,
            purpose="unsubscribe",
            email=user.email,
            created_at=now,
            expires_at=now + UNSUBSCRIBE_TTL,
        )
    )
    return f"{base_url.rstrip('/')}/unsubscribe?token={token}"


def with_unsubscribe(
    session: Session, message: EmailMessage, user: User, base_url: str
) -> EmailMessage:
    """`message` with the unsubscribe footer every marketing email must carry."""
    link = unsubscribe_link(session, user, base_url)
    note = "You are getting this because you are a Forgeway customer."
    return replace(
        message,
        text=f"{message.text}\n\n--\n{note} To stop these emails, open: {link}",
        html=(
            f'{message.html}<hr><p style="font-size:12px">{escape(note)} '
            f'<a href="{escape(link)}">Unsubscribe from offers</a></p>'
        ),
    )


def unsubscribe(session: Session, token: str, now: datetime | None = None) -> None:
    """Opt the link's learner out of marketing. Clicking again is harmless."""
    row = session.get(AccountToken, _hash(token))
    if row is None or row.purpose != "unsubscribe":
        raise InvalidInputError(f"This unsubscribe link is not valid. {_OTHER_WAYS}")
    if row.expires_at <= (now or datetime.now(UTC)):
        raise InvalidInputError(f"This unsubscribe link has expired. {_OTHER_WAYS}")
    profile = session.get(LearnerProfile, row.user_id)
    if profile is not None:
        profile.marketing_opt_out = True


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
