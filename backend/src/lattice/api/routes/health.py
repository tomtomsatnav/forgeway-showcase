"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from lattice.api.deps import State

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """The process is up."""
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
def readyz(state: State) -> dict[str, str] | JSONResponse:
    """The database is reachable and content is loaded."""
    try:
        with state.sessions() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return {"status": "ready", "exercises": str(len(state.catalogue.sources))}
