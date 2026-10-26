"""The demo seed against the shipped content, and the progression migration's backfill."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError

from lattice.application import certificates, progression
from lattice.application.content_sync import current_revision_ids, sync_content
from lattice.application.demo import DEMO_EMAIL, seed_demo_learner
from lattice.application.streak import streak_for
from lattice.infrastructure.content_loader import load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import TalentAllocation, User
from tests.integration.conftest import ADMIN_URL

REAL_CONTENT = Path(__file__).parents[3] / "content"


def test_the_demo_learner_has_a_path_talents_badges_and_a_live_streak(factory):
    catalogue = load_catalogue(REAL_CONTENT)
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
        assert seed_demo_learner(
            session, catalogue, current_revision_ids(session), 14, free_per_branch=3
        )
        assert not seed_demo_learner(
            session, catalogue, current_revision_ids(session), 14, free_per_branch=3
        )

    with factory() as session:
        user_id = session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
        assert user_id is not None
        profile = progression.profile_view(session, catalogue, user_id, free_per_branch=3)
        badges = [b for b in progression.badge_views(session, catalogue, user_id) if b.awarded_at]
        streak = streak_for(session, user_id)
        taken = len(session.scalars(select(TalentAllocation).filter_by(user_id=user_id)).all())
        owned = certificates.list_certificates(session, catalogue, user_id)
    assert [c.branch_id for c in owned] == ["starter"]
    assert owned[0].is_public and owned[0].published_at is not None
    assert profile.path == "retrieval"
    assert 1 <= taken <= 3
    assert {b.badge.id for b in badges} >= {"first-steps", "foundations-complete"}
    assert streak.current >= 7


def test_a_small_demo_stays_a_generalist_because_the_foundations_are_unfinished(factory):
    catalogue = load_catalogue(REAL_CONTENT)
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
        seed_demo_learner(session, catalogue, current_revision_ids(session), 3, free_per_branch=3)
    with factory() as session:
        user_id = session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
        assert user_id is not None
        assert (
            progression.profile_view(session, catalogue, user_id, free_per_branch=3).path
            == "generalist"
        )


def test_the_migration_backfills_local_days_from_utc_created_at():
    from alembic import command
    from alembic.config import Config

    from lattice.infrastructure.db import engine as engine_module
    from lattice.settings import get_settings

    scratch = "lattice_migration_test"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)"))
            conn.execute(text(f"CREATE DATABASE {scratch}"))
    except OperationalError:
        pytest.skip("Postgres is not reachable (run `docker compose up -d db`)")
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{scratch}"
    previous = os.environ.get("LATTICE_DATABASE_URL")
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))

    def migrate(revision: str) -> None:
        os.environ["LATTICE_DATABASE_URL"] = url
        engine_module.get_engine.cache_clear()
        get_settings.cache_clear()
        command.upgrade(config, revision)

    user = "00000000-0000-0000-0000-000000000001"
    try:
        migrate("ca84b47f949a")  # the baseline, before progression
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, display_name, password_hash, created_at) "
                    "VALUES (:user, 'a@b.c', 'A', 'x', now())"
                ),
                {"user": user},
            )
            conn.execute(
                text(
                    "INSERT INTO exercise_revisions "
                    "(exercise_id, version, content_hash, definition, is_current, created_at) "
                    "VALUES ('s.a', 1, 'h', '{}', true, now())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO attempts (id, user_id, exercise_id, revision_id, files, status, "
                    "tries, created_at) VALUES ('00000000-0000-0000-0000-0000000000a1', "
                    ":user, 's.a', 1, '{}', 'passed', 0, '2026-03-01 23:30:00+00')"
                ),
                {"user": user},
            )
        migrate("head")
        with engine.connect() as conn:
            row = conn.execute(text("SELECT local_day, files_hash FROM attempts")).one()
        assert str(row.local_day) == "2026-03-01"
        assert row.files_hash is None  # attempts that predate hashing are never repeats
        engine.dispose()
    finally:
        if previous is None:
            os.environ.pop("LATTICE_DATABASE_URL", None)
        else:
            os.environ["LATTICE_DATABASE_URL"] = previous
        engine_module.get_engine.cache_clear()
        get_settings.cache_clear()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)"))
        admin.dispose()
