"""The learner's own data: a JSON export of everything held about them, and account deletion.

Both are rate-limited per account; deletion also per IP, as it checks a password.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response, status

from lattice.api import schemas
from lattice.api.deps import SESSION_COOKIE, ClientIp, CurrentLearner, Db, MutatingLearner, State
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import account_data

router = APIRouter(prefix="/api/account", tags=["account"], responses=PROBLEM_RESPONSES)
HOUR = timedelta(hours=1)


@router.get("/export")
def export_account(
    learner: CurrentLearner, response: Response, db: Db, state: State
) -> schemas.AccountExport:
    """Download everything held about the learner as JSON: the account and profile, sessions,
    attempts with their code, drafts, progress, the XP ledger, talents, badges, certificates,
    the waitlist entry and rate-limit records naming the account."""
    state.limiter.check(
        f"export:user:{learner.user.id}",
        limit=state.settings.account_exports_per_hour,
        window=HOUR,
        message="You have downloaded your data several times this hour. Try again later.",
    )
    now = datetime.now(UTC)
    response.headers["Content-Disposition"] = (
        f'attachment; filename="forgeway-data-{now.date().isoformat()}.json"'
    )
    response.headers["Cache-Control"] = "no-store"
    return schemas.AccountExport.model_validate(account_data.export_account(db, learner.user, now))


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: schemas.AccountDeletion,
    learner: MutatingLearner,
    response: Response,
    db: Db,
    state: State,
    ip: ClientIp,
) -> None:
    """Delete the account and everything held about it, once the current password is
    confirmed (422 if it is wrong). Every session ends and public certificate pages stop
    working. This cannot be undone."""
    message = "Too many tries. Try again later."
    limit = state.settings.account_deletions_per_hour
    state.limiter.check(f"delete:ip:{ip}", limit=limit, window=HOUR, message=message)
    state.limiter.check(f"delete:user:{learner.user.id}", limit=limit, window=HOUR, message=message)
    account_data.delete_account(db, learner.user, body.password)
    response.delete_cookie(SESSION_COOKIE, path="/")
