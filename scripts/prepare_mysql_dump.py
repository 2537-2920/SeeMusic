#!/usr/bin/env python3
"""Prepare a MySQL dump for shared developer databases with limited privileges.

Usage:
    python scripts/prepare_mysql_dump.py --input SeeMusic --output SeeMusic.safe.sql
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


GTID_PURGED_PATTERN = re.compile(r"^\s*SET\s+@@GLOBAL\.GTID_PURGED\b", re.IGNORECASE)
LOCK_TABLES_PATTERN = re.compile(r"^\s*LOCK\s+TABLES\b", re.IGNORECASE)
UNLOCK_TABLES_PATTERN = re.compile(r"^\s*UNLOCK\s+TABLES\b", re.IGNORECASE)
DEFINER_PATTERN = re.compile(r"/\*![0-9]{5}\s+DEFINER=`[^`]+`@`[^`]+`\s*\*/\s*")


def sanitize_dump(raw_sql: str) -> tuple[str, dict[str, int]]:
    removed = {"gtid_purged": 0, "lock_tables": 0, "unlock_tables": 0, "definer": 0}
    output_lines: list[str] = []

    for line in raw_sql.splitlines(keepends=True):
        if GTID_PURGED_PATTERN.search(line):
            removed["gtid_purged"] += 1
            continue
        if LOCK_TABLES_PATTERN.search(line):
            removed["lock_tables"] += 1
            continue
        if UNLOCK_TABLES_PATTERN.search(line):
            removed["unlock_tables"] += 1
            continue

        # Remove DEFINER clause without dropping the rest of the statement.
        cleaned_line, count = DEFINER_PATTERN.subn("", line)
        if count:
            removed["definer"] += count
        output_lines.append(cleaned_line)

    return "".join(output_lines), removed


def prepare_dump(input_path: Path, output_path: Path) -> dict[str, int]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    raw_sql = input_path.read_text(encoding="utf-8", errors="replace")
    safe_sql, removed = sanitize_dump(raw_sql)
    output_path.write_text(safe_sql, encoding="utf-8", newline="")
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a privilege-safe MySQL dump file.")
    parser.add_argument("--input", "-i", required=True, help="Path to source SQL dump.")
    parser.add_argument("--output", "-o", required=True, help="Path to sanitized SQL dump.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    removed = prepare_dump(input_path, output_path)

    print(f"Prepared safe dump: {output_path}")
    print("Removed:")
    print(f"  GTID_PURGED lines: {removed['gtid_purged']}")
    print(f"  LOCK TABLES lines: {removed['lock_tables']}")
    print(f"  UNLOCK TABLES lines: {removed['unlock_tables']}")
    print(f"  DEFINER clauses: {removed['definer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
