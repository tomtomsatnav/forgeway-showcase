"""Content releases for "What's new": the notes, newest first, and each learner's last seen."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from lattice.application.errors import NotFoundError
from lattice.domain.content.releases import ReleaseNote, has_unread
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.models import LearnerProfile


@dataclass(frozen=True)
class ReleasesView:
    releases: tuple[ReleaseNote, ...]  # newest first
    last_seen: str | None
    unread: bool


def _profile(session: Session, user_id: uuid.UUID) -> LearnerProfile:
    profile = session.get(LearnerProfile, user_id)
    if profile is None:
        raise NotFoundError("No such learner.")
    return profile


def releases_view(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> ReleasesView:
    last_seen = _profile(session, user_id).last_seen_release
    return ReleasesView(
        releases=catalogue.releases,
        last_seen=last_seen,
        unread=has_unread(catalogue.releases, last_seen),
    )


def mark_seen(session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID) -> ReleasesView:
    """Record the newest release as seen. Idempotent; a no-op when there are no releases."""
    if catalogue.releases:
        _profile(session, user_id).last_seen_release = catalogue.releases[0].version
    return releases_view(session, catalogue, user_id)
