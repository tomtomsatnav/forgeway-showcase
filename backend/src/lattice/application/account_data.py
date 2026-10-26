"""A learner's own data: exporting everything held about them, and deleting their account.

The export is the subject-access copy the privacy policy promises: every row that belongs to the
account, as plain JSON. Secrets that protect the account (the password hash, session and emailed
token hashes) are left out: they are about the account's security, not about the learner, and a
leaked export must not weaken it.

Deleting removes the user row. Every table that belongs to a learner references `users.id` with
`ON DELETE CASCADE`, so one statement removes their profile, sessions (signing them out
everywhere), emailed tokens, attempts with their code, drafts, progress, XP, talents, badges,
certificates (whose public pages then 404) and waitlist entry. Rate-limit records that name the
account's address or id go too; those keyed only on an IP address expire within a day.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from lattice.application.accounts import password_matches
from lattice.application.errors import InvalidInputError
from lattice.infrastructure.db.models import (
    AccountToken,
    Attempt,
    BadgeAward,
    Certificate,
    Draft,
    ExerciseProgress,
    LearnerProfile,
    ProWaitlistEntry,
    RateLimitHit,
    TalentAllocation,
    User,
    XpEvent,
)
from lattice.infrastructure.db.models import Session as SessionRow

EXPORT_FORMAT = "forgeway-account-export"
EXPORT_VERSION = 1
WRONG_PASSWORD = "That password is incorrect, so your account has not been deleted."  # noqa: S105 - a message, not a password


def export_account(session: Session, user: User, now: datetime | None = None) -> dict[str, Any]:
    """Everything held about `user`, as JSON-ready values (datetimes as ISO 8601 strings)."""
    uid = user.id
    profile = session.get(LearnerProfile, uid)
    waitlist = session.get(ProWaitlistEntry, uid)
    data: dict[str, Any] = {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": now or datetime.now(UTC),
        "account": {
            "id": uid,
            "email": user.email,
            "pending_email": user.pending_email,
            "display_name": user.display_name,
            "plan": user.plan,
            "created_at": user.created_at,
            "email_verified_at": user.email_verified_at,
        },
        "profile": None
        if profile is None
        else {
            "mode": profile.mode,
            "colour_scheme": profile.colour_scheme,
            "path_choice": profile.path_choice,
            "time_zone": profile.time_zone,
            "leaderboard_opt_in": profile.leaderboard_opt_in,
            "last_seen_release": profile.last_seen_release,
        },
        "sessions": [
            {"created_at": row.created_at, "expires_at": row.expires_at}
            for row in _rows(session, SessionRow, SessionRow.user_id == uid, SessionRow.created_at)
        ],
        "emailed_links": [
            {
                "purpose": row.purpose,
                "email": row.email,
                "created_at": row.created_at,
                "expires_at": row.expires_at,
            }
            for row in _rows(
                session, AccountToken, AccountToken.user_id == uid, AccountToken.created_at
            )
        ],
        "attempts": [
            {
                "id": row.id,
                "exercise_id": row.exercise_id,
                "files": row.files,
                "status": row.status,
                "report": row.report,
                "created_at": row.created_at,
                "finished_at": row.finished_at,
                "local_day": row.local_day,
            }
            for row in _rows(session, Attempt, Attempt.user_id == uid, Attempt.created_at)
        ],
        "drafts": [
            {"exercise_id": row.exercise_id, "files": row.files, "updated_at": row.updated_at}
            for row in _rows(session, Draft, Draft.user_id == uid, Draft.exercise_id)
        ],
        "exercise_progress": [
            {
                "exercise_id": row.exercise_id,
                "hints_revealed": row.hints_revealed,
                "first_passed_at": row.first_passed_at,
                "passing_attempt_id": row.passing_attempt_id,
            }
            for row in _rows(
                session,
                ExerciseProgress,
                ExerciseProgress.user_id == uid,
                ExerciseProgress.exercise_id,
            )
        ],
        "xp_events": [
            {
                "exercise_id": row.exercise_id,
                "reason": row.reason,
                "amount": row.amount,
                "attempt_id": row.attempt_id,
                "created_at": row.created_at,
            }
            for row in _rows(session, XpEvent, XpEvent.user_id == uid, XpEvent.id)
        ],
        "talents": [
            {"node_id": row.node_id, "allocated_at": row.allocated_at}
            for row in _rows(
                session, TalentAllocation, TalentAllocation.user_id == uid, TalentAllocation.id
            )
        ],
        "badges": [
            {"badge_id": row.badge_id, "attempt_id": row.attempt_id, "awarded_at": row.awarded_at}
            for row in _rows(session, BadgeAward, BadgeAward.user_id == uid, BadgeAward.id)
        ],
        "certificates": [
            {
                "id": row.id,
                "branch_id": row.branch_id,
                "branch_title": row.branch_title,
                "recipient_name": row.recipient_name,
                "exercise_count": row.exercise_count,
                "includes_capstone": row.includes_capstone,
                "issued_at": row.issued_at,
                "attempt_id": row.attempt_id,
                "is_public": row.is_public,
                "published_at": row.published_at,
            }
            for row in _rows(
                session, Certificate, Certificate.user_id == uid, Certificate.issued_at
            )
        ],
        "waitlist": None
        if waitlist is None
        else {
            "email": waitlist.email,
            "plan_interest": waitlist.plan_interest,
            "joined_at": waitlist.joined_at,
        },
        "rate_limit_records": [
            {"key": row.key, "at": row.at}
            for row in _rows(session, RateLimitHit, _names_account(user), RateLimitHit.at)
        ],
    }
    plain: dict[str, Any] = _plain(data)
    return plain


def delete_account(session: Session, user: User, password: str) -> None:
    """Delete `user` and every row that belongs to them, once `password` is confirmed."""
    if not password_matches(user, password):
        raise InvalidInputError(WRONG_PASSWORD)
    session.execute(delete(RateLimitHit).where(_names_account(user)))
    session.execute(delete(User).where(User.id == user.id))
    session.expunge(user)


def _names_account(user: User) -> Any:
    """Rate-limit keys that name the account. Keys end with what they count, after a colon
    (`login:ip-email:203.0.113.7:ada@example.com`, `export:user:<id>`), so this matches that
    last part exactly: `ada@example.com` does not match `bada@example.com`."""
    names = {str(user.id), user.email, *([user.pending_email] if user.pending_email else [])}
    return or_(*(func.right(RateLimitHit.key, len(name) + 1) == f":{name}" for name in names))


def _rows(session: Session, model: Any, where: Any, order: Any) -> list[Any]:
    return list(session.scalars(select(model).where(where).order_by(order)))


def _plain(value: Any) -> Any:
    """JSON-ready: datetimes and dates as ISO 8601, UUIDs as strings."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):  # date
        return value.isoformat()
    return value
