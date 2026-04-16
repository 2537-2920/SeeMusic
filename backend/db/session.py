"""Database engine and session helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import Settings
from backend.db.base import Base
from backend.db.tunnel import close_mysql_tunnel, ensure_mysql_tunnel


_ENGINES: dict[str, Engine] = {}
_SESSION_FACTORIES: dict[str, sessionmaker[Session]] = {}


def resolve_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    return Settings().database_url


def _engine_options(database_url: str) -> dict[str, object]:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    elif database_url.startswith("mysql"):
        options["pool_recycle"] = 300
        options["pool_timeout"] = 10
        options["connect_args"] = {
            "connect_timeout": 5,
            "read_timeout": 15,
            "write_timeout": 15,
        }
    return options


def get_engine() -> Engine:
    database_url = resolve_database_url()
    if database_url not in _ENGINES:
        if not os.getenv("DATABASE_URL"):
            ensure_mysql_tunnel()
        _ENGINES[database_url] = create_engine(database_url, **_engine_options(database_url))
    return _ENGINES[database_url]


def get_session_factory() -> sessionmaker[Session]:
    database_url = resolve_database_url()
    if database_url not in _SESSION_FACTORIES:
        _SESSION_FACTORIES[database_url] = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
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
    # Import all ORM models before creating tables so Base.metadata is complete.
    from backend.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def reset_database_state() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
    _SESSION_FACTORIES.clear()
    close_mysql_tunnel()
