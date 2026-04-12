"""Database engine and session helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import settings
from backend.db.base import Base


_ENGINES: dict[str, Engine] = {}
_SESSION_FACTORIES: dict[str, sessionmaker[Session]] = {}


def resolve_database_url() -> str:
    return os.getenv("DATABASE_URL", settings.database_url)


def _engine_options(database_url: str) -> dict[str, object]:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return options


def get_engine() -> Engine:
    database_url = resolve_database_url()
    if database_url not in _ENGINES:
        _ENGINES[database_url] = create_engine(database_url, **_engine_options(database_url))
    return _ENGINES[database_url]


def get_session_factory() -> sessionmaker[Session]:
    database_url = resolve_database_url()
    if database_url not in _SESSION_FACTORIES:
        _SESSION_FACTORIES[database_url] = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SESSION_FACTORIES[database_url]


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    Base.metadata.create_all(bind=get_engine())


def reset_database_state() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
    _SESSION_FACTORIES.clear()

