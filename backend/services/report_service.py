"""Report export helpers."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy import select

from backend.export.export_utils import build_export_files


USE_DB: bool = False
_session_factory = None
REPORT_EXPORTS: dict[str, dict[str, Any]] = {}


def set_db_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


@contextmanager
def _session_scope() -> Iterator[Any]:
    if _session_factory is None:
        raise RuntimeError("DB mode enabled but no session factory configured")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_report_exports() -> None:
    REPORT_EXPORTS.clear()


def export_report(payload: dict) -> dict:
    report_id = f"r_{uuid4().hex[:8]}"
    files = build_export_files(report_id, payload.get("formats", []))
    result = {
        "report_id": report_id,
        "analysis_id": payload.get("analysis_id"),
        "files": files,
        "include_charts": payload.get("include_charts", True),
    }

    if not USE_DB:
        REPORT_EXPORTS[report_id] = deepcopy(result)
        return result

    from backend.db.models import Project, Report

    analysis_id = payload.get("analysis_id")
    with _session_scope() as session:
        project = None
        if analysis_id:
            project = session.execute(select(Project).where(Project.analysis_id == analysis_id)).scalar_one_or_none()
        report = Report(
            report_id=report_id,
            project_id=int(project.id) if project is not None else None,
            analysis_id=analysis_id,
            pitch_score=payload.get("pitch_score"),
            rhythm_score=payload.get("rhythm_score"),
            total_score=payload.get("total_score"),
            error_points=payload.get("error_points"),
            export_url=files[0]["download_url"] if files else None,
            metadata_={
                "formats": list(payload.get("formats") or []),
                "files": files,
                "include_charts": bool(payload.get("include_charts", True)),
            },
        )
        session.add(report)

    return result
