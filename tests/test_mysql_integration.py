from __future__ import annotations

import os

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from backend.config.settings import Settings
from backend.db.base import Base
from backend.db.models import (
    AudioAnalysis,
    CommunityComment,
    CommunityFavorite,
    CommunityLike,
    CommunityPost,
    PitchSequence,
    Project,
    Report,
    Sheet,
    User,
    UserHistory,
)
from backend.db.repositories import get_sheet_by_score_id
from backend.db.session import get_engine, get_session_factory, reset_database_state, resolve_database_url, session_scope
from backend.services import analysis_service, community_service, report_service
from backend.services.analysis_service import clear_analysis_results, get_saved_pitch_sequence, save_analysis_result
from backend.services.score_service import create_score_from_pitch_sequence
from backend.user import history_manager, user_system


MYSQL_INTEGRATION_DATABASE_URL_ENV = "MYSQL_INTEGRATION_DATABASE_URL"
RUN_MYSQL_INTEGRATION_ENV = "RUN_MYSQL_INTEGRATION"

pytestmark = pytest.mark.mysql_integration


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_mysql_test_database_url() -> str | None:
    explicit_url = os.getenv(MYSQL_INTEGRATION_DATABASE_URL_ENV)
    if explicit_url and explicit_url.startswith("mysql"):
        return explicit_url

    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("mysql"):
        return database_url

    if _parse_bool(os.getenv(RUN_MYSQL_INTEGRATION_ENV)):
        resolved = Settings().database_url
        if resolved.startswith("mysql"):
            return resolved

    return None


def _recreate_schema() -> None:
    from backend.db import models as _models  # noqa: F401

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def mysql_database(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    database_url = _resolve_mysql_test_database_url()
    if not database_url:
        pytest.skip(
            "MySQL integration test skipped. Set MYSQL_INTEGRATION_DATABASE_URL or "
            "DATABASE_URL to a mysql+pymysql URL, or set RUN_MYSQL_INTEGRATION=1 "
            "with the existing SSH/MySQL env configuration."
        )

    monkeypatch.setenv("DATABASE_URL", database_url)
    reset_database_state()
    _recreate_schema()
    factory = get_session_factory()
    user_system.set_db_session_factory(factory)
    user_system.USE_DB = True
    history_manager.set_db_session_factory(factory)
    history_manager.USE_DB = True
    analysis_service.set_db_session_factory(factory)
    analysis_service.USE_DB = True
    report_service.set_db_session_factory(factory)
    report_service.USE_DB = True
    community_service.set_db_session_factory(factory)
    community_service.USE_DB = True

    try:
        yield {"database_url": resolve_database_url()}
    finally:
        try:
            user_system.USE_DB = False
            history_manager.USE_DB = False
            analysis_service.USE_DB = False
            report_service.USE_DB = False
            community_service.USE_DB = False
            clear_analysis_results()
            _recreate_schema()
        finally:
            reset_database_state()


def _create_user(
    *,
    username: str = "mysql_tester",
    password: str = "secret",
    email: str = "mysql_tester@example.com",
) -> int:
    with session_scope() as session:
        user = User(username=username, password=password, email=email)
        session.add(user)
        session.flush()
        return int(user.id)


class TestMySQLConnection:
    def test_mysql_connection_is_alive(self, mysql_database: dict[str, str]) -> None:
        with get_engine().connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1

        assert mysql_database["database_url"].startswith("mysql")

    def test_all_orm_tables_exist_in_mysql(self, mysql_database: dict[str, str]) -> None:
        inspector = inspect(get_engine())
        table_names = set(inspector.get_table_names())

        assert {
            "user",
            "project",
            "sheet",
            "export_record",
            "report",
            "community_post",
            "community_comment",
            "community_like",
            "community_favorite",
            "audio_analysis",
            "pitch_sequence",
            "user_history",
        }.issubset(table_names)

        report_columns = {column["name"] for column in inspector.get_columns("report")}
        community_post_columns = {column["name"] for column in inspector.get_columns("community_post")}
        audio_analysis_columns = {column["name"] for column in inspector.get_columns("audio_analysis")}

        assert {"report_id", "analysis_id", "metadata"}.issubset(report_columns)
        assert {
            "community_score_id",
            "score_id",
            "author_name",
            "subtitle",
            "style",
            "instrument",
            "price",
            "cover_url",
            "source_file_name",
            "file_content_base64",
            "file_content_type",
            "favorite_count",
            "download_count",
        }.issubset(community_post_columns)
        assert {"result"}.issubset(audio_analysis_columns)


class TestMySQLScoreService:
    def test_create_score_from_pitch_sequence_persists_project_and_sheet(
        self,
        mysql_database: dict[str, str],
    ) -> None:
        user_id = _create_user()

        result = create_score_from_pitch_sequence(
            {
                "user_id": user_id,
                "title": "MySQL Integration Score",
                "analysis_id": "an_mysql_score_001",
                "tempo": 88,
                "time_signature": "3/4",
                "key_signature": "D",
                "pitch_sequence": [
                    {"time": 0.0, "frequency": 440.0, "duration": 0.25},
                    {"time": 0.25, "frequency": 493.88, "duration": 0.25},
                    {"time": 0.5, "frequency": 523.25, "duration": 0.25},
                ],
            }
        )

        with session_scope() as session:
            project = session.scalar(select(Project).where(Project.id == result["project_id"]))
            sheet = get_sheet_by_score_id(session, result["score_id"])

            assert project is not None
            assert sheet is not None
            assert int(project.user_id) == user_id
            assert project.title == "MySQL Integration Score"
            assert project.analysis_id == "an_mysql_score_001"
            assert int(sheet.project_id) == int(project.id)
            assert sheet.score_id == result["score_id"]
            assert sheet.bpm == 88
            assert sheet.key_sign == "D"
            assert sheet.time_sign == "3/4"
            assert isinstance(sheet.note_data, dict)
            assert sheet.note_data["title"] == "MySQL Integration Score"


class TestMySQLDomainPersistence:
    def test_mysql_pitch_persistence_uses_note_events_and_lazy_cache(
        self,
        mysql_database: dict[str, str],
    ) -> None:
        frames = [
            {"time": 0.0, "frequency": 440.0, "duration": 0.01, "note": "A4", "voiced": True},
            {"time": 0.01, "frequency": 441.0, "duration": 0.01, "note": "A4", "voiced": True},
            {"time": 0.05, "frequency": 493.88, "duration": 0.01, "note": "B4", "voiced": True},
        ]

        save_analysis_result(
            analysis_id="an_mysql_pitch_events",
            file_name="demo.wav",
            sample_rate=16000,
            duration=0.5,
            status=1,
            params={"frame_ms": 20, "hop_ms": 10, "algorithm": "yin"},
            result_data={"log_id": "log_mysql_pitch"},
            pitch_sequence=frames,
        )
        clear_analysis_results()

        with session_scope() as session:
            analysis = session.scalar(select(AudioAnalysis).where(AudioAnalysis.analysis_id == "an_mysql_pitch_events"))
            cache_count = session.scalar(
                select(func.count()).select_from(PitchSequence).where(PitchSequence.analysis_id == "an_mysql_pitch_events")
            )

            assert analysis is not None
            assert analysis.result["pitch_sequence_format"] == "note_events"
            assert analysis.result["pitch_sequence"] == [
                {"start": 0.0, "end": 0.02, "note": "A4", "frequency_avg": 440.5},
                {"start": 0.05, "end": 0.06, "note": "B4", "frequency_avg": 493.88},
            ]
            assert analysis.result["pitch_meta"]["original_point_count"] == len(frames)
            assert cache_count == 0

        rebuilt = get_saved_pitch_sequence("an_mysql_pitch_events", populate_cache=False)
        assert rebuilt
        assert rebuilt[0]["note"] == "A4"

        with session_scope() as session:
            cache_count = session.scalar(
                select(func.count()).select_from(PitchSequence).where(PitchSequence.analysis_id == "an_mysql_pitch_events")
            )
            assert cache_count == 0

        cached = get_saved_pitch_sequence("an_mysql_pitch_events", populate_cache=True)

        with session_scope() as session:
            cache_count = session.scalar(
                select(func.count()).select_from(PitchSequence).where(PitchSequence.analysis_id == "an_mysql_pitch_events")
            )

        assert cached
        assert cache_count == len(cached)

    def test_report_audio_analysis_and_community_tables_round_trip(
        self,
        mysql_database: dict[str, str],
    ) -> None:
        user_id = _create_user(username="mysql_domain_user", email="mysql_domain_user@example.com")

        with session_scope() as session:
            project = Project(user_id=user_id, title="MySQL Domain Project", status=1, analysis_id="an_mysql_001")
            session.add(project)
            session.flush()

            sheet = Sheet(
                project_id=int(project.id),
                score_id="score_mysql_001",
                note_data={"score_id": "score_mysql_001", "tempo": 120, "key_signature": "C", "time_signature": "4/4"},
                bpm=120,
                key_sign="C",
                time_sign="4/4",
            )
            session.add(sheet)
            session.flush()

            analysis = AudioAnalysis(
                user_id=user_id,
                analysis_id="an_mysql_001",
                file_name="demo.wav",
                file_url="/storage/audio/demo.wav",
                sample_rate=16000,
                duration=1.5,
                bpm=120,
                status=1,
                params={"mode": "integration"},
                result={"segments": 3, "status": "ok"},
            )
            report = Report(
                project_id=int(project.id),
                report_id="r_mysql_001",
                analysis_id="an_mysql_001",
                pitch_score=95.5,
                rhythm_score=97.0,
                total_score=96.2,
                error_points=[{"time": 0.5, "type": "pitch"}],
                export_url="/storage/reports/r_mysql_001.pdf",
                metadata_={"source": "integration-test"},
            )
            post = CommunityPost(
                user_id=user_id,
                sheet_id=int(sheet.id),
                community_score_id="cmt_mysql_001",
                score_id="score_mysql_001",
                title="MySQL Community Score",
                author_name="MySQL Tester",
                subtitle="MySQL Tester · Piano",
                content="Integration round-trip for MySQL.",
                style="流行",
                instrument="钢琴",
                price=0.0,
                cover_url="/storage/covers/mysql.png",
                source_file_name="mysql-score.pdf",
                tags=["流行", "钢琴"],
                like_count=3,
                favorite_count=2,
                download_count=5,
                view_count=8,
            )
            session.add_all([analysis, report, post])
            session.flush()

            comment = CommunityComment(
                comment_id="comment_mysql_001",
                post_id=int(post.id),
                user_id=user_id,
                username="MySQL Tester",
                avatar_url="/storage/avatars/mysql.png",
                content="Nice score!",
            )
            like = CommunityLike(post_id=int(post.id), actor_key=f"user:{user_id}", user_id=user_id)
            favorite = CommunityFavorite(post_id=int(post.id), actor_key=f"user:{user_id}", user_id=user_id)
            history = UserHistory(
                user_id=user_id,
                type="report",
                resource_id="r_mysql_001",
                title="MySQL integration history",
                metadata_={"analysis_id": "an_mysql_001"},
            )
            session.add_all([comment, like, favorite, history])

        with session_scope() as session:
            stored_report = session.scalar(select(Report).where(Report.report_id == "r_mysql_001"))
            stored_analysis = session.scalar(select(AudioAnalysis).where(AudioAnalysis.analysis_id == "an_mysql_001"))
            stored_post = session.scalar(select(CommunityPost).where(CommunityPost.community_score_id == "cmt_mysql_001"))
            stored_comment = session.scalar(select(CommunityComment).where(CommunityComment.comment_id == "comment_mysql_001"))
            stored_history = session.scalar(select(UserHistory).where(UserHistory.resource_id == "r_mysql_001"))

            assert stored_report is not None
            assert stored_report.metadata_ == {"source": "integration-test"}
            assert stored_report.analysis_id == "an_mysql_001"

            assert stored_analysis is not None
            assert stored_analysis.result == {"segments": 3, "status": "ok"}
            assert stored_analysis.params == {"mode": "integration"}

            assert stored_post is not None
            assert stored_post.tags == ["流行", "钢琴"]
            assert stored_post.favorite_count == 2
            assert stored_post.download_count == 5
            assert stored_post.source_file_name == "mysql-score.pdf"

            assert stored_comment is not None
            assert stored_comment.username == "MySQL Tester"

            assert stored_history is not None
            assert stored_history.metadata_ == {"analysis_id": "an_mysql_001"}

            like_count = session.scalar(
                select(func.count()).select_from(CommunityLike).where(CommunityLike.post_id == int(stored_post.id))
            )
            favorite_count = session.scalar(
                select(func.count()).select_from(CommunityFavorite).where(CommunityFavorite.post_id == int(stored_post.id))
            )
            assert like_count == 1
            assert favorite_count == 1

    def test_mysql_enforces_unique_business_ids(self, mysql_database: dict[str, str]) -> None:
        user_id = _create_user(username="mysql_unique_user", email="mysql_unique_user@example.com")

        with session_scope() as session:
            project = Project(user_id=user_id, title="Unique Constraint Project", status=1)
            session.add(project)
            session.flush()

            first_report = Report(
                project_id=int(project.id),
                report_id="r_mysql_unique",
                analysis_id="an_mysql_unique_1",
                metadata_={},
            )
            second_report = Report(
                project_id=int(project.id),
                report_id="r_mysql_unique",
                analysis_id="an_mysql_unique_2",
                metadata_={},
            )
            session.add(first_report)
            session.flush()
            session.add(second_report)

            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
