"""ORM models for the project database tables used by the app."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


BIGINT_COMPAT = BigInteger().with_variant(Integer, "sqlite")


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class Sheet(Base):
    __tablename__ = "sheet"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("project.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    score_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    note_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    bpm: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    key_sign: Mapped[str] = mapped_column(String(10), default="C", nullable=False)
    time_sign: Mapped[str] = mapped_column(String(10), default="4/4", nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class ExportRecord(Base):
    __tablename__ = "export_record"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("project.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class Report(Base):
    __tablename__ = "report"
    __table_args__ = (UniqueConstraint("report_id", name="uq_report_report_id"),)

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("project.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    analysis_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    pitch_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhythm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_points: Mapped[list[dict[str, Any]] | dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    export_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class CommunityPost(Base):
    __tablename__ = "community_post"
    __table_args__ = (
        UniqueConstraint("community_score_id", name="uq_community_post_community_score_id"),
        UniqueConstraint("score_id", name="uq_community_post_score_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    sheet_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("sheet.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    community_score_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    score_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False, default="社区用户")
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class AudioAnalysis(Base):
    __tablename__ = "audio_analysis"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    analysis_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Backward-compatible alias for older service/tests that still use result_data.
    @property
    def result_data(self) -> dict[str, Any]:
        return self.result

    @result_data.setter
    def result_data(self, value: dict[str, Any]) -> None:
        self.result = value

    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class PitchSequence(Base):
    __tablename__ = "pitch_sequence"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("audio_analysis.analysis_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    time: Mapped[float] = mapped_column("time", Float, nullable=False)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    cents_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CommunityComment(Base):
    __tablename__ = "community_comment"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    comment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    post_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("community_post.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class CommunityLike(Base):
    __tablename__ = "community_like"
    __table_args__ = (UniqueConstraint("post_id", "actor_key", name="uq_community_like_post_actor"),)

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("community_post.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class CommunityFavorite(Base):
    __tablename__ = "community_favorite"
    __table_args__ = (UniqueConstraint("post_id", "actor_key", name="uq_community_favorite_post_actor"),)

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("community_post.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class UserHistory(Base):
    __tablename__ = "user_history"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class UserToken(Base):
    __tablename__ = "user_token"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    expired_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preference"

    id: Mapped[int] = mapped_column(BIGINT_COMPAT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT_COMPAT,
        ForeignKey("user.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
