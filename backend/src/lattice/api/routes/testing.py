"""End-to-end test support. Mounted only when `Settings.email_outbox_exposed` is true: the
console email provider together with `LATTICE_E2E=1`, never where real email is sent."""

from __future__ import annotations

import re

from fastapi import APIRouter

from lattice.api.deps import Db, State
from lattice.api.schemas import OutboxToken, TestPlan
from lattice.application import accounts, plans
from lattice.application.errors import NotFoundError
from lattice.domain.entitlements import Plan
from lattice.infrastructure.email import ConsoleEmailSender

router = APIRouter(prefix="/api/test", tags=["testing"], include_in_schema=False)
_TOKEN = re.compile(r"[?&]token=([A-Za-z0-9_-]+)")


@router.get("/outbox/latest")
def latest_token(email: str, state: State) -> OutboxToken:
    """The link token in the newest email sent to `email`."""
    sender = state.email
    message = (
        sender.latest(accounts.normalise_email(email))
        if isinstance(sender, ConsoleEmailSender)
        else None
    )
    match = _TOKEN.search(message.text) if message else None
    if message is None or match is None:
        raise NotFoundError("No email with a link has been sent to that address.")
    return OutboxToken(subject=message.subject, token=match.group(1))


@router.post("/plan", status_code=204)
def set_plan(body: TestPlan, db: Db) -> None:
    """Put an account on a plan, so a spec can reach Pro content. There is no billing; in
    production the owner uses `forgeway accounts set-plan`."""
    plans.set_plan(db, body.email, Plan(body.plan))
