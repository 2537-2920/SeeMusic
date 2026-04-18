"""Dual-mode history record storage: in-memory (default) or database-backed."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Mode toggle – flipped by conftest.py or application bootstrap
# ---------------------------------------------------------------------------
# 默认关闭数据库模式，由 application 或 conftest 手动开启
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
    session = _get_session()
    try:
        from backend.db.models import UserHistory, Project, AudioAnalysis, CommunityPost
        db_user_id = _parse_db_user_id(user_id)
        all_items = []
        
        # 1. 聚合 Project 表 (归类为“识谱/转谱”)
        projects = session.query(Project).filter_by(user_id=db_user_id).all()
        for p in projects:
            all_items.append({
                "history_id": str(p.id),
                "type": "transcription",
                "resource_id": p.analysis_id,
                "info": {
                    "title": p.title or "音频转谱项目",
                    "duration": f"{p.duration:.1f}s" if p.duration else "未知",
                    "label": "音轨识谱"
                },
                "created_at": p.create_time.isoformat() if p.create_time else None
            })

        # 2. 聚合 AudioAnalysis 表 (区分识谱和唱歌测评)
        analyses = session.query(AudioAnalysis).filter_by(user_id=db_user_id).all()
        for a in analyses:
            params = a.params or {}
            source = params.get("source", "")
            
            # 判断逻辑：如果有节奏报告或是专门的测评上传，归类为测评；否则归类为识谱
            is_evaluation = (
                source == "analyze_rhythm_upload" or 
                "rhythm_report" in (a.result or {}) or
                "ref_id" in params
            )
            
            h_type = "evaluation" if is_evaluation else "transcription"
            h_label = "唱歌测评" if is_evaluation else "识谱分析"
            
            # 提取详细信息
            info_data = {
                "title": a.file_name or h_label,
                "label": h_label
            }
            if a.result:
                # 如果是唱歌测评，把报告里的关键指标拉平
                if "rhythm_report" in a.result:
                    report = a.result["rhythm_report"]
                    info_data.update({
                        "score": report.get("score"),
                        "timing_accuracy": report.get("timing_accuracy"),
                        "feedback": report.get("feedback")
                    })
                else:
                    info_data.update(a.result)
            
            all_items.append({
                "history_id": str(a.id),
                "type": h_type,
                "resource_id": a.analysis_id,
                "info": info_data,
                "created_at": a.create_time.isoformat() if a.create_time else None
            })

        # 3. 聚合 CommunityPost 表 (社区贡献)
        posts = session.query(CommunityPost).filter_by(user_id=db_user_id).all()
        for s in posts:
            all_items.append({
                "history_id": str(s.id),
                "type": "community",
                "resource_id": s.score_id,
                "info": {
                    "title": s.title or "乐谱发布",
                    "likes": s.like_count, 
                    "downloads": s.download_count
                },
                "created_at": s.create_time.isoformat() if s.create_time else None
            })

        # 4. 聚合 UserHistory 表 (其他操作)
        rows = session.query(UserHistory).filter_by(user_id=db_user_id).all()
        for r in rows:
            all_items.append({
                "history_id": str(r.id),
                "type": r.type,
                "resource_id": r.resource_id,
                "metadata": r.metadata_ or {},
                "info": {
                    "title": r.title,
                    **(r.metadata_ or {})
                },
                "created_at": r.create_time.isoformat() if r.create_time else None
            })

        all_items.sort(key=lambda x: x["created_at"] or "", reverse=True)
        return {"items": all_items}
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
