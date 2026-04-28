"""Database engine and session helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
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

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_community_post_columns(engine)
    _ensure_community_interaction_columns(engine)


def _ensure_community_post_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("community_post")}
    except Exception:
        return

    statements: list[str] = []
    dialect = engine.dialect.name
    
    # 你的新增：封面字段
    if "cover_image" not in columns:
        if dialect == "sqlite":
            statements.append("ALTER TABLE community_post ADD COLUMN cover_image BLOB")
        else:
            statements.append("ALTER TABLE community_post ADD COLUMN cover_image LONGBLOB NULL")
    if "cover_content_type" not in columns:
        if dialect == "sqlite":
            statements.append("ALTER TABLE community_post ADD COLUMN cover_content_type VARCHAR(64)")
        else:
            statements.append("ALTER TABLE community_post ADD COLUMN cover_content_type VARCHAR(64) NULL")
            
    # 服务器新增：乐谱内容字段
    if "file_content_base64" not in columns:
        if dialect == "sqlite":
            statements.append("ALTER TABLE community_post ADD COLUMN file_content_base64 TEXT")
        else:
            statements.append("ALTER TABLE community_post ADD COLUMN file_content_base64 LONGTEXT NULL")
    if "file_content_type" not in columns:
        if dialect == "sqlite":
            statements.append("ALTER TABLE community_post ADD COLUMN file_content_type VARCHAR(64) DEFAULT 'application/pdf'")
        else:
            statements.append("ALTER TABLE community_post ADD COLUMN file_content_type VARCHAR(64) NOT NULL DEFAULT 'application/pdf'")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_community_interaction_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    dialect = engine.dialect.name

    def table_columns(table_name: str) -> set[str] | None:
        try:
            return {column["name"] for column in inspector.get_columns(table_name)}
        except Exception:
            return None

    statements: list[str] = []
    post_columns = table_columns("community_post")
    if post_columns is not None:
        if "like_count" not in post_columns:
            statements.append("ALTER TABLE community_post ADD COLUMN like_count INTEGER NOT NULL DEFAULT 0")
        if "favorite_count" not in post_columns:
            statements.append("ALTER TABLE community_post ADD COLUMN favorite_count INTEGER NOT NULL DEFAULT 0")
        if "download_count" not in post_columns:
            statements.append("ALTER TABLE community_post ADD COLUMN download_count INTEGER NOT NULL DEFAULT 0")
        if "view_count" not in post_columns:
            statements.append("ALTER TABLE community_post ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0")

    for table_name in ("community_like", "community_favorite"):
        columns = table_columns(table_name)
        if columns is None:
            continue
        if "actor_key" not in columns:
            statements.append(f"ALTER TABLE {table_name} ADD COLUMN actor_key VARCHAR(128) NOT NULL DEFAULT 'guest'")
        if "user_id" not in columns:
            user_id_type = "BIGINT" if dialect != "sqlite" else "INTEGER"
            statements.append(f"ALTER TABLE {table_name} ADD COLUMN user_id {user_id_type} NULL")
        if "create_time" not in columns:
            if dialect == "sqlite":
                statements.append(f"ALTER TABLE {table_name} ADD COLUMN create_time DATETIME NULL")
            else:
                statements.append(f"ALTER TABLE {table_name} ADD COLUMN create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def reset_database_state() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
    _SESSION_FACTORIES.clear()
    close_mysql_tunnel()
