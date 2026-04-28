"""Administrative helpers for maintenance operations on the application database."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


APP_TABLES_TO_TRUNCATE: tuple[str, ...] = (
    "community_favorite",
    "community_like",
    "community_comment",
    "export_record",
    "report",
    "user_history",
    "user_token",
    "user_preference",
    "pitch_sequence",
    "audio_analysis",
    "community_post",
    "sheet",
    "project",
    "user",
)


def _ensure_mysql_connection(connection: Any) -> None:
    dialect = getattr(getattr(connection, "dialect", None), "name", "")
    if dialect != "mysql":
        raise ValueError("These maintenance helpers only support MySQL connections.")


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace("`", "``")
    return f"`{escaped}`"


def truncate_mysql_tables(
    connection: Any,
    *,
    tables: Sequence[str] = APP_TABLES_TO_TRUNCATE,
) -> tuple[str, ...]:
    """Truncate application tables while preserving schema and indexes."""

    _ensure_mysql_connection(connection)
    executed_tables: list[str] = []
    connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
    try:
        for table in tables:
            connection.exec_driver_sql(f"TRUNCATE TABLE {_quote_identifier(table)}")
            executed_tables.append(table)
    finally:
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
    return tuple(executed_tables)


def verify_mysql_tables_cleared(
    connection: Any,
    *,
    tables: Sequence[str] = APP_TABLES_TO_TRUNCATE,
) -> dict[str, dict[str, Any]]:
    """Verify that target tables are empty and still expose indexes."""

    _ensure_mysql_connection(connection)
    counts: dict[str, int] = {}
    indexes: dict[str, list[dict[str, Any]]] = {}

    for table in tables:
        count = int(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {_quote_identifier(table)}").scalar_one())
        if count != 0:
            raise RuntimeError(f"Table {table} is not empty after truncate: {count} rows remain.")
        counts[table] = count

        index_rows = [
            dict(row)
            for row in connection.exec_driver_sql(f"SHOW INDEX FROM {_quote_identifier(table)}").mappings()
        ]
        if not index_rows:
            raise RuntimeError(f"Table {table} is missing indexes after truncate verification.")
        indexes[table] = index_rows

    return {"counts": counts, "indexes": indexes}
