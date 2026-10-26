"""Public configuration the browser needs before anyone signs in."""

from __future__ import annotations

from fastapi import APIRouter

from lattice.api.deps import State
from lattice.api.schemas import PublicConfig

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def public_config(state: State) -> PublicConfig:
    """The Turnstile site key (null when the human check is off) and the free plan's allowance
    per track. Nothing here is secret."""
    return PublicConfig(
        turnstile_site_key=state.settings.turnstile_site_key or None,
        free_exercises_per_branch=state.settings.free_exercises_per_branch,
    )
