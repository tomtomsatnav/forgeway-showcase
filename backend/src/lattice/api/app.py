"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from lattice.api import errors, observability
from lattice.api.client_ip import parse_networks
from lattice.api.deps import AppState
from lattice.api.routes import (
    account,
    auth,
    certificates,
    health,
    learning,
    ops,
    pro,
    progression,
    public_config,
    public_pages,
    releases,
    testing,
)
from lattice.application.content_sync import current_revision_ids
from lattice.domain.email import EmailSender
from lattice.infrastructure.content_loader import load_catalogue
from lattice.infrastructure.db.engine import get_engine, session_factory
from lattice.infrastructure.email import build_sender
from lattice.infrastructure.logging_setup import configure as configure_logging
from lattice.infrastructure.theme_flavour import load_flavour
from lattice.infrastructure.turnstile import TurnstileVerifier
from lattice.settings import Settings, get_settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    email: EmailSender | None = None,
    turnstile: TurnstileVerifier | None = None,
) -> FastAPI:
    """Build the app. `email` and `turnstile` replace the configured ones (tests pass fakes)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    trusted_proxies = parse_networks(settings.trusted_proxies)
    email = email or build_sender(
        settings.email_provider, settings.resend_api_key, settings.email_from
    )
    if turnstile is None and settings.turnstile_secret:
        turnstile = TurnstileVerifier(settings.turnstile_secret)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        sessions = session_factory(engine or get_engine(settings.database_url))
        catalogue = load_catalogue(settings.content_dir)
        with sessions() as session:
            revisions = current_revision_ids(session)
        missing = sorted(set(catalogue.sources) - set(revisions))
        if missing:
            raise RuntimeError(f"content not synced; run `forgeway content sync` ({missing[:3]}…)")
        flavour = load_flavour(
            settings.content_dir, "rpg", catalogue.graph, catalogue.progression.tree.path_ids
        )
        app.state.lattice = AppState(
            settings, sessions, catalogue, revisions, flavour, email, turnstile, trusted_proxies
        )
        yield

    app = FastAPI(
        title="Forgeway API",
        version="0.1.0",
        summary="Gamified, auto-graded learning for modern AI engineering.",
        lifespan=lifespan,
    )
    errors.install(app)
    app.middleware("http")(observability.request_id_middleware)

    allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

    @app.middleware("http")
    async def reject_cross_origin_writes(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Defence in depth alongside SameSite cookies and CSRF tokens."""
        origin = request.headers.get("origin")
        if (
            request.method not in _SAFE_METHODS
            and origin
            and not _same_origin(origin, request, allowed_origins)
        ):
            return errors.problem(403, "Forbidden", "Cross-origin request refused.", "forbidden")
        response: Response = await call_next(request)
        return response

    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    routers: tuple[APIRouter, ...] = (
        health.router,
        ops.router,
        auth.router,
        account.router,
        learning.router,
        progression.router,
        certificates.router,
        pro.router,
        releases.router,
        public_pages.router,
        public_config.router,
    )
    if settings.email_outbox_exposed:
        routers = (*routers, testing.router)
    for router in routers:
        app.include_router(router)
    return app


def _same_origin(origin: str, request: Request, allowed: list[str]) -> bool:
    if origin in allowed:
        return True
    host = request.headers.get("host", "")
    return urlsplit(origin).netloc == host
