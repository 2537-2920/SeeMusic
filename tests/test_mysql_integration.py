"""Integration tests that run against the real cloud MySQL database.

These tests are **skipped by default** in local development and only run
when explicitly selected with ``pytest -m mysql``.

Required environment variables (set in CI secrets):
    SSH_HOST, SSH_USER, SSH_KEY_FILE, MYSQL_HOST, MYSQL_PORT,
    MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB_NAME, DB_HOST, DB_PORT
"""

from __future__ import annotations

import uuid

import pytest

from backend.db.models import (
    AudioAnalysis,
    CommunityComment,
    CommunityFavorite,
    CommunityLike,
    CommunityPost,
    PitchSequence,
    Report,
    User,
    UserHistory,
    UserToken,
)
from backend.db.session import session_scope
from backend.services import analysis_service, community_service, report_service
from backend.user import history_manager, user_system

pytestmark = pytest.mark.mysql

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TAG = f"ci_{uuid.uuid4().hex[:8]}"  # unique per run to avoid collisions


def _unique(prefix: str) -> str:
    return f"{prefix}_{_TAG}"


# ---------------------------------------------------------------------------
# 1. Connection & schema
# ---------------------------------------------------------------------------


class TestMySQLConnection:
    """Verify the SSH tunnel + MySQL handshake works."""

    def test_mysql_connection_is_alive(self, mysql_database: dict) -> None:
        """Engine can execute a trivial query on the real server."""
        from backend.db.session import get_engine

        with get_engine().connect() as conn:
            result = conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            assert result.scalar() == 1

    def test_all_orm_tables_exist_in_mysql(self, mysql_database: dict) -> None:
        """Every table declared in models.py exists on the remote server."""
        from sqlalchemy import inspect as sa_inspect

        from backend.db.session import get_engine

        expected_tables = {
            "user", "user_token", "project", "sheet", "export_record",
            "report", "community_post", "community_comment",
            "community_like", "community_favorite",
            "audio_analysis", "pitch_sequence", "user_history",
        }
        actual_tables = set(sa_inspect(get_engine()).get_table_names())
        missing = expected_tables - actual_tables
        assert not missing, f"Missing tables on MySQL server: {missing}"


# ---------------------------------------------------------------------------
# 2. User system — register / login / token / logout
# ---------------------------------------------------------------------------


class TestMySQLUserSystem:
    """Full user lifecycle against real MySQL."""

    def test_register_login_token_logout(self, mysql_database: dict) -> None:
        username = _unique("user")
        password = "Test@12345"
        email = f"{username}@ci.test"

        # Register
        reg = user_system.register_user(username, password, email)
        assert reg["status"] == "success"
        user_id = reg["user_id"]
        assert isinstance(user_id, int) and user_id > 0

        # Login
        login = user_system.login_user(username, password)
        assert login["status"] == "success"
        token = login["token"]

        # Lookup by token
        lookup = user_system.get_user_by_token(token)
        assert lookup["username"] == username

        # Logout
        out = user_system.logout_user(token)
        assert out["status"] == "success"

        # Token no longer valid
        invalid = user_system.get_user_by_token(token)
        assert invalid.get("status") == "error"

        # ----- cleanup -----
        self._cleanup_user(user_id)

    def test_duplicate_username_rejected(self, mysql_database: dict) -> None:
        username = _unique("dup")
        user_system.register_user(username, "Pass1234")
        dup = user_system.register_user(username, "Other5678")
        assert dup["status"] == "error"

        # cleanup
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).first()
            if u:
                s.delete(u)

    # ---- cleanup helper ----
    @staticmethod
    def _cleanup_user(user_id: int) -> None:
        with session_scope() as s:
            s.query(UserToken).filter_by(user_id=user_id).delete()
            s.query(UserHistory).filter_by(user_id=user_id).delete()
            s.query(User).filter_by(id=user_id).delete()


# ---------------------------------------------------------------------------
# 3. History manager — save / list / delete
# ---------------------------------------------------------------------------


class TestMySQLHistoryManager:

    def test_save_list_delete_cycle(self, mysql_database: dict) -> None:
        # Create a test user first
        username = _unique("hist")
        reg = user_system.register_user(username, "Pass1234")
        uid = str(reg["user_id"])

        # Save
        payload = {"action": "analyse", "detail": "CI integration test"}
        saved = history_manager.save_history(uid, payload)
        assert saved["status"] == "success"

        # List
        listed = history_manager.list_history(uid)
        assert listed["status"] == "success"
        items = listed["history"]
        assert any(h["action"] == "analyse" for h in items)

        # Delete
        target = next(h for h in items if h["action"] == "analyse")
        deleted = history_manager.delete_history(uid, str(target["id"]))
        assert deleted["status"] == "success"

        # Verify gone
        listed2 = history_manager.list_history(uid)
        assert not any(h["id"] == target["id"] for h in listed2["history"])

        # cleanup
        with session_scope() as s:
            s.query(UserHistory).filter_by(user_id=int(uid)).delete()
            s.query(User).filter_by(id=int(uid)).delete()


# ---------------------------------------------------------------------------
# 4. Analysis service — persist audio analysis
# ---------------------------------------------------------------------------


class TestMySQLAnalysisService:

    def test_persist_audio_analysis(self, mysql_database: dict) -> None:
        analysis_id = _unique("ana")

        analysis_service.save_analysis_result(
            analysis_id=analysis_id,
            file_name="ci_test.wav",
            file_url="/uploads/ci_test.wav",
            sample_rate=44100,
            duration=3.5,
            bpm=120.0,
            status="completed",
            params={"source": "ci"},
            result_data={"notes": [{"pitch": 440, "onset": 0.0}]},
            pitch_sequence=[
                {"time": 0.0, "freq": 440.0, "note": "A4", "midi": 69},
            ],
            user_id=None,
            is_reference=False,
        )

        seq = analysis_service.get_saved_pitch_sequence(analysis_id)
        assert len(seq) >= 1
        assert seq[0]["freq"] == 440.0

        # cleanup
        with session_scope() as s:
            s.query(PitchSequence).filter_by(analysis_id=analysis_id).delete()
            s.query(AudioAnalysis).filter_by(analysis_id=analysis_id).delete()


# ---------------------------------------------------------------------------
# 5. Report service — persist report
# ---------------------------------------------------------------------------


class TestMySQLReportService:

    def test_persist_report(self, mysql_database: dict) -> None:
        report_id = _unique("rpt")

        result = report_service.export_report({
            "report_id": report_id,
            "title": "CI report",
            "format": "pdf",
            "content": {"summary": "CI integration test report"},
        })
        assert result["status"] == "success"

        # verify in DB
        with session_scope() as s:
            row = s.query(Report).filter_by(report_id=report_id).first()
            assert row is not None
            assert row.title == "CI report"

        # cleanup
        with session_scope() as s:
            s.query(Report).filter_by(report_id=report_id).delete()


# ---------------------------------------------------------------------------
# 6. Community service — publish / comment / like / favorite
# ---------------------------------------------------------------------------


class TestMySQLCommunityService:

    def test_community_full_lifecycle(self, mysql_database: dict) -> None:
        # Setup: register a user
        username = _unique("comm")
        reg = user_system.register_user(username, "Pass1234")
        uid = reg["user_id"]
        current_user = {"user_id": uid, "username": username}

        # Publish
        pub = community_service.publish_community_score(
            {"title": "CI Song", "description": "Integration test", "tags": "ci,test"},
            current_user=current_user,
        )
        assert pub["status"] == "success"
        score_id = str(pub["score"]["id"])

        # Comment
        cmt = community_service.add_community_comment(
            score_id,
            {"content": "Looks good from CI!"},
            current_user=current_user,
        )
        assert cmt["status"] == "success"

        # Like
        like = community_service.set_score_like(score_id, True, current_user=current_user)
        assert like["status"] == "success"

        # Favorite
        fav = community_service.set_score_favorite(score_id, True, current_user=current_user)
        assert fav["status"] == "success"

        # Detail includes comment, like, favorite
        detail = community_service.get_community_score_detail(score_id, current_user=current_user)
        assert detail["status"] == "success"
        assert detail["score"]["like_count"] >= 1

        # ---- cleanup ----
        with session_scope() as s:
            s.query(CommunityFavorite).filter_by(user_id=uid).delete()
            s.query(CommunityLike).filter_by(user_id=uid).delete()
            s.query(CommunityComment).filter_by(user_id=uid).delete()
            s.query(CommunityPost).filter_by(user_id=uid).delete()
            s.query(UserToken).filter_by(user_id=uid).delete()
            s.query(User).filter_by(id=uid).delete()
