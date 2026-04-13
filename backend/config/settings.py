"""Application settings for the Music AI System."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus


ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        file_value = value.strip().strip("\"'")
        current_value = os.environ.get(key)
        if current_value is not None:
            cleaned_current = current_value.strip()
            if cleaned_current and not cleaned_current.lower().startswith("your_"):
                continue
        os.environ[key] = file_value


_load_env_file(ROOT_DIR / ".env")


def _nonempty_env(*values: str | None) -> str | None:
    for value in values:
        if value is None:
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        if cleaned.lower().startswith("your_"):
            continue
        return cleaned
    return None


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Music AI System"))
    api_prefix: str = field(default_factory=lambda: os.getenv("API_PREFIX", "/api/v1"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "0") == "1")
    storage_dir: Path = field(default_factory=lambda: (ROOT_DIR / os.getenv("STORAGE_DIR", "storage")).resolve())
    max_upload_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")))
    ssh_host: str = field(default_factory=lambda: os.getenv("SSH_HOST", ""))
    ssh_port: int = field(default_factory=lambda: int(os.getenv("SSH_PORT", "22")))
    ssh_user: str = field(default_factory=lambda: os.getenv("SSH_USER", ""))
    ssh_key_file: str = field(default_factory=lambda: os.getenv("SSH_KEY_FILE", ""))
    mysql_host: str = field(default_factory=lambda: os.getenv("MYSQL_HOST", "127.0.0.1"))
    mysql_port: int = field(default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")))
    mysql_user: str = field(default_factory=lambda: os.getenv("MYSQL_USER", ""))
    mysql_password: str = field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    mysql_db_name: str = field(default_factory=lambda: os.getenv("MYSQL_DB_NAME", ""))
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "127.0.0.1"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "3307")))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "root"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "SeeMusic"))

    @property
    def database_url(self) -> str:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return database_url

        user = _nonempty_env(self.mysql_user, self.db_user) or self.db_user
        password = _nonempty_env(self.mysql_password, self.db_password) or self.db_password
        db_name = _nonempty_env(self.mysql_db_name, self.db_name) or self.db_name
        return f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{self.db_host}:{self.db_port}/{db_name}?charset=utf8mb4"


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
