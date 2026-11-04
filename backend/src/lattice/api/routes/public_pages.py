"""Unauthenticated certificate pages: the verification page and its share image."""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse, HTMLResponse

from lattice.api import certificate_page
from lattice.api.deps import Db, State
from lattice.api.routes.certificates import PUBLIC_HEADERS, image_url, public_url
from lattice.application import certificates
from lattice.application.errors import NotFoundError
from lattice.domain.certificates import format_issue_date
from lattice.infrastructure.certificates.image import FONTS_DIR, CardContent, render_png

# Not in the OpenAPI contract: these are pages for people and link previews, not API calls.
router = APIRouter(include_in_schema=False)

_NOT_FOUND_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
# The page has no scripts and loads only its own fonts, so it forbids everything else.
_PAGE_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; font-src 'self'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
_FONT_HEADERS = {"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"}


@router.get("/c/fonts/{name}")
def certificate_font(name: str) -> Response:
    """The brand fonts for the verification page, the same files the share image is drawn in."""
    if name not in certificate_page.PAGE_FONTS:
        return Response(status_code=404, headers=_NOT_FOUND_HEADERS)
    return FileResponse(FONTS_DIR / name, media_type="font/ttf", headers=_FONT_HEADERS)


@router.get("/c/{certificate_id}.png")
def certificate_image(certificate_id: str, db: Db) -> Response:
    """The 1200x627 share image. 404 unless the certificate is public."""
    try:
        row = certificates.public_certificate(db, certificate_id)
    except NotFoundError:
        return Response(status_code=404, headers=_NOT_FOUND_HEADERS)
    png = render_png(
        CardContent(
            recipient_name=row.recipient_name,
            branch_title=row.branch_title,
            exercise_count=row.exercise_count,
            includes_capstone=row.includes_capstone,
            issued_on=format_issue_date(row.issued_at.date()),
            credential_id=row.id,
        )
    )
    return Response(png, media_type="image/png", headers=PUBLIC_HEADERS)


@router.get("/c/{certificate_id}", response_class=HTMLResponse)
def certificate_page_for(certificate_id: str, db: Db, state: State) -> HTMLResponse:
    """The verification page, with OpenGraph tags. A friendly 404 unless it is public."""
    site_url = state.settings.public_base_url.rstrip("/") + "/"
    try:
        row = certificates.public_certificate(db, certificate_id)
    except NotFoundError:
        return HTMLResponse(
            certificate_page.render_not_found_page(site_url),
            status_code=404,
            headers={**_NOT_FOUND_HEADERS, "Content-Security-Policy": _PAGE_POLICY},
        )
    page = certificate_page.render_certificate_page(
        certificate_page.PageContent(
            recipient_name=row.recipient_name,
            branch_title=row.branch_title,
            exercise_count=row.exercise_count,
            includes_capstone=row.includes_capstone,
            issued_on=format_issue_date(row.issued_at.date()),
            issued_iso=row.issued_at.date().isoformat(),
            credential_id=row.id,
            url=public_url(state.settings, row.id),
            image_url=image_url(state.settings, row.id),
            site_url=site_url,
        )
    )
    return HTMLResponse(page, headers={**PUBLIC_HEADERS, "Content-Security-Policy": _PAGE_POLICY})
