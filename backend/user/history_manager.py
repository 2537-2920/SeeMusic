"""Dual-mode history record storage: in-memory (default) or database-backed."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Mode toggle – flipped by conftest.py or application bootstrap
# ---------------------------------------------------------------------------
USE_DB: bool = False
_session_factory = None


def set_db_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


def _get_session():
    if _session_factory is None:
        raise RuntimeError("DB mode enabled but no session factory configured")
    return _session_factory()


def _parse_db_user_id(user_id: str) -> int:
    if not str(user_id).isdigit():
        raise HTTPException(status_code=400, detail="invalid user_id")
    return int(user_id)


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
HISTORIES: dict[str, list[dict]] = {}


# ===== save =====
def save_history(user_id: str, payload: dict) -> dict:
    if USE_DB:
        return _save_history_db(user_id, payload)
    return _save_history_mem(user_id, payload)


def _save_history_mem(user_id: str, payload: dict) -> dict:
    entry = {
        "history_id": f"h_{uuid4().hex[:8]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    HISTORIES.setdefault(user_id, []).append(deepcopy(entry))
    return entry


def _save_history_db(user_id: str, payload: dict) -> dict:
    from backend.db.models import UserHistory
    session = _get_session()
    try:
        db_user_id = _parse_db_user_id(user_id)
        record = UserHistory(
            user_id=db_user_id,
            type=payload.get("type", "unknown"),
            resource_id=payload.get("resource_id"),
            title=payload.get("title", ""),
            metadata_=deepcopy(payload.get("metadata") or {}),
        )
        session.add(record)
        session.commit()
        return {
            "history_id": str(record.id),
            "created_at": record.create_time.isoformat() if record.create_time else datetime.now(timezone.utc).isoformat(),
            **payload,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ===== list =====
def list_history(user_id: str) -> dict:
    if USE_DB:
        return _list_history_db(user_id)
    return _list_history_mem(user_id)


def _list_history_mem(user_id: str) -> dict:
    return {"items": deepcopy(HISTORIES.get(user_id, []))}


def _list_history_db(user_id: str) -> dict:
    from backend.db.models import UserHistory
    session = _get_session()
    try:
        db_user_id = _parse_db_user_id(user_id)
        rows = session.query(UserHistory).filter_by(user_id=db_user_id).all()
        items = [
            {
                "history_id": str(r.id),
                "type": r.type,
                "resource_id": r.resource_id,
                "title": r.title,
                "metadata": deepcopy(r.metadata_ or {}),
                "created_at": r.create_time.isoformat() if r.create_time else None,
            }
            for r in rows
        ]
        return {"items": items}
    finally:
        session.close()


# ===== delete =====
def delete_history(user_id: str, history_id: str) -> dict:
    if USE_DB:
        return _delete_history_db(user_id, history_id)
    return _delete_history_mem(user_id, history_id)


def _delete_history_mem(user_id: str, history_id: str) -> dict:
    items = HISTORIES.get(user_id, [])
    HISTORIES[user_id] = [item for item in items if item.get("history_id") != history_id]
    return {"history_id": history_id, "deleted": True}


def _delete_history_db(user_id: str, history_id: str) -> dict:
    from backend.db.models import UserHistory
    session = _get_session()
    try:
        db_user_id = _parse_db_user_id(user_id)
        if not str(history_id).isdigit():
            raise HTTPException(status_code=400, detail="invalid history_id")
        record = session.query(UserHistory).filter_by(id=int(history_id), user_id=db_user_id).first()
        if record:
            session.delete(record)
            session.commit()
        return {"history_id": history_id, "deleted": True}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
