"""ORM models for the project database tables used by task B."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


BIGINT_COMPAT = BigInteger().with_variant(Integer, "sqlite")


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT_COMPAT, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Sheet(Base):
    __tablename__ = "sheet"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BIGINT_COMPAT, index=True, nullable=False)
    note_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    bpm: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    key_sign: Mapped[str] = mapped_column(String(10), default="C", nullable=False)
    time_sign: Mapped[str] = mapped_column(String(10), default="4/4", nullable=False)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    score_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)


class ExportRecord(Base):
    __tablename__ = "export_record"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BIGINT_COMPAT, index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
