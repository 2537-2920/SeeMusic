"""Repository helpers for score-related database operations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import ExportRecord, Project, Sheet, User


def get_user_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def create_project(
    session: Session,
    *,
    user_id: int,
    title: str,
    status: int = 1,
    analysis_id: str | None = None,
    audio_url: str | None = None,
    duration: float | None = None,
) -> Project:
    project = Project(
        user_id=user_id,
        title=title,
        status=status,
        analysis_id=analysis_id,
        audio_url=audio_url,
        duration=duration,
    )
    session.add(project)
    session.flush()
    return project


def get_sheet_by_score_id(session: Session, score_id: str) -> Sheet | None:
    statement = select(Sheet).where(Sheet.score_id == score_id)
    return session.execute(statement).scalar_one_or_none()


def _score_snapshot(score: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(score)
    snapshot.pop("undo_stack", None)
    snapshot.pop("redo_stack", None)
    return snapshot


def score_from_sheet(sheet: Sheet) -> dict[str, Any]:
    score = deepcopy(sheet.note_data or {})
    score["score_id"] = score.get("score_id") or sheet.score_id
    score["tempo"] = int(score.get("tempo", sheet.bpm or 120))
    score["key_signature"] = str(score.get("key_signature", sheet.key_sign or "C"))
    score["time_signature"] = str(score.get("time_signature", sheet.time_sign or "4/4"))
    score["version"] = int(score.get("version", 1))
    return score


def create_sheet(session: Session, *, project_id: int, score: dict[str, Any]) -> Sheet:
    snapshot = _score_snapshot(score)
    sheet = Sheet(
        project_id=project_id,
        score_id=snapshot["score_id"],
        note_data=snapshot,
        bpm=int(snapshot.get("tempo", 120)),
        key_sign=str(snapshot.get("key_signature", "C")),
        time_sign=str(snapshot.get("time_signature", "4/4")),
    )
    session.add(sheet)
    session.flush()
    return sheet


def update_sheet_from_score(session: Session, sheet: Sheet, score: dict[str, Any]) -> Sheet:
    snapshot = _score_snapshot(score)
    sheet.note_data = snapshot
    sheet.score_id = snapshot.get("score_id")
    sheet.bpm = int(snapshot.get("tempo", 120))
    sheet.key_sign = str(snapshot.get("key_signature", "C"))
    sheet.time_sign = str(snapshot.get("time_signature", "4/4"))
    session.add(sheet)
    session.flush()
    return sheet


def create_export_record(session: Session, *, project_id: int, export_format: str, file_url: str | None = None) -> ExportRecord:
    record = ExportRecord(project_id=project_id, format=export_format, file_url=file_url)
    session.add(record)
    session.flush()
    return record


def update_export_record(session: Session, record: ExportRecord, *, file_url: str | None = None) -> ExportRecord:
    record.file_url = file_url
    session.add(record)
    session.flush()
    return record


def delete_export_record(session: Session, record: ExportRecord) -> None:
    session.delete(record)
    session.flush()


def list_export_records_by_project(session: Session, project_id: int) -> list[ExportRecord]:
    statement = select(ExportRecord).where(ExportRecord.project_id == project_id).order_by(ExportRecord.id.desc())
    return list(session.execute(statement).scalars())


def get_export_record_by_id(session: Session, export_record_id: int) -> ExportRecord | None:
    return session.get(ExportRecord, export_record_id)


def has_other_export_records_with_file_url(
    session: Session,
    *,
    file_url: str | None,
    exclude_export_record_id: int,
) -> bool:
    if not file_url:
        return False
    statement = select(func.count()).select_from(ExportRecord).where(
        ExportRecord.file_url == file_url,
        ExportRecord.id != exclude_export_record_id,
    )
    return bool(session.execute(statement).scalar_one())
