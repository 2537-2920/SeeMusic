from __future__ import annotations

from pathlib import Path

import pytest

from backend.config.settings import Settings, settings
from backend.core.score.score_utils import reset_score_cache
from backend.db.models import User
from backend.db.session import init_database, reset_database_state, session_scope
from backend.services import analysis_service, community_service, report_service
from backend.user import history_manager, user_system
from backend.user.history_manager import HISTORIES
from backend.user.user_system import TOKENS, USERS
from backend.utils.audio_logger import AUDIO_LOGS


@pytest.fixture(autouse=True)
def reset_in_memory_state(tmp_path: Path) -> None:
    reset_score_cache()
    USERS.clear()
    TOKENS.clear()
    HISTORIES.clear()
    AUDIO_LOGS.clear()
    analysis_service.clear_analysis_results()
    report_service.clear_report_exports()
    community_service.COMMUNITY_SCORES.clear()
    community_service.COMMUNITY_COMMENTS.clear()
    community_service.COMMUNITY_LIKES.clear()
    community_service.COMMUNITY_FAVORITES.clear()
    # Ensure user/history modules are in memory mode by default
    user_system.USE_DB = False
    history_manager.USE_DB = False
    analysis_service.USE_DB = False
    report_service.USE_DB = False
    community_service.USE_DB = False
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    object.__setattr__(settings, "storage_dir", storage_dir)
    yield
    reset_score_cache()
    USERS.clear()
    TOKENS.clear()
    HISTORIES.clear()
    AUDIO_LOGS.clear()
    analysis_service.clear_analysis_results()
    report_service.clear_report_exports()
    community_service.COMMUNITY_SCORES.clear()
    community_service.COMMUNITY_COMMENTS.clear()
    community_service.COMMUNITY_LIKES.clear()
    community_service.COMMUNITY_FAVORITES.clear()
    user_system.USE_DB = False
    history_manager.USE_DB = False
    analysis_service.USE_DB = False
    report_service.USE_DB = False
    community_service.USE_DB = False


@pytest.fixture
def score_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, int | str]:
    database_path = tmp_path / "score-module.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")

    reset_database_state()
    reset_score_cache()
    init_database()

    with session_scope() as session:
        user = User(username="score_tester", password="secret")
        session.add(user)
        session.flush()
        user_id = int(user.id)

    yield {"database_url": str(database_path), "user_id": user_id}

    reset_score_cache()
    reset_database_state()


@pytest.fixture
def user_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, int | str]:
    """Set up a SQLite database and switch user_system / history_manager to DB mode."""
    from backend.db.session import get_session_factory

    database_path = tmp_path / "user-module.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")

    reset_database_state()
    init_database()

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

    yield {"database_url": str(database_path)}

    user_system.USE_DB = False
    history_manager.USE_DB = False
    analysis_service.USE_DB = False
    report_service.USE_DB = False
    community_service.USE_DB = False
    reset_database_state()


@pytest.fixture
def mysql_database() -> dict[str, str]:
    """Connect to the real MySQL database via SSH tunnel.

    Requires environment variables: SSH_HOST, SSH_USER, SSH_KEY_FILE,
    MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB_NAME, etc.
    Tests using this fixture must be marked with ``@pytest.mark.mysql``.
    """
    import os
    from backend.db.session import get_session_factory

    # Ensure no leftover DATABASE_URL override — let settings build the MySQL URL
    os.environ.pop("DATABASE_URL", None)

    reset_database_state()
    init_database()  # opens SSH tunnel as needed, creates missing tables

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

    yield {"database_url": Settings().database_url}

    user_system.USE_DB = False
    history_manager.USE_DB = False
    analysis_service.USE_DB = False
    report_service.USE_DB = False
    community_service.USE_DB = False
    reset_database_state()
