"""Certificates: issuing on branch completion, the owner's list and edits, and public lookup."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lattice.application.errors import InvalidInputError, NotFoundError
from lattice.application.learning import passed_exercises
from lattice.domain.certificates import (
    InvalidRecipientNameError,
    clean_recipient_name,
    snapshot_name,
)
from lattice.domain.content import Tier
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.models import Certificate, User


def issue_certificates(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    branch_ids: Iterable[str],
    attempt_id: uuid.UUID | None,
) -> list[Certificate]:
    """Issue a certificate for each of `branch_ids` the learner has completed.

    Idempotent: (learner, branch) is unique, so a certificate is issued once however often this
    runs, and only those inserted by this call are returned. The recipient name, branch title,
    exercise count and whether the branch has a capstone are snapshotted here and never follow
    later changes.
    """
    graph = catalogue.graph
    passed = passed_exercises(session, user_id)
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("No such learner.")
    issued: list[Certificate] = []
    for branch_id in branch_ids:
        count = len(graph.branch_exercises(branch_id))
        if branch_id not in graph.branches or count == 0:
            continue
        if not graph.is_branch_complete(branch_id, passed):
            continue
        inserted = session.scalars(
            insert(Certificate)
            .values(
                user_id=user_id,
                branch_id=branch_id,
                recipient_name=snapshot_name(user.display_name),
                branch_title=graph.branches[branch_id].title,
                exercise_count=count,
                includes_capstone=any(
                    e.tier is Tier.CAPSTONE for e in graph.branch_exercises(branch_id)
                ),
                attempt_id=attempt_id,
                is_public=False,
            )
            .on_conflict_do_nothing(constraint="uq_certificate_once")
            .returning(Certificate)
        ).first()
        if inserted is not None:
            issued.append(inserted)
    return issued


def list_certificates(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> list[Certificate]:
    """The learner's certificates, newest first.

    Branches completed before certificates existed are issued here, on first listing, with no
    attempt recorded.
    """
    issue_certificates(session, catalogue, user_id, catalogue.graph.branches, None)
    return list(
        session.scalars(
            select(Certificate)
            .where(Certificate.user_id == user_id)
            .order_by(Certificate.issued_at.desc(), Certificate.id)
        )
    )


def update_certificate(
    session: Session,
    user_id: uuid.UUID,
    certificate_id: str,
    *,
    is_public: bool | None = None,
    recipient_name: str | None = None,
) -> Certificate:
    """Publish, unpublish or rename. Another learner's certificate is "not found", never
    "forbidden", so its existence is not revealed."""
    certificate = session.get(Certificate, certificate_id, with_for_update=True)
    if certificate is None or certificate.user_id != user_id:
        raise NotFoundError("No such certificate.")
    if recipient_name is not None:
        try:
            certificate.recipient_name = clean_recipient_name(recipient_name)
        except InvalidRecipientNameError as err:
            raise InvalidInputError(str(err)) from err
    if is_public is not None and is_public != certificate.is_public:
        certificate.is_public = is_public
        certificate.published_at = datetime.now(UTC) if is_public else None
    return certificate


def public_certificate(session: Session, certificate_id: str) -> Certificate:
    """A certificate its owner has made public. Private and unknown ids look the same."""
    certificate = session.get(Certificate, certificate_id)
    if certificate is None or not certificate.is_public:
        raise NotFoundError("No such certificate.")
    return certificate
