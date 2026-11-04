"""The forgeway-kit wheel, the live mode guide and the toolkit reference. Public: no secrets."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse

from lattice.api.deps import State
from lattice.application.errors import NotFoundError
from lattice.application.local_live import kit_wheel

router = APIRouter(prefix="/kit", include_in_schema=False)


@router.get("/latest")
def latest_kit(state: State) -> RedirectResponse:
    """Redirect to the current wheel. `pip install` needs the versioned name itself."""
    wheel = kit_wheel(state.settings.kit_dir)
    if wheel is None:
        raise NotFoundError("The toolkit wheel is not built on this server.")
    return RedirectResponse(f"/kit/{wheel.name}", status_code=307)


@router.get("/live-mode.md")
def live_mode_guide(state: State) -> PlainTextResponse:
    """The live mode guide as Markdown, which the app's /live-mode page renders."""
    return _markdown(state.settings.live_mode_guide, "The live mode guide")


@router.get("/toolkit-reference.md")
def toolkit_reference(state: State) -> PlainTextResponse:
    """The toolkit reference as Markdown, which the app's /toolkit page renders."""
    return _markdown(state.settings.toolkit_reference, "The toolkit reference")


@router.get("/{filename}")
def kit_file(filename: str, state: State) -> FileResponse:
    """The wheel by its file name; anything else is 404, so no other file can be reached."""
    wheel = kit_wheel(state.settings.kit_dir)
    if wheel is None or filename != wheel.name:
        raise NotFoundError("No such file.")
    return FileResponse(wheel, media_type="application/octet-stream", filename=wheel.name)


def _markdown(path: Path, what: str) -> PlainTextResponse:
    if not path.is_file():
        raise NotFoundError(f"{what} is not on this server.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
