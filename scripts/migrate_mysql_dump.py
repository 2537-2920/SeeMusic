#!/usr/bin/env python3
"""Upload and import a privilege-safe MySQL dump over SSH."""

from __future__ import annotations

import argparse
import getpass
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from prepare_mysql_dump import prepare_dump


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
VERIFY_SQL_FILE = ROOT_DIR / "scripts" / "verify_seemusic_import.sql"
USE_STATEMENT_PATTERN = re.compile(r"^\s*USE\s+`[^`]+`;\s*$", re.MULTILINE)


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("\"'")
    return env


def pick_value(cli_value: object, env: dict[str, str], env_key: str, default: object = None) -> object:
    if cli_value is not None:
        return cli_value
    if env_key in env and env[env_key] != "":
        return env[env_key]
    return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare, upload, and import a MySQL dump over SSH.")
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the .env file. Default: project-root/.env.",
    )
    parser.add_argument("--host", help="Remote server IP or hostname. Falls back to SSH_HOST in .env.")
    parser.add_argument("--ssh-user", help="SSH username. Falls back to SSH_USER in .env.")
    parser.add_argument("--key-file", help="SSH private key path. Falls back to SSH_KEY_FILE in .env.")
    parser.add_argument("--ssh-port", type=int, help="SSH port. Falls back to SSH_PORT or 22.")
    parser.add_argument("--input", help="Source SQL dump path. Falls back to MYSQL_DUMP_INPUT or SeeMusic.")
    parser.add_argument("--output", help="Sanitized SQL dump path. Falls back to MYSQL_DUMP_OUTPUT.")
    parser.add_argument("--db-name", help="Remote database name. Falls back to MYSQL_DB_NAME or SeeMusic.")
    parser.add_argument("--mysql-user", help="Remote MySQL username. Falls back to MYSQL_USER in .env.")
    parser.add_argument("--mysql-password", help="Remote MySQL password. Falls back to MYSQL_PASSWORD in .env.")
    parser.add_argument(
        "--allow-empty-password",
        action="store_true",
        help="Use an intentionally empty MySQL password instead of prompting.",
    )
    parser.add_argument("--mysql-host", help="Remote MySQL host. Falls back to MYSQL_HOST or 127.0.0.1.")
    parser.add_argument("--mysql-port", type=int, help="Remote MySQL port. Falls back to MYSQL_PORT or 3306.")
    parser.add_argument(
        "--remote-dir",
        help="Remote temporary directory. Falls back to MYSQL_REMOTE_DIR or /tmp/seemusic_migration.",
    )
    parser.add_argument(
        "--keep-remote-files",
        action="store_true",
        help="Keep uploaded SQL and credential files on the remote host after import.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the post-import verification query.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands that would run without executing them.",
    )
    return parser.parse_args()


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f"Required command not found in PATH: {name}")


def run_command(command: list[str], dry_run: bool) -> None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"$ {printable}")
    if not dry_run:
        subprocess.run(command, check=True, env=build_subprocess_env())


def build_ssh_base(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-i",
        str(Path(args.key_file).expanduser().resolve()),
        "-p",
        str(args.ssh_port),
        f"{args.ssh_user}@{args.host}",
    ]


def build_scp_base(args: argparse.Namespace) -> list[str]:
    return [
        "scp",
        "-i",
        str(Path(args.key_file).expanduser().resolve()),
        "-P",
        str(args.ssh_port),
    ]


def remote_quote(value: str) -> str:
    return shlex.quote(value)


def require_config(config: dict[str, object], key: str, hint: str) -> str:
    value = config.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required setting `{key}`. Set {hint} in .env or pass the CLI flag.")
    return str(value)


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    return env


def render_verify_sql(db_name: str) -> str:
    if not VERIFY_SQL_FILE.exists():
        raise FileNotFoundError(f"Verification SQL template not found: {VERIFY_SQL_FILE}")

    template = VERIFY_SQL_FILE.read_text(encoding="utf-8-sig")
    rendered, replaced = USE_STATEMENT_PATTERN.subn(f"USE `{db_name}`;", template, count=1)
    if replaced:
        return rendered
    return f"USE `{db_name}`;\n\n{template}"


def main() -> int:
    args = parse_args()
    require_binary("ssh")
    require_binary("scp")

    env_file = Path(args.env_file).expanduser().resolve()
    env = load_env_file(env_file)
    config = {
        "host": pick_value(args.host, env, "SSH_HOST"),
        "ssh_user": pick_value(args.ssh_user, env, "SSH_USER"),
        "key_file": pick_value(args.key_file, env, "SSH_KEY_FILE"),
        "ssh_port": int(pick_value(args.ssh_port, env, "SSH_PORT", 22)),
        "input": pick_value(args.input, env, "MYSQL_DUMP_INPUT", "SeeMusic"),
        "output": pick_value(args.output, env, "MYSQL_DUMP_OUTPUT", "SeeMusic.safe.sql"),
        "db_name": pick_value(args.db_name, env, "MYSQL_DB_NAME", "SeeMusic"),
        "mysql_user": pick_value(args.mysql_user, env, "MYSQL_USER"),
        "mysql_password": pick_value(args.mysql_password, env, "MYSQL_PASSWORD", ""),
        "allow_empty_password": args.allow_empty_password or parse_bool(env.get("MYSQL_ALLOW_EMPTY_PASSWORD")),
        "mysql_host": pick_value(args.mysql_host, env, "MYSQL_HOST", "127.0.0.1"),
        "mysql_port": int(pick_value(args.mysql_port, env, "MYSQL_PORT", 3306)),
        "remote_dir": pick_value(args.remote_dir, env, "MYSQL_REMOTE_DIR", "/tmp/seemusic_migration"),
        "keep_remote_files": args.keep_remote_files or parse_bool(env.get("MYSQL_KEEP_REMOTE_FILES")),
        "skip_verify": args.skip_verify or parse_bool(env.get("MYSQL_SKIP_VERIFY")),
    }

    host = require_config(config, "host", "SSH_HOST / --host")
    ssh_user = require_config(config, "ssh_user", "SSH_USER / --ssh-user")
    key_file = require_config(config, "key_file", "SSH_KEY_FILE / --key-file")
    mysql_user = require_config(config, "mysql_user", "MYSQL_USER / --mysql-user")

    input_path = Path(str(config["input"])).expanduser().resolve()
    output_path = Path(str(config["output"])).expanduser().resolve()

    print("Preparing privilege-safe dump...")
    removed = prepare_dump(input_path, output_path)
    print(f"Prepared safe dump: {output_path}")
    print(
        "Removed:"
        f" GTID_PURGED={removed['gtid_purged']},"
        f" LOCK TABLES={removed['lock_tables']},"
        f" UNLOCK TABLES={removed['unlock_tables']},"
        f" DEFINER={removed['definer']}"
    )

    mysql_password = str(config["mysql_password"])
    if not mysql_password and not args.dry_run and not config["allow_empty_password"]:
        mysql_password = getpass.getpass(f"MySQL password for {mysql_user}@{config['mysql_host']}: ")

    runtime_args = argparse.Namespace(
        host=host,
        ssh_user=ssh_user,
        key_file=key_file,
        ssh_port=int(config["ssh_port"]),
    )
    ssh_base = build_ssh_base(runtime_args)
    scp_base = build_scp_base(runtime_args)

    remote_dir = str(config["remote_dir"]).rstrip("/")
    db_name = str(config["db_name"])
    remote_safe_dump = posixpath.join(remote_dir, f"{db_name}.safe.sql")
    remote_create_sql = posixpath.join(remote_dir, "create_db.sql")
    remote_verify_sql = posixpath.join(remote_dir, "verify_import.sql")
    remote_client_cnf = posixpath.join(remote_dir, "mysql_client.cnf")

    create_sql = (
        f"CREATE DATABASE IF NOT EXISTS `{db_name}`\n"
        "  CHARACTER SET utf8mb4\n"
        "  COLLATE utf8mb4_0900_ai_ci;\n"
    )
    verify_sql = render_verify_sql(db_name)
    client_cnf = (
        "[client]\n"
        f"user={mysql_user}\n"
        f"password={mysql_password}\n"
        f"host={config['mysql_host']}\n"
        f"port={config['mysql_port']}\n"
    )

    with tempfile.TemporaryDirectory(prefix="seemusic-migrate-") as temp_dir:
        temp_path = Path(temp_dir)
        create_path = temp_path / "create_db.sql"
        verify_path = temp_path / "verify_import.sql"
        cnf_path = temp_path / "mysql_client.cnf"

        create_path.write_text(create_sql, encoding="utf-8", newline="")
        verify_path.write_text(verify_sql, encoding="utf-8", newline="")
        cnf_path.write_text(client_cnf, encoding="utf-8", newline="")

        run_command(
            ssh_base
            + [
                f"mkdir -p {remote_quote(remote_dir)} && chmod 700 {remote_quote(remote_dir)}",
            ],
            args.dry_run,
        )

        for local_path, remote_path in (
            (output_path, remote_safe_dump),
            (create_path, remote_create_sql),
            (verify_path, remote_verify_sql),
            (cnf_path, remote_client_cnf),
        ):
            run_command(
                scp_base
                + [
                    str(local_path),
                    f"{ssh_user}@{host}:{remote_path}",
                ],
                args.dry_run,
            )

        remote_steps = [
            "set -e",
            f"chmod 600 {remote_quote(remote_client_cnf)}",
            (
                f"mysql --defaults-extra-file={remote_quote(remote_client_cnf)} "
                f"< {remote_quote(remote_create_sql)}"
            ),
            (
                f"mysql --defaults-extra-file={remote_quote(remote_client_cnf)} "
                f"{remote_quote(db_name)} < {remote_quote(remote_safe_dump)}"
            ),
        ]
        if not config["skip_verify"]:
            remote_steps.append(
                f"mysql --defaults-extra-file={remote_quote(remote_client_cnf)} "
                f"< {remote_quote(remote_verify_sql)}"
            )
        cleanup_targets = [remote_create_sql, remote_verify_sql, remote_client_cnf]
        if not config["keep_remote_files"]:
            cleanup_targets.append(remote_safe_dump)
        remote_steps.append("rm -f " + " ".join(remote_quote(path) for path in cleanup_targets))

        remote_command = "sh -lc " + remote_quote("; ".join(remote_steps))
        run_command(ssh_base + [remote_command], args.dry_run)

    print("Migration flow completed.")
    if config["keep_remote_files"]:
        print(f"Uploaded files were kept under {remote_dir}")
    else:
        print(f"Uploaded SQL files were cleaned up from {remote_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
