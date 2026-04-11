import pytest

from backend.core.score.score_utils import SCORES
from backend.user.history_manager import HISTORIES
from backend.user.user_system import TOKENS, USERS
from backend.utils.audio_logger import AUDIO_LOGS


@pytest.fixture(autouse=True)
def reset_in_memory_state():
    SCORES.clear()
    HISTORIES.clear()
    TOKENS.clear()
    USERS.clear()
    AUDIO_LOGS.clear()
    yield
    SCORES.clear()
    HISTORIES.clear()
    TOKENS.clear()
    USERS.clear()
    AUDIO_LOGS.clear()
