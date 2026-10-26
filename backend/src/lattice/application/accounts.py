"""Registration, login, server-side sessions, email verification and password reset."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from lattice.application.errors import (
    ConflictError,
    EmailUnverifiedError,
    InvalidInputError,
    UnauthenticatedError,
)
from lattice.application.streak import validate_time_zone
from lattice.domain.email import EmailMessage
from lattice.infrastructure.db.engine import rowcount
from lattice.infrastructure.db.models import AccountToken, LearnerProfile, User
from lattice.infrastructure.db.models import Session as SessionRow

MIN_PASSWORD_LENGTH = 10
_hasher = PasswordHasher()
# Verified against when the email is unknown, so response time does not reveal which
# addresses have accounts.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


TokenPurpose = Literal["verify-email", "reset-password"]
VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=15)
UNVERIFIED_GRACE = timedelta(days=7)  # unverified accounts older than this are purged
_INVALID_LINK = "This link is invalid or has expired. Request a new one."


@dataclass(frozen=True)
class IssuedSession:
    token: str  # goes in the httpOnly cookie; never stored
    csrf_token: str
    expires_at: datetime


def normalise_email(email: str) -> str:
    return email.strip().lower()


def register(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    time_zone: str = "UTC",
    mode: str = "professional",
    colour_scheme: str = "system",
) -> User:
    """Create an account and its learner profile, in the given IANA time zone and theme."""
    email = normalise_email(email)
    validate_time_zone(time_zone)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidInputError(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters.")
    if _email_taken(session, email):
        raise ConflictError("An account with that email already exists.")
    user = User(
        email=email, display_name=display_name.strip(), password_hash=_hasher.hash(password)
    )
    session.add(user)
    session.flush()
    session.add(
        LearnerProfile(user_id=user.id, time_zone=time_zone, mode=mode, colour_scheme=colour_scheme)
    )
    return user


def authenticate(session: Session, *, email: str, password: str) -> User:
    """Return the user for valid credentials; raise `UnauthenticatedError` otherwise."""
    user = session.scalar(select(User).where(User.email == normalise_email(email)))
    try:
        _hasher.verify(user.password_hash if user else _DUMMY_HASH, password)
    except VerificationError:
        user = None
    if user is None:
        raise UnauthenticatedError("Email or password is incorrect.")
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    return user


def password_matches(user: User, password: str) -> bool:
    """Whether `password` is the account's current password."""
    try:
        return _hasher.verify(user.password_hash, password)
    except VerificationError:
        return False


def issue_session(session: Session, user_id: uuid.UUID, *, ttl: timedelta) -> IssuedSession:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + ttl
    session.add(
        SessionRow(token_hash=_hash(token), user_id=user_id, csrf_token=csrf, expires_at=expires_at)
    )
    return IssuedSession(token, csrf, expires_at)


def resolve_session(session: Session, token: str) -> tuple[User, SessionRow] | None:
    """The user behind a session cookie, or None if it is unknown or expired."""
    row = session.get(SessionRow, _hash(token))
    if row is None or row.expires_at <= datetime.now(UTC):
        return None
    user = session.get(User, row.user_id)
    return (user, row) if user else None


def revoke_session(session: Session, token: str) -> None:
    session.execute(delete(SessionRow).where(SessionRow.token_hash == _hash(token)))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _email_taken(session: Session, email: str) -> bool:
    return session.scalar(select(User.id).where(User.email == email)) is not None


def revoke_all_sessions(session: Session, user_id: uuid.UUID) -> int:
    return rowcount(session.execute(delete(SessionRow).where(SessionRow.user_id == user_id)))


def require_verified(user: User) -> None:
    """Raise unless the learner has verified their email address."""
    if user.email_verified_at is None:
        raise EmailUnverifiedError(
            "Verify your email address first: follow the link we sent you, or ask for a new one."
        )


# Emailed tokens ------------------------------------------------------------------------------


def _issue_token(
    session: Session, user_id: uuid.UUID, purpose: TokenPurpose, email: str, ttl: timedelta
) -> str:
    """A new single-use token. Earlier tokens for the same purpose stop working."""
    session.execute(
        delete(AccountToken).where(AccountToken.user_id == user_id, AccountToken.purpose == purpose)
    )
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        AccountToken(
            token_hash=_hash(token),
            user_id=user_id,
            purpose=purpose,
            email=email,
            created_at=now,
            expires_at=now + ttl,
        )
    )
    return token


def _redeem_token(session: Session, token: str, purpose: TokenPurpose) -> AccountToken:
    """Consume a token (deleting it) or raise if it is unknown, of another purpose or expired."""
    row = session.get(AccountToken, _hash(token), with_for_update=True)
    if row is None or row.purpose != purpose:
        raise InvalidInputError(_INVALID_LINK)
    session.delete(row)
    session.flush()
    if row.expires_at <= datetime.now(UTC):
        raise InvalidInputError(_INVALID_LINK)
    return row


def verification_email(
    session: Session, user: User, base_url: str, *, to: str | None = None
) -> EmailMessage:
    """Issue a 24-hour verification token for `to` (the account's address by default) and
    return the email that carries it."""
    address = to or user.email
    token = _issue_token(session, user.id, "verify-email", address, VERIFY_TTL)
    link = f"{base_url.rstrip('/')}/verify-email?token={token}"
    return EmailMessage(
        to=address,
        subject="Confirm your email for Forgeway",
        text=(
            f"Hello {user.display_name},\n\nConfirm this address for your Forgeway account by "
            f"opening this link within 24 hours:\n\n{link}\n\nIf you did not ask for this, you "
            "can ignore this email."
        ),
        html=_html(
            user.display_name,
            "Confirm this address for your Forgeway account. The link works for 24 hours.",
            link,
            "Confirm email",
        ),
    )


def verify_email(session: Session, token: str) -> User:
    """Mark the address a verification token was sent to as verified.

    The token names its address: the account's current one, or a pending new one, which then
    replaces it. A token for any other address (an older pending change) is refused.
    """
    row = _redeem_token(session, token, "verify-email")
    user = session.get(User, row.user_id, with_for_update=True)
    if user is None:
        raise InvalidInputError(_INVALID_LINK)
    if row.email == user.pending_email:
        if _email_taken(session, row.email):
            user.pending_email = None
            raise ConflictError("Another account now uses that email address.")
        user.email, user.pending_email = row.email, None
    elif row.email != user.email:
        raise InvalidInputError(_INVALID_LINK)
    user.email_verified_at = datetime.now(UTC)
    return user


def request_email_change(
    session: Session, user: User, *, new_email: str, password: str, base_url: str
) -> EmailMessage:
    """Record `new_email` as pending and return the verification email for it.

    The current address keeps working until the new one is verified, so a typo cannot lock the
    learner out. The current password is required.
    """
    try:
        _hasher.verify(user.password_hash, password)
    except VerificationError as err:
        raise UnauthenticatedError("That password is incorrect.") from err
    new_email = normalise_email(new_email)
    if new_email == user.email:
        raise InvalidInputError("That is already your email address.")
    if _email_taken(session, new_email):
        raise ConflictError("An account with that email already exists.")
    user.pending_email = new_email
    return verification_email(session, user, base_url, to=new_email)


def password_reset_email(session: Session, email: str, base_url: str) -> EmailMessage | None:
    """Issue a 15-minute reset token and return its email, or None for an unknown address.

    Callers answer the same either way, so the response never reveals whether an account exists.
    """
    user = session.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        return None
    token = _issue_token(session, user.id, "reset-password", user.email, RESET_TTL)
    link = f"{base_url.rstrip('/')}/reset-password?token={token}"
    return EmailMessage(
        to=user.email,
        subject="Reset your Forgeway password",
        text=(
            f"Hello {user.display_name},\n\nSomeone asked to reset the password for your "
            f"Forgeway account. To choose a new one, open this link within 15 minutes:\n\n"
            f"{link}\n\nIf it was not you, ignore this email: your password stays as it is."
        ),
        html=_html(
            user.display_name,
            "Someone asked to reset your Forgeway password. The link works for 15 minutes. If it "
            "was not you, ignore this email: your password stays as it is.",
            link,
            "Choose a new password",
        ),
    )


def check_reset_token(session: Session, token: str) -> None:
    """Raise unless `token` is an unexpired password-reset token. Nothing is consumed."""
    row = session.get(AccountToken, _hash(token))
    if row is None or row.purpose != "reset-password" or row.expires_at <= datetime.now(UTC):
        raise InvalidInputError(_INVALID_LINK)


def reset_password(session: Session, token: str, new_password: str) -> User:
    """Set a new password from a reset token and end every session the account has.

    Following the link proves the learner reads that inbox, so the address counts as verified.
    """
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise InvalidInputError(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters.")
    row = _redeem_token(session, token, "reset-password")
    user = session.get(User, row.user_id, with_for_update=True)
    if user is None or row.email != user.email:
        raise InvalidInputError(_INVALID_LINK)
    user.password_hash = _hasher.hash(new_password)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
    revoke_all_sessions(session, user.id)
    return user


@dataclass(frozen=True)
class PurgeSummary:
    accounts: int
    tokens: int


def purge_unverified(session: Session, now: datetime | None = None) -> PurgeSummary:
    """Delete accounts never verified within the grace period, and expired tokens. Idempotent."""
    now = now or datetime.now(UTC)
    accounts = rowcount(
        session.execute(
            delete(User).where(
                User.email_verified_at.is_(None), User.created_at < now - UNVERIFIED_GRACE
            )
        )
    )
    tokens = rowcount(session.execute(delete(AccountToken).where(AccountToken.expires_at <= now)))
    return PurgeSummary(accounts, tokens)


def _html(name: str, message: str, link: str, action: str) -> str:
    return (
        f"<p>Hello {escape(name)},</p><p>{escape(message)}</p>"
        f'<p><a href="{escape(link)}">{escape(action)}</a></p>'
        f"<p>Or paste this link into your browser:<br>{escape(link)}</p>"
    )
