"""Runtime configuration, read from environment variables (see `.env.example`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from lattice.domain.live import LiveConfig, LiveLimits, ModelRate, SpendPolicy


class LiveModelRate(BaseModel):
    """USD per million tokens for one model; `long_*` prices apply past `long_above` input."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_read: float = Field(ge=0)
    cache_write: float = Field(ge=0)
    long_above: int | None = None
    long_input: float | None = None
    long_output: float | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LATTICE_", env_file=".env", extra="ignore")

    # "production" on the live site (deploy/vps/docker-compose.prod.yml sets it). It refuses
    # settings that are only safe in development: the console email provider, insecure cookies.
    environment: Literal["development", "production"] = "development"
    content_dir: Path = Path("content")
    # Where the forgeway-kit wheel is, served at /kit/ (`uv build --wheel grader/kit -o dist/kit`).
    kit_dir: Path = Path("dist/kit")
    # The live mode guide, shown at /live-mode (from /kit/live-mode.md) and put in every download.
    live_mode_guide: Path = Path("docs/live-mode.md")
    # The toolkit reference, shown at /toolkit (from /kit/toolkit-reference.md).
    toolkit_reference: Path = Path("docs/toolkit-reference.md")
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

    # In-app live runs (ADR 0012): a learner's code against a real model, on the platform's key.
    # The key is read by the worker only and never enters a sandbox. Unset, the feature is off.
    live_anthropic_api_key: SecretStr | None = None
    # Whether to offer live runs. Unset, they are on wherever the key is set. The API never needs
    # the key, only this (true): give the key to the worker alone.
    live_runs_enabled: bool | None = None
    # Tests point this at a stub server on the host.
    live_anthropic_base_url: str = "https://api.anthropic.com"
    # Every proxied call runs on this model, whatever learner code asks for.
    live_model: str = "claude-haiku-5-5"
    # USD per million tokens, per model (JSON in the environment). Haiku 5.5's first-party prices
    # (owner's decision, docs/plans/ai-tutor.md): five times higher past 100K input tokens.
    live_rate_card: dict[str, LiveModelRate] = Field(
        default_factory=lambda: {
            "claude-haiku-5-5": LiveModelRate(
                input=0.10, output=0.50, cache_read=0.01, cache_write=0.125,
                long_above=100_000, long_input=0.50, long_output=2.50,
            )
        }
    )  # fmt: skip
    # A paid learner's monthly live-run spend may reach this share of what they pay, converted
    # from the billing prices (monthly, or annual / 12) at `gbp_to_usd`.
    live_spend_cap_fraction: float = Field(default=0.5, ge=0, le=1)
    gbp_to_usd: float = Field(default=1.27, gt=0)
    # The monthly cap of a paid plan with no billing price behind it: billing off, or granted by
    # hand.
    live_pro_monthly_cap_usd: float = Field(default=10.0, ge=0)
    # A trial's live-run allowance, for the whole trial, in place of the Pro cap.
    live_trial_usd: float = Field(default=1.0, ge=0)
    # No more than this share of the monthly cap in one UTC day (the burst limit).
    live_daily_cap_fraction: float = Field(default=0.1, gt=0, le=1)
    # The free plan's monthly live-run allowance in USD; 0, the default, means none.
    live_free_monthly_usd: float = Field(default=0.0, ge=0)
    # Per-run limits.
    live_max_calls_per_run: int = Field(default=20, ge=1)
    live_max_tokens_per_run: int = Field(default=60_000, ge=1)
    live_max_output_tokens_per_call: int = Field(default=1024, ge=1)
    live_run_timeout_s: int = Field(default=60, ge=5, le=120)
    live_runs_per_hour: int = Field(default=30, ge=1)  # per account
    # Seconds of the worker an account's live runs may hold in any 24 hours, from claim to finish.
    live_seconds_per_day: int = Field(default=600, ge=1)

    # Billing through Stripe (docs/plans/billing.md). Off until the keys and both price ids are
    # set; with billing off the site shows the Pro waitlist. Keys come only from the environment.
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_price_monthly: str | None = None  # price_…, £19 a month, tax-inclusive
    stripe_price_annual: str | None = None  # price_…, £190 a year, tax-inclusive
    billing_trial_days: int = Field(default=7, ge=0, le=30)
    # What the site shows, in pence, VAT included. Checked against the Stripe prices on first use.
    billing_monthly_price_minor: int = Field(default=1900, ge=0)
    billing_annual_price_minor: int = Field(default=19000, ge=0)
    billing_webhooks_per_minute: int = Field(default=300, ge=1)  # per client IP
    billing_checkouts_per_hour: int = Field(default=20, ge=1)  # per account
    # Portal, pause, resume and withdraw together, per account.
    billing_actions_per_hour: int = Field(default=20, ge=1)
    # The trader's UK geographic address for documents (E-Commerce Regs reg 6; CA 2006 s.1201):
    # the virtual office, never a home address. Billing refuses to switch on while it is unset.
    trader_address: str | None = None

    @property
    def billing_enabled(self) -> bool:
        return all(
            (
                self.stripe_secret_key and self.stripe_secret_key.get_secret_value(),
                self.stripe_webhook_secret and self.stripe_webhook_secret.get_secret_value(),
                self.stripe_price_monthly,
                self.stripe_price_annual,
            )
        )

    @property
    def live_enabled(self) -> bool:
        if self.live_runs_enabled is not None:
            return self.live_runs_enabled
        return bool(self.live_anthropic_api_key and self.live_anthropic_api_key.get_secret_value())

    def _live_interval_caps(self) -> dict[str, float]:
        """Each billing interval's monthly live-run cap in USD; none while billing is off."""
        if not self.billing_enabled:
            return {}
        share = self.gbp_to_usd * self.live_spend_cap_fraction / 100  # the prices are in pence
        return {
            "monthly": self.billing_monthly_price_minor * share,
            "annual": self.billing_annual_price_minor / 12 * share,
        }

    def live_config(self) -> LiveConfig:
        return LiveConfig(
            enabled=self.live_enabled,
            model=self.live_model,
            rates={
                name: ModelRate(**rate.model_dump()) for name, rate in self.live_rate_card.items()
            },
            policy=SpendPolicy(
                pro_monthly_cap_usd=self.live_pro_monthly_cap_usd,
                daily_fraction=self.live_daily_cap_fraction,
                free_monthly_usd=self.live_free_monthly_usd,
                trial_usd=self.live_trial_usd,
                interval_caps_usd=self._live_interval_caps(),
            ),
            limits=LiveLimits(
                max_calls=self.live_max_calls_per_run,
                max_tokens=self.live_max_tokens_per_run,
                max_output_tokens_per_call=self.live_max_output_tokens_per_call,
                timeout_s=self.live_run_timeout_s,
            ),
            runs_per_hour=self.live_runs_per_hour,
            seconds_per_day=self.live_seconds_per_day,
        )

    @model_validator(mode="after")
    def _live_model_is_priced(self) -> Settings:
        if self.live_model not in self.live_rate_card:
            raise ValueError("LATTICE_LIVE_RATE_CARD must price LATTICE_LIVE_MODEL")
        return self

    @model_validator(mode="after")
    def _production_is_safe(self) -> Settings:
        if self.environment == "production":
            if self.email_provider == "console":
                raise ValueError(
                    "LATTICE_EMAIL_PROVIDER=console only logs email; production needs resend"
                )
            if not self.secure_cookies:
                raise ValueError("production needs LATTICE_SECURE_COOKIES=true")
        return self

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
