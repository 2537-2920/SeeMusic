"""Score service helpers."""

from __future__ import annotations

import logging
import mimetypes
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.exc import SQLAlchemyError

from backend.config.settings import settings
from backend.core.score.score_utils import (
    create_score as create_canonical_score,
    get_score_state,
    redo_score as _redo_score,
    save_score,
    snapshot_score,
    undo_score as _undo_score,
    update_score_musicxml,
)
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.db.models import ExportRecord
from backend.db.repositories import (
    create_export_record,
    create_project,
    create_sheet,
    delete_export_record,
    get_export_record_by_id,
    get_sheet_by_score_id,
    get_user_by_id,
    has_other_export_records_with_file_url,
    list_export_records_by_project,
    score_from_sheet,
    update_export_record,
    update_sheet_from_score,
)
from backend.db.session import session_scope
from backend.export.export_utils import write_score_export


class ScoreServiceError(Exception):
    """Base class for score service errors."""


class ScoreNotFoundError(ScoreServiceError):
    """Raised when the requested score does not exist."""


class ScoreOperationError(ScoreServiceError):
    """Raised when a full-score MusicXML payload is invalid."""


class UserNotFoundError(ScoreServiceError):
    """Raised when the referenced user does not exist."""


class ExportRecordNotFoundError(ScoreServiceError):
    """Raised when the requested export record does not exist."""


class ExportFileNotFoundError(ScoreServiceError):
    """Raised when the export metadata exists but the file is missing."""


STORAGE_PREFIX = "/storage/"
SCORE_PROJECT_CACHE: Dict[str, int] = {}
SCORE_EXPORT_CACHE: Dict[str, Dict[str, Any]] = {}
IN_MEMORY_PROJECT_ID_BASE = 900_000_000
_in_memory_project_id_counter = 0
_DB_FALLBACK_RUNTIME_MARKERS = (
    "db mode enabled but no session factory configured",
    "database unavailable",
    "mysql tunnel",
    "ssh tunnel",
    "local mysql port",
    "ssh:",
    "socket:",
)

logger = logging.getLogger(__name__)



def _default_project_title(title: str | None, score_id: str) -> str:
    if title:
        return title
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return f"Generated Score {score_id} @ {timestamp}"


def _next_in_memory_project_id() -> int:
    global _in_memory_project_id_counter
    _in_memory_project_id_counter += 1
    return IN_MEMORY_PROJECT_ID_BASE + _in_memory_project_id_counter


def _cache_score_runtime_state(score: Dict[str, Any], project_id: int) -> None:
    score_id = str(score["score_id"])
    SCORE_PROJECT_CACHE[score_id] = int(project_id)
    SCORE_EXPORT_CACHE.setdefault(
        score_id,
        {
            "score_id": score_id,
            "project_id": int(project_id),
            "items": [],
        },
    )


def _load_sheet_from_cache(score_id: str) -> tuple[Dict[str, Any], int]:
    try:
        cached_score = snapshot_score(get_score_state(score_id))
    except KeyError as exc:
        raise ScoreNotFoundError(f"score {score_id} not found") from exc

    project_id = SCORE_PROJECT_CACHE.get(score_id)
    if project_id is None:
        raise ScoreNotFoundError(f"score {score_id} not found")
    return cached_score, int(project_id)


def _build_cached_export_listing(score_id: str) -> Dict[str, Any]:
    listing = SCORE_EXPORT_CACHE.get(score_id)
    if listing is None:
        _, project_id = _load_sheet_from_cache(score_id)
        listing = {"score_id": score_id, "project_id": int(project_id), "items": []}
        SCORE_EXPORT_CACHE[score_id] = deepcopy(listing)

    items = deepcopy(listing.get("items", []))
    return {
        "score_id": score_id,
        "project_id": int(listing["project_id"]),
        "count": len(items),
        "items": items,
    }


def _cache_export_listing(score_id: str, project_id: int, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    SCORE_EXPORT_CACHE[score_id] = {
        "score_id": score_id,
        "project_id": int(project_id),
        "items": deepcopy(items),
    }
    return _build_cached_export_listing(score_id)


def _upsert_cached_export_item(score_id: str, project_id: int, item: Dict[str, Any]) -> Dict[str, Any]:
    listing = _build_cached_export_listing(score_id)
    items = [existing for existing in listing["items"] if int(existing["export_record_id"]) != int(item["export_record_id"])]
    items.insert(0, deepcopy(item))
    return _cache_export_listing(score_id, project_id, items)


def _get_cached_export_item(score_id: str, export_record_id: int) -> Dict[str, Any]:
    listing = _build_cached_export_listing(score_id)
    for item in listing["items"]:
        if int(item["export_record_id"]) == int(export_record_id):
            return deepcopy(item)
    raise ExportRecordNotFoundError(f"export record {export_record_id} not found for score {score_id}")


def _is_db_fallback_exception(exc: Exception) -> bool:
    if isinstance(exc, SQLAlchemyError):
        return True
    if not isinstance(exc, RuntimeError):
        return False
    message = str(exc).strip().lower()
    return any(marker in message for marker in _DB_FALLBACK_RUNTIME_MARKERS)



def _load_sheet(score_id: str) -> tuple[Dict[str, Any], int]:
    try:
        with session_scope() as session:
            sheet = get_sheet_by_score_id(session, score_id)
            if sheet is None:
                logger.warning(
                    "Score %s was not found in DB; using in-memory fallback if available",
                    score_id,
                )
                return _load_sheet_from_cache(score_id)
            score = score_from_sheet(sheet)
            project_id = int(sheet.project_id)
            _cache_score_runtime_state(score, project_id)
            return score, project_id
    except Exception as exc:
        if not _is_db_fallback_exception(exc):
            raise
        logger.warning("Failed to load score %s from DB; using in-memory fallback if available: %s", score_id, exc)
        return _load_sheet_from_cache(score_id)



def _sync_score_cache(score: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cached = get_score_state(score["score_id"])
    except KeyError:
        save_score(score)
        return get_score_state(score["score_id"])

    if int(cached.get("version", 1)) != int(score.get("version", 1)):
        save_score(score)
        return get_score_state(score["score_id"])

    return cached



def _persist_score(score: Dict[str, Any], project_id: int) -> Dict[str, Any]:
    score["project_id"] = int(project_id)
    try:
        with session_scope() as session:
            sheet = get_sheet_by_score_id(session, score["score_id"])
            if sheet is None:
                logger.warning(
                    "Score %s is not persisted in DB; keeping in-memory state only",
                    score["score_id"],
                )
                _cache_score_runtime_state(score, int(project_id))
                return {**snapshot_score(score), "project_id": project_id}
            update_sheet_from_score(session, sheet, score)
            project_id = int(sheet.project_id)
    except Exception as exc:
        if not _is_db_fallback_exception(exc):
            raise
        logger.warning(
            "Failed to persist score %s to DB; using in-memory fallback instead: %s",
            score["score_id"],
            exc,
        )
    _cache_score_runtime_state(score, int(project_id))
    return {**snapshot_score(score), "project_id": project_id}



def _resolve_export_path(file_url: str | None) -> Path | None:
    if not file_url:
        return None

    relative_path = file_url
    if relative_path.startswith(STORAGE_PREFIX):
        relative_path = relative_path[len(STORAGE_PREFIX) :]
        resolved = (settings.storage_dir / relative_path.lstrip("/\\")).resolve()
    else:
        candidate = Path(file_url)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (settings.storage_dir / relative_path.lstrip("/\\")).resolve()

    storage_root = settings.storage_dir.resolve()
    if resolved != storage_root and storage_root not in resolved.parents:
        raise ExportFileNotFoundError("export file path is outside the storage directory")
    return resolved



def _serialize_export_record(score_id: str, record: ExportRecord) -> Dict[str, Any]:
    file_path = _resolve_export_path(record.file_url)
    exists = bool(file_path and file_path.exists())
    file_name = file_path.name if file_path else None
    content_type = mimetypes.guess_type(file_name or record.file_url or "")[0] or "application/octet-stream"
    return {
        "export_record_id": int(record.id),
        "project_id": int(record.project_id),
        "score_id": score_id,
        "format": str(record.format),
        "file_name": file_name,
        "file_path": str(file_path) if file_path else None,
        "download_url": record.file_url,
        "detail_url": f"/api/v1/scores/{score_id}/exports/{int(record.id)}",
        "preview_url": f"/api/v1/scores/{score_id}/exports/{int(record.id)}/preview",
        "download_api_url": f"/api/v1/scores/{score_id}/exports/{int(record.id)}/download",
        "regenerate_url": f"/api/v1/scores/{score_id}/exports/{int(record.id)}/regenerate",
        "delete_url": f"/api/v1/scores/{score_id}/exports/{int(record.id)}",
        "content_type": content_type,
        "exists": exists,
        "size_bytes": file_path.stat().st_size if exists and file_path else 0,
        "created_at": record.create_time.isoformat() if record.create_time else None,
        "updated_at": record.update_time.isoformat() if record.update_time else None,
    }



def _get_export_record_model(score_id: str, export_record_id: int) -> tuple[int, ExportRecord]:
    _, project_id = _load_sheet(score_id)
    with session_scope() as session:
        record = get_export_record_by_id(session, export_record_id)
        if record is None or int(record.project_id) != project_id:
            raise ExportRecordNotFoundError(f"export record {export_record_id} not found for score {score_id}")
        session.expunge(record)
        return project_id, record



def _get_export_record(score_id: str, export_record_id: int) -> Dict[str, Any]:
    _, project_id = _load_sheet(score_id)
    with session_scope() as session:
        record = get_export_record_by_id(session, export_record_id)
        if record is None or int(record.project_id) != project_id:
            raise ExportRecordNotFoundError(f"export record {export_record_id} not found for score {score_id}")
        return _serialize_export_record(score_id, record)



def _safe_unlink(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    file_path.unlink()
    return True



def _build_export_for_record(
    score: Dict[str, Any],
    *,
    export_format: str,
    export_record_id: int,
    page_size: str = "A4",
    with_annotations: bool = True,
) -> Dict[str, Any]:
    return write_score_export(
        score,
        export_format=export_format,
        storage_dir=settings.storage_dir,
        page_size=page_size,
        with_annotations=with_annotations,
        file_stem=f"{score['score_id']}_export_{export_record_id}",
    )



def create_score_from_pitch_sequence(payload: Dict[str, Any]) -> Dict[str, Any]:
    score = build_score_from_pitch_sequence(
        payload["pitch_sequence"],
        tempo=payload.get("tempo", 120),
        time_signature=payload.get("time_signature", "4/4"),
        key_signature=payload.get("key_signature", "C"),
        title=payload.get("title"),
    )
    user_id = int(payload["user_id"])
    title = _default_project_title(payload.get("title"), score["score_id"])
    if score.get("title") != title:
        score = create_canonical_score(
            musicxml=score["musicxml"],
            title=title,
            score_id=score["score_id"],
            version=int(score.get("version", 1)),
        )
    score["title"] = title

    project_id: int | None = None
    try:
        with session_scope() as session:
            user = get_user_by_id(session, user_id)
            if user is None:
                raise UserNotFoundError(f"user {user_id} not found")

            project = create_project(
                session,
                user_id=user.id,
                title=title,
                status=1,
                analysis_id=payload.get("analysis_id"),
                audio_url=None,
                duration=None,
            )
            create_sheet(session, project_id=project.id, score=score)
            project_id = int(project.id)
    except Exception as exc:
        if not _is_db_fallback_exception(exc):
            raise
        project_id = _next_in_memory_project_id()
        logger.warning(
            "Failed to create score %s in DB; using in-memory fallback project_id=%s instead: %s",
            score["score_id"],
            project_id,
            exc,
        )

    score["project_id"] = int(project_id)
    save_score(score)
    _cache_score_runtime_state(score, int(project_id))
    return {**score, "project_id": project_id}



def get_score(score_id: str) -> Dict[str, Any]:
    score, project_id = _load_sheet(score_id)
    cached = _sync_score_cache(score)
    return {**snapshot_score(cached), "project_id": project_id}



def edit_score(score_id: str, musicxml: str) -> Dict[str, Any]:
    db_score, project_id = _load_sheet(score_id)
    score = _sync_score_cache(db_score)
    try:
        updated = update_score_musicxml(score, musicxml)
    except ValueError as exc:
        raise ScoreOperationError(str(exc)) from exc
    return _persist_score(updated, project_id)



def export_score(score_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    score, project_id = _load_sheet(score_id)
    export_format = str(payload.get("format", "pdf"))
    page_size = str(payload.get("page_size", "A4"))
    with_annotations = bool(payload.get("with_annotations", True))

    with session_scope() as session:
        record = create_export_record(session, project_id=project_id, export_format=export_format, file_url=None)
        export_payload = _build_export_for_record(
            score,
            export_format=export_format,
            export_record_id=int(record.id),
            page_size=page_size,
            with_annotations=with_annotations,
        )
        update_export_record(session, record, file_url=export_payload.get("download_url"))
        record_payload = _serialize_export_record(score_id, record)

    _upsert_cached_export_item(score_id, project_id, record_payload)
    return {"project_id": project_id, **export_payload, **record_payload}



def list_score_exports(score_id: str) -> Dict[str, Any]:
    _, project_id = _load_sheet(score_id)
    try:
        with session_scope() as session:
            records = list_export_records_by_project(session, project_id)
            items = [_serialize_export_record(score_id, record) for record in records]
        return _cache_export_listing(score_id, project_id, items)
    except Exception as exc:
        if not _is_db_fallback_exception(exc):
            raise
        logger.warning(
            "Failed to load export list for %s from DB; using in-memory fallback if available: %s",
            score_id,
            exc,
        )
        return _build_cached_export_listing(score_id)



def get_score_export_record(score_id: str, export_record_id: int) -> Dict[str, Any]:
    try:
        record = _get_export_record(score_id, export_record_id)
        _upsert_cached_export_item(score_id, int(record["project_id"]), record)
        return record
    except Exception as exc:
        if not _is_db_fallback_exception(exc):
            raise
        logger.warning(
            "Failed to load export record %s for %s from DB; using in-memory fallback if available: %s",
            export_record_id,
            score_id,
            exc,
        )
        return _get_cached_export_item(score_id, export_record_id)



def get_score_export_file(score_id: str, export_record_id: int) -> Dict[str, Any]:
    export_record = get_score_export_record(score_id, export_record_id)
    if not export_record.get("exists") or not export_record.get("file_path"):
        raise ExportFileNotFoundError(f"export file {export_record_id} is missing for score {score_id}")
    return export_record



def regenerate_score_export(score_id: str, export_record_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    score, project_id = _load_sheet(score_id)
    page_size = str(payload.get("page_size", "A4"))
    with_annotations = bool(payload.get("with_annotations", True))

    with session_scope() as session:
        record = get_export_record_by_id(session, export_record_id)
        if record is None or int(record.project_id) != project_id:
            raise ExportRecordNotFoundError(f"export record {export_record_id} not found for score {score_id}")

        previous_file_url = record.file_url
        previous_file_path = _resolve_export_path(previous_file_url)
        export_payload = _build_export_for_record(
            score,
            export_format=str(record.format),
            export_record_id=int(record.id),
            page_size=page_size,
            with_annotations=with_annotations,
        )
        update_export_record(session, record, file_url=export_payload.get("download_url"))
        record_payload = _serialize_export_record(score_id, record)

        new_file_path = _resolve_export_path(record.file_url)
        if (
            previous_file_path
            and previous_file_path != new_file_path
            and not has_other_export_records_with_file_url(
                session,
                file_url=previous_file_url,
                exclude_export_record_id=int(record.id),
            )
        ):
            _safe_unlink(previous_file_path)

    _upsert_cached_export_item(score_id, project_id, record_payload)
    return {"project_id": project_id, "regenerated": True, **export_payload, **record_payload}



def delete_score_export(score_id: str, export_record_id: int) -> Dict[str, Any]:
    _, project_id = _load_sheet(score_id)

    with session_scope() as session:
        record = get_export_record_by_id(session, export_record_id)
        if record is None or int(record.project_id) != project_id:
            raise ExportRecordNotFoundError(f"export record {export_record_id} not found for score {score_id}")

        payload = _serialize_export_record(score_id, record)
        file_path = _resolve_export_path(record.file_url)
        should_delete_file = not has_other_export_records_with_file_url(
            session,
            file_url=record.file_url,
            exclude_export_record_id=int(record.id),
        )
        file_deleted = bool(file_path and should_delete_file and _safe_unlink(file_path))
        delete_export_record(session, record)

    cached_listing = _build_cached_export_listing(score_id)
    remaining_items = [item for item in cached_listing["items"] if int(item["export_record_id"]) != int(export_record_id)]
    _cache_export_listing(score_id, project_id, remaining_items)
    return {
        "score_id": score_id,
        "project_id": project_id,
        "export_record_id": export_record_id,
        "format": payload.get("format"),
        "file_name": payload.get("file_name"),
        "deleted": True,
        "file_deleted": file_deleted,
    }



def undo_score_action(score_id: str) -> Dict[str, Any]:
    db_score, project_id = _load_sheet(score_id)
    _sync_score_cache(db_score)
    try:
        reverted = _undo_score(score_id)
    except KeyError as exc:
        raise ScoreNotFoundError(f"score {score_id} not found") from exc
    return _persist_score(reverted, project_id)



def redo_score_action(score_id: str) -> Dict[str, Any]:
    db_score, project_id = _load_sheet(score_id)
    _sync_score_cache(db_score)
    try:
        redone = _redo_score(score_id)
    except KeyError as exc:
        raise ScoreNotFoundError(f"score {score_id} not found") from exc
    return _persist_score(redone, project_id)


undo_score = undo_score_action
redo_score = redo_score_action
