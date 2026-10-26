"""Runtime configuration, read from environment variables (see `.env.example`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LATTICE_", env_file=".env", extra="ignore")

    content_dir: Path = Path("content")
    database_url: str = "postgresql+psycopg://lattice:lattice@localhost:5432/lattice"
    sandbox_image_python: str = "lattice-sandbox-python:dev"
    # An OCI runtime for grading containers, such as "runsc" (gVisor) in production. None uses
    # Docker's default runtime, as in development and CI.
    sandbox_oci_runtime: str | None = None
    session_ttl_hours: int = Field(default=24 * 14, ge=1)
    secure_cookies: bool = False
    attempts_per_minute: int = Field(default=10, ge=1)
    log_level: str = "INFO"
    worker_poll_seconds: float = Field(default=0.5, gt=0)
    # Origin used for every absolute URL we hand out: credential links, OpenGraph tags, images.
    public_base_url: str = "http://localhost:8080"
    allowed_origins: str = "http://localhost:5173"  # comma-separated; the Vite dev server

    # Proxies whose forwarding headers are believed (comma-separated CIDRs, e.g. Caddy's network).
    # Empty: the connecting peer is the client, and forwarding headers are ignored.
    trusted_proxies: str = ""

    # Transactional email. "console" logs each message (development); "resend" sends through
    # Resend's HTTP API and needs `resend_api_key` and a verified `email_from` domain.
    email_provider: Literal["console", "resend"] = "console"
    resend_api_key: str | None = None
    email_from: str = "Forgeway <noreply@localhost>"
    # Test-only: exposes the console outbox at /api/test/outbox. Honoured only with the console
    # provider, so it can never be on where real email is sent.
    e2e: bool = False

    # Cloudflare Turnstile on register. Without a secret, verification is skipped (development,
    # tests, and production until a Turnstile site exists).
    turnstile_secret: str | None = None
    turnstile_site_key: str | None = None

    # Abuse limits. Per-IP limits key on the real client IP (see `trusted_proxies`).
    register_per_ip_per_hour: int = Field(default=10, ge=1)
    login_per_ip_per_hour: int = Field(default=60, ge=1)
    # Sign-ins per email address from any IP, so spreading guesses over many addresses does not
    # get round the per-IP limits.
    login_per_email_per_hour: int = Field(default=50, ge=1)
    password_reset_per_ip_per_hour: int = Field(default=10, ge=1)
    password_reset_per_email_per_hour: int = Field(default=3, ge=1)
    verification_emails_per_hour: int = Field(default=3, ge=1)  # resends, per account
    attempts_per_day: int = Field(default=200, ge=1)  # per account, rolling 24 hours
    # Sandbox seconds per account in any 24 hours, from graded attempts' recorded durations, so
    # one learner cannot hold the worker for hours with deliberate timeouts.
    grading_seconds_per_day: int = Field(default=1800, ge=60)
    account_exports_per_hour: int = Field(default=5, ge=1)  # data exports, per account
    account_deletions_per_hour: int = Field(default=5, ge=1)  # tries, per account and per IP
    max_queue_depth: int = Field(default=50, ge=1)  # queued attempts before new ones are refused
    # The free plan's allowance: this many exercises of every standard branch past the foundations,
    # in each branch's stable order (ADR 0011).
    free_exercises_per_branch: int = Field(default=3, ge=0)
    # The sandbox's memory ceiling, whatever an exercise declares.
    sandbox_max_memory_mb: int = Field(default=768, ge=64)
    # Multiplies every exercise's time limit, for a slower sandbox runtime such as gVisor.
    sandbox_timeout_factor: float = Field(default=1.0, ge=1.0, le=5.0)

    @model_validator(mode="after")
    def _resend_needs_a_key(self) -> Settings:
        if self.email_provider == "resend" and not self.resend_api_key:
            raise ValueError("LATTICE_EMAIL_PROVIDER=resend needs LATTICE_RESEND_API_KEY")
        return self

    @property
    def email_outbox_exposed(self) -> bool:
        return self.e2e and self.email_provider == "console"


@lru_cache
def get_settings() -> Settings:
    return Settings()
