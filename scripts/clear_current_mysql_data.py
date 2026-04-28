#!/usr/bin/env python3
"""Clear current application data from the MySQL database resolved from .env."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.maintenance import APP_TABLES_TO_TRUNCATE, truncate_mysql_tables, verify_mysql_tables_cleared
from backend.db.session import get_engine, resolve_database_url, reset_database_state


def _describe_target(database_url: str) -> dict[str, Any]:
    url = make_url(database_url)
    return {
        "driver": url.drivername,
        "host": url.host,
        "port": url.port,
        "database": url.database,
        "username": url.username,
    }


def main() -> int:
    database_url = resolve_database_url()
    if not database_url.startswith("mysql"):
        raise SystemExit(f"Current DATABASE_URL is not MySQL: {database_url}")

    engine = get_engine()
    try:
        with engine.begin() as connection:
            truncated_tables = truncate_mysql_tables(connection, tables=APP_TABLES_TO_TRUNCATE)
            verification = verify_mysql_tables_cleared(connection, tables=truncated_tables)
    finally:
        reset_database_state()

    print("Cleared application data from current MySQL database.")
    print(
        json.dumps(
            {
                "target": _describe_target(database_url),
                "tables": verification["counts"],
                "index_names": {
                    table: sorted({str(item.get("Key_name")) for item in rows})
                    for table, rows in verification["indexes"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
