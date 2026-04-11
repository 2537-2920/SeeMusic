"""Report export helpers."""

from __future__ import annotations

from uuid import uuid4

from backend.export.export_utils import build_export_files


def export_report(payload: dict) -> dict:
    report_id = f"r_{uuid4().hex[:8]}"
    files = build_export_files(report_id, payload.get("formats", []))
    return {
        "report_id": report_id,
        "analysis_id": payload.get("analysis_id"),
        "files": files,
        "include_charts": payload.get("include_charts", True),
    }

