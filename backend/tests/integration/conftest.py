"""Integration fixtures: a real Postgres database migrated with Alembic."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.models import Base
from tests.content_factory import write_branch, write_exercise

ADMIN_URL = os.environ.get(
    "LATTICE_TEST_ADMIN_URL", "postgresql+psycopg://lattice:lattice@localhost:5432/lattice"
)
# Override to run several checkouts against one Postgres without clobbering each other.
TEST_DB = os.environ.get("LATTICE_TEST_DB", "lattice_test")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
            conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    except OperationalError:
        pytest.skip("Postgres is not reachable (run `docker compose up -d db`)")
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
    _migrate(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()
    admin.dispose()


def _migrate(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    from lattice.infrastructure.db import engine as engine_module

    os.environ["LATTICE_DATABASE_URL"] = url
    engine_module.get_engine.cache_clear()
    from lattice.settings import get_settings

    get_settings.cache_clear()
    command.upgrade(Config(str(Path(__file__).parents[2] / "alembic.ini")), "head")


@pytest.fixture
def factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one -> two (with hints). Retrieval (requires starter): chunking."""
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_exercise(tmp_path, "starter", "one", xp=50)
    write_exercise(
        tmp_path, "starter", "two", xp=100, prerequisites=["starter.one"], hints=["h1", "h2"]
    )
    write_exercise(tmp_path, "retrieval", "chunking", xp=100)
    return load_catalogue(tmp_path)
