from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.db.maintenance import APP_TABLES_TO_TRUNCATE, truncate_mysql_tables, verify_mysql_tables_cleared


class _FakeScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeMappingsResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return list(self._rows)


class _FakeConnection:
    def __init__(
        self,
        *,
        counts: dict[str, int] | None = None,
        indexes: dict[str, list[dict[str, object]]] | None = None,
        fail_on: str | None = None,
    ) -> None:
        self.dialect = SimpleNamespace(name="mysql")
        self.counts = counts or {table: 0 for table in APP_TABLES_TO_TRUNCATE}
        self.indexes = indexes or {
            table: [{"Key_name": "PRIMARY"}, {"Key_name": f"ix_{table}_sample"}]
            for table in APP_TABLES_TO_TRUNCATE
        }
        self.fail_on = fail_on
        self.statements: list[str] = []

    def exec_driver_sql(self, statement: str):
        self.statements.append(statement)
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError(f"boom: {statement}")
        if statement.startswith("SELECT COUNT(*) FROM "):
            table = statement.split("`")[1]
            return _FakeScalarResult(self.counts[table])
        if statement.startswith("SHOW INDEX FROM "):
            table = statement.split("`")[1]
            return _FakeMappingsResult(self.indexes[table])
        return None


def test_truncate_mysql_tables_disables_foreign_keys_and_restores_them() -> None:
    connection = _FakeConnection()

    tables = truncate_mysql_tables(connection)

    assert tables == APP_TABLES_TO_TRUNCATE
    assert connection.statements[0] == "SET FOREIGN_KEY_CHECKS=0"
    assert connection.statements[-1] == "SET FOREIGN_KEY_CHECKS=1"
    assert connection.statements[1:-1] == [
        f"TRUNCATE TABLE `{table}`"
        for table in APP_TABLES_TO_TRUNCATE
    ]


def test_truncate_mysql_tables_restores_foreign_key_checks_after_failure() -> None:
    failing_table = APP_TABLES_TO_TRUNCATE[3]
    connection = _FakeConnection(fail_on=f"`{failing_table}`")

    with pytest.raises(RuntimeError, match="boom"):
        truncate_mysql_tables(connection)

    assert connection.statements[0] == "SET FOREIGN_KEY_CHECKS=0"
    assert connection.statements[-1] == "SET FOREIGN_KEY_CHECKS=1"


def test_verify_mysql_tables_cleared_returns_counts_and_indexes() -> None:
    connection = _FakeConnection()

    verification = verify_mysql_tables_cleared(connection)

    assert verification["counts"] == {table: 0 for table in APP_TABLES_TO_TRUNCATE}
    assert all("PRIMARY" in {row["Key_name"] for row in rows} for rows in verification["indexes"].values())


def test_verify_mysql_tables_cleared_raises_when_rows_remain() -> None:
    connection = _FakeConnection(counts={"user": 2, **{table: 0 for table in APP_TABLES_TO_TRUNCATE if table != "user"}})

    with pytest.raises(RuntimeError, match="user is not empty"):
        verify_mysql_tables_cleared(connection)
