"""In-memory audio logging."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


AUDIO_LOGS: list[dict] = []


def record_audio_log(payload: dict) -> dict:
    entry = {
        "log_id": f"log_{uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    AUDIO_LOGS.append(deepcopy(entry))
    return entry

