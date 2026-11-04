"""Time-based deletion the privacy policy promises, run daily by `forgeway accounts
purge-unverified` (deploy/vps/purge.sh): expired sign-in sessions, waitlist entries after 12
months, and pseudonymised regulation-37 consent records after six years.

Deleting an account removes its waitlist entry at once (ON DELETE CASCADE) and pseudonymises its
consents (`account_data.delete_account`); this handles what is left as it ages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from lattice.infrastructure.db.engine import rowcount
from lattice.infrastructure.db.models import BillingConsent, ProWaitlistEntry
from lattice.infrastructure.db.models import Session as SessionRow

WAITLIST_RETENTION = timedelta(days=365)
# Six years: the limitation period for a contract claim in England and Wales.
CONSENT_RETENTION = timedelta(days=6 * 365 + 2)


@dataclass(frozen=True)
class RetentionSummary:
    sessions: int
    waitlist: int
    consents: int


def purge_expired(session: Session, now: datetime | None = None) -> RetentionSummary:
    """Delete expired sessions, waitlist entries over 12 months old and consent records over six
    years old. Idempotent."""
    now = now or datetime.now(UTC)
    sessions = rowcount(session.execute(delete(SessionRow).where(SessionRow.expires_at <= now)))
    waitlist = rowcount(
        session.execute(
            delete(ProWaitlistEntry).where(ProWaitlistEntry.joined_at < now - WAITLIST_RETENTION)
        )
    )
    consents = rowcount(
        session.execute(
            delete(BillingConsent).where(BillingConsent.created_at < now - CONSENT_RETENTION)
        )
    )
    return RetentionSummary(sessions, waitlist, consents)
