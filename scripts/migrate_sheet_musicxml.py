"""One-off migration: convert legacy sheet.note_data scores into canonical MusicXML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect, text

from backend.core.score.musicxml_utils import (
    build_canonical_score_from_musicxml,
    build_score_metadata_snapshot,
    musicxml_from_legacy_score,
)
from backend.db.models import Sheet
from backend.db.session import init_database, session_scope


@dataclass
class MigrationStats:
    total_rows: int = 0
    migrated_rows: int = 0
    skipped_rows: int = 0
    failed_rows: int = 0


def _ensure_musicxml_column() -> None:
    with session_scope() as session:
        bind = session.get_bind()
        inspector = inspect(bind)
        columns = {column["name"] for column in inspector.get_columns("sheet")}
        if "musicxml" in columns:
            return

        dialect_name = bind.dialect.name
        if dialect_name == "mysql":
            session.execute(text("ALTER TABLE sheet ADD COLUMN musicxml LONGTEXT NULL"))
        else:
            session.execute(text("ALTER TABLE sheet ADD COLUMN musicxml TEXT NULL"))


def migrate_sheets() -> MigrationStats:
    stats = MigrationStats()
    _ensure_musicxml_column()

    with session_scope() as session:
        sheets = session.query(Sheet).order_by(Sheet.id.asc()).all()
        stats.total_rows = len(sheets)

        for sheet in sheets:
            try:
                if sheet.musicxml:
                    canonical = build_canonical_score_from_musicxml(
                        sheet.musicxml,
                        score_id=sheet.score_id,
                        title=(sheet.note_data or {}).get("title"),
                        version=int((sheet.note_data or {}).get("version", 1)),
                        project_id=int(sheet.project_id),
                    )
                    sheet.musicxml = canonical["musicxml"]
                    sheet.note_data = build_score_metadata_snapshot(canonical)
                    sheet.bpm = canonical["tempo"]
                    sheet.key_sign = canonical["key_signature"]
                    sheet.time_sign = canonical["time_signature"]
                    stats.skipped_rows += 1
                    continue

                legacy_payload = dict(sheet.note_data or {})
                if not legacy_payload.get("measures"):
                    stats.failed_rows += 1
                    continue

                musicxml = musicxml_from_legacy_score(legacy_payload, fallback_title=legacy_payload.get("title"))
                canonical = build_canonical_score_from_musicxml(
                    musicxml,
                    score_id=sheet.score_id,
                    title=legacy_payload.get("title"),
                    version=int(legacy_payload.get("version", 1)),
                    project_id=int(sheet.project_id),
                )
                sheet.musicxml = canonical["musicxml"]
                sheet.note_data = build_score_metadata_snapshot(canonical)
                sheet.bpm = canonical["tempo"]
                sheet.key_sign = canonical["key_signature"]
                sheet.time_sign = canonical["time_signature"]
                session.add(sheet)
                stats.migrated_rows += 1
            except Exception:
                stats.failed_rows += 1

    return stats


def main() -> None:
    init_database()
    stats = migrate_sheets()
    print("Sheet MusicXML migration finished")
    print(f"  total:    {stats.total_rows}")
    print(f"  migrated: {stats.migrated_rows}")
    print(f"  skipped:  {stats.skipped_rows}")
    print(f"  failed:   {stats.failed_rows}")


if __name__ == "__main__":
    main()
