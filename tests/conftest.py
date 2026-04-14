from __future__ import annotations

from pathlib import Path

import pytest

from backend.config.settings import settings
from backend.core.score.score_utils import reset_score_cache
from backend.db.models import User
from backend.db.session import init_database, reset_database_state, session_scope
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
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    object.__setattr__(settings, "storage_dir", storage_dir)
    yield
    reset_score_cache()
    USERS.clear()
    TOKENS.clear()
    HISTORIES.clear()
    AUDIO_LOGS.clear()


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
