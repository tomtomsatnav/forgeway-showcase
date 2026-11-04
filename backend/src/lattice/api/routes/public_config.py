"""Public configuration the browser needs before anyone signs in."""

from __future__ import annotations

from fastapi import APIRouter

from lattice.api.deps import State
from lattice.api.routes.billing import billing_config
from lattice.api.schemas import PublicConfig
from lattice.application.local_live import kit_wheel_url

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def public_config(state: State) -> PublicConfig:
    """The Turnstile site key (null when the human check is off), the free plan's allowance per
        track, the forgeway-kit wheel's URL (null where none is built) and the Pro prices
    (`billing`, `enabled` false while billing is off) and the trader's address for the legal
    pages (null while unset). Nothing here is secret."""
    settings = state.settings
    return PublicConfig(
        turnstile_site_key=settings.turnstile_site_key or None,
        free_exercises_per_branch=settings.free_exercises_per_branch,
        kit_wheel_url=kit_wheel_url(settings.kit_dir, settings.public_base_url),
        live_runs=settings.live_enabled,
        live_model=settings.live_model if settings.live_enabled else None,
        billing=billing_config(settings, enabled=state.billing is not None),
        trader_address=(settings.trader_address or "").strip() or None,
    )
