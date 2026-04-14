from __future__ import annotations

from backend.config.settings import Settings
from backend.db.session import resolve_database_url


def test_settings_builds_mysql_connection_from_env(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "3307")
    monkeypatch.setenv("DB_USER", "score_user")
    monkeypatch.setenv("DB_PASSWORD", "secret_pwd")
    monkeypatch.setenv("DB_NAME", "SeeMusic")

    config = Settings()

    assert config.db_host == "db.example.com"
    assert config.db_port == 3307
    assert config.db_user == "score_user"
    assert config.db_name == "SeeMusic"
    assert config.database_url == "mysql+pymysql://score_user:secret_pwd@db.example.com:3307/SeeMusic?charset=utf8mb4"


def test_database_url_override_takes_priority(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///override.db")

    assert resolve_database_url() == "sqlite+pysqlite:///override.db"
