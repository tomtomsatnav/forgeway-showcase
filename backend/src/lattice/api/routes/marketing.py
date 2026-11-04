"""The unsubscribe link in marketing email (PECR reg 22). No sign-in: the token is the proof."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, status

from lattice.api import schemas
from lattice.api.deps import ClientIp, Db, State
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import marketing

router = APIRouter(prefix="/api/marketing", tags=["marketing"], responses=PROBLEM_RESPONSES)
UNSUBSCRIBES_PER_IP_PER_HOUR = 30  # a shared office's worth; tokens cannot be guessed at this rate


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(body: schemas.MarketingUnsubscribe, db: Db, state: State, ip: ClientIp) -> None:
    """Stop marketing email to the link's learner. The link keeps working, so a second click
    is harmless; 422 if it is unknown or expired, and 429 past an hourly limit per IP."""
    state.limiter.check(
        f"unsubscribe:ip:{ip}",
        limit=UNSUBSCRIBES_PER_IP_PER_HOUR,
        window=timedelta(hours=1),
        message="Too many tries. Try again later.",
    )
    marketing.unsubscribe(db, body.token)
