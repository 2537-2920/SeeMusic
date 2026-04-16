from __future__ import annotations

import os

from backend.config.settings import Settings
from sqlalchemy import inspect

from backend.db.session import _engine_options, get_engine, init_database, reset_database_state, resolve_database_url
from backend.db.tunnel import TunnelConfig, _ssh_subprocess_env, build_ssh_tunnel_command


def test_settings_builds_mysql_connection_from_env(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_USER", "")
    monkeypatch.setenv("MYSQL_PASSWORD", "")
    monkeypatch.setenv("MYSQL_DB_NAME", "")
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


def test_settings_prefers_mysql_connection_over_db_values(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "root_pwd")
    monkeypatch.setenv("MYSQL_DB_NAME", "SeeMusic")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "3307")
    monkeypatch.setenv("DB_USER", "score_user")
    monkeypatch.setenv("DB_PASSWORD", "secret_pwd")
    monkeypatch.setenv("DB_NAME", "OtherDB")

    config = Settings()

    assert config.database_url == "mysql+pymysql://root:root_pwd@db.example.com:3307/SeeMusic?charset=utf8mb4"


def test_load_env_file_overrides_blank_env_values(monkeypatch, tmp_path) -> None:
    from backend.config.settings import _load_env_file

    env_file = tmp_path / ".env"
    env_file.write_text("MYSQL_USER=root\nDB_USER=seemusic_app\n", encoding="utf-8")

    monkeypatch.setenv("MYSQL_USER", "")
    monkeypatch.setenv("DB_USER", "")

    _load_env_file(env_file)

    assert os.environ["MYSQL_USER"] == "root"
    assert os.environ["DB_USER"] == "seemusic_app"


def test_database_url_override_takes_priority(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///override.db")

    assert resolve_database_url() == "sqlite+pysqlite:///override.db"


def test_engine_options_enable_mysql_timeouts_and_recycle() -> None:
    options = _engine_options("mysql+pymysql://root@127.0.0.1:3307/SeeMusic")

    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] == 300
    assert options["pool_timeout"] == 10
    assert options["connect_args"] == {
        "connect_timeout": 5,
        "read_timeout": 15,
        "write_timeout": 15,
    }


def test_init_database_creates_all_declared_tables(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "schema.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")

    reset_database_state()
    init_database()

    table_names = set(inspect(get_engine()).get_table_names())
    assert {
        "user",
        "project",
        "sheet",
        "export_record",
        "report",
        "community_post",
        "community_comment",
        "community_like",
        "community_favorite",
        "audio_analysis",
        "pitch_sequence",
        "user_history",
    }.issubset(table_names)

    inspector = inspect(get_engine())
    report_columns = {column["name"] for column in inspector.get_columns("report")}
    community_post_columns = {column["name"] for column in inspector.get_columns("community_post")}
    audio_analysis_columns = {column["name"] for column in inspector.get_columns("audio_analysis")}

    assert {"report_id", "analysis_id", "metadata"}.issubset(report_columns)
    assert {
        "community_score_id",
        "score_id",
        "author_name",
        "subtitle",
        "style",
        "instrument",
        "price",
        "cover_url",
        "source_file_name",
        "file_content_base64",
        "file_content_type",
        "favorite_count",
        "download_count",
    }.issubset(community_post_columns)
    assert {"result"}.issubset(audio_analysis_columns)

    reset_database_state()


def test_build_ssh_tunnel_command_uses_forwarded_mysql_port(tmp_path) -> None:
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("dummy", encoding="utf-8")

    command = build_ssh_tunnel_command(
        TunnelConfig(
            ssh_host="175.24.130.34",
            ssh_user="ubuntu",
            ssh_key_file=key_file,
            ssh_port=22,
            local_host="127.0.0.1",
            local_port=3307,
            remote_host="127.0.0.1",
            remote_port=3306,
        )
    )

    assert command[0] == "ssh"
    assert "-L" in command
    assert "127.0.0.1:3307:127.0.0.1:3306" in command
    assert "ControlMaster=no" in command
    assert "ControlPath=none" in command
    assert "ControlPersist=no" in command
    assert "-o" in command and "StrictHostKeyChecking=accept-new" in command
    assert "-o" in command and "IdentitiesOnly=yes" in command
    assert command[-1] == "ubuntu@175.24.130.34"


def test_ssh_subprocess_env_strips_conda_library_overrides(monkeypatch) -> None:
    monkeypatch.setenv("LD_LIBRARY_PATH", "/home/xianz/anaconda3/lib")
    monkeypatch.setenv("LD_PRELOAD", "libexample.so")

    env = _ssh_subprocess_env()

    assert env.get("LD_LIBRARY_PATH") is None
    assert env.get("LD_PRELOAD") is None
