"""History record storage."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


HISTORIES: dict[str, list[dict]] = {}


def save_history(user_id: str, payload: dict) -> dict:
    entry = {
        "history_id": f"h_{uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    HISTORIES.setdefault(user_id, []).append(deepcopy(entry))
    return entry


def list_history(user_id: str) -> dict:
    return {"items": deepcopy(HISTORIES.get(user_id, []))}


def delete_history(user_id: str, history_id: str) -> dict:
    items = HISTORIES.get(user_id, [])
    HISTORIES[user_id] = [item for item in items if item.get("history_id") != history_id]
    return {"history_id": history_id, "deleted": True}

