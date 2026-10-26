"""Certificates: the owner's list and edits, and the public JSON view."""

from __future__ import annotations

from fastapi import APIRouter, Response

from lattice.api import schemas
from lattice.api.deps import CurrentLearner, Db, MutatingLearner, State
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import accounts, certificates, plans
from lattice.domain.certificates import ISSUER, certification_name
from lattice.infrastructure.db.models import Certificate
from lattice.settings import Settings

PUBLIC_HEADERS = {"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"}

router = APIRouter(prefix="/api", tags=["certificates"], responses=PROBLEM_RESPONSES)


def public_url(settings: Settings, certificate_id: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/c/{certificate_id}"


def image_url(settings: Settings, certificate_id: str) -> str:
    return f"{public_url(settings, certificate_id)}.png"


def _owned(row: Certificate, settings: Settings) -> schemas.Certificate:
    url = public_url(settings, row.id)
    return schemas.Certificate(
        id=row.id,
        branch_id=row.branch_id,
        branch_title=row.branch_title,
        recipient_name=row.recipient_name,
        exercise_count=row.exercise_count,
        includes_capstone=row.includes_capstone,
        issued_at=row.issued_at,
        is_public=row.is_public,
        published_at=row.published_at,
        public_url=url,
        image_url=image_url(settings, row.id),
        linkedin=schemas.LinkedInFields(
            name=certification_name(row.branch_title),
            organisation=ISSUER,
            issue_year=row.issued_at.year,
            issue_month=row.issued_at.month,
            credential_id=row.id,
            credential_url=url,
        ),
    )


@router.get("/certificates")
def list_certificates(learner: CurrentLearner, db: Db, state: State) -> schemas.CertificateList:
    """The learner's certificates, newest first. Completed branches missing one are issued now."""
    rows = certificates.list_certificates(db, state.catalogue, learner.user.id)
    return schemas.CertificateList(certificates=[_owned(r, state.settings) for r in rows])


@router.patch("/certificates/{certificate_id}")
def update_certificate(
    certificate_id: str,
    body: schemas.CertificateUpdate,
    learner: MutatingLearner,
    db: Db,
    state: State,
) -> schemas.Certificate:
    """Publish or unpublish a certificate, or change the name on it. 404 unless it is yours.

    Publishing needs a verified email (403 `email-unverified`) and a Pro or Team plan (403
    `plan-required`). Unpublishing and renaming are open to every plan."""
    if body.is_public:
        accounts.require_verified(learner.user)
        plans.require_publish_entitlement(learner.user)
    row = certificates.update_certificate(
        db,
        learner.user.id,
        certificate_id,
        is_public=body.is_public,
        recipient_name=body.recipient_name,
    )
    return _owned(row, state.settings)


@router.get("/public/certificates/{certificate_id}")
def get_public_certificate(
    certificate_id: str, response: Response, db: Db, state: State
) -> schemas.PublicCertificate:
    """A public certificate, with no sign-in. 404 if it is private or does not exist."""
    row = certificates.public_certificate(db, certificate_id)
    response.headers.update(PUBLIC_HEADERS)
    return schemas.PublicCertificate(
        id=row.id,
        recipient_name=row.recipient_name,
        branch_title=row.branch_title,
        exercise_count=row.exercise_count,
        includes_capstone=row.includes_capstone,
        issued_at=row.issued_at,
        url=public_url(state.settings, row.id),
        image_url=image_url(state.settings, row.id),
    )
