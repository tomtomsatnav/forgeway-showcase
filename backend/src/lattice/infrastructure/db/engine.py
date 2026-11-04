"""Engine and session factory."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, cast

from sqlalchemy import CursorResult, Engine, Result, create_engine
from sqlalchemy.orm import Session, sessionmaker

from lattice.settings import get_settings


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """A session whose work is committed on success and rolled back on any error."""
    with factory() as session, session.begin():
        yield session


def rowcount(result: Result[Any]) -> int:
    """Rows affected by an INSERT, UPDATE or DELETE."""
    return int(cast(CursorResult[Any], result).rowcount)
