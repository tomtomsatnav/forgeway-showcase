"""Request-scoped dependencies: database session, current learner, CSRF and the catalogue."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session, sessionmaker

from lattice.api import client_ip
from lattice.api.rate_limit import RateLimiter
from lattice.application import accounts
from lattice.application.errors import ForbiddenError, UnauthenticatedError
from lattice.domain.email import EmailSender
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.models import Session as SessionRow
from lattice.infrastructure.db.models import User
from lattice.infrastructure.theme_flavour import ThemeFlavour
from lattice.infrastructure.turnstile import TurnstileVerifier
from lattice.settings import Settings

SESSION_COOKIE = "lattice_session"


@dataclass
class AppState:
    """Process-wide state built once at startup."""

    settings: Settings
    sessions: sessionmaker[Session]
    catalogue: ContentCatalogue
    revision_ids: dict[str, int]
    rpg_flavour: ThemeFlavour
    email: EmailSender
    turnstile: TurnstileVerifier | None  # None: verification is off (no secret configured)
    trusted_proxies: tuple[client_ip.IpNetwork, ...] = ()
    limiter: RateLimiter = field(init=False)

    def __post_init__(self) -> None:
        self.limiter = RateLimiter(self.sessions)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.lattice
    return state


State = Annotated[AppState, Depends(get_state)]


def get_client_ip(request: Request, state: State) -> str:
    """The real client address, for per-IP limits (see `lattice.api.client_ip`)."""
    peer = request.client.host if request.client else None
    headers = {k.lower(): v for k, v in request.headers.items()}
    return client_ip.resolve(peer, headers, state.trusted_proxies)


ClientIp = Annotated[str, Depends(get_client_ip)]


def get_db(state: State) -> Iterator[Session]:
    """One transaction per request: committed on success, rolled back on error."""
    with state.sessions() as session, session.begin():
        yield session


Db = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class Learner:
    user: User
    session: SessionRow
    token: str


def current_learner(request: Request, db: Db) -> Learner:
    token = request.cookies.get(SESSION_COOKIE)
    resolved = accounts.resolve_session(db, token) if token else None
    if resolved is None:
        raise UnauthenticatedError("Sign in to continue.")
    user, row = resolved
    return Learner(user=user, session=row, token=token or "")


CurrentLearner = Annotated[Learner, Depends(current_learner)]


def csrf_protected(
    learner: CurrentLearner, x_csrf_token: Annotated[str | None, Header()] = None
) -> Learner:
    """Mutations by a signed-in learner must echo the session's CSRF token in a header."""
    if x_csrf_token is None or not secrets.compare_digest(x_csrf_token, learner.session.csrf_token):
        raise ForbiddenError("Missing or invalid CSRF token. Reload the page and try again.")
    return learner


MutatingLearner = Annotated[Learner, Depends(csrf_protected)]


def verified_learner(learner: MutatingLearner) -> Learner:
    """A mutating learner whose email address is verified."""
    accounts.require_verified(learner.user)
    return learner


VerifiedLearner = Annotated[Learner, Depends(verified_learner)]
