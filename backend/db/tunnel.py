"""SSH tunnel helpers for remote MySQL access."""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from backend.config.settings import Settings


_TUNNEL_LOCK = threading.Lock()
_ACTIVE_TUNNEL: subprocess.Popen[bytes] | None = None


@dataclass(frozen=True)
class TunnelConfig:
    """Runtime settings for forwarding local MySQL traffic to a remote host."""

    ssh_host: str
    ssh_user: str
    ssh_key_file: Path
    ssh_port: int
    local_host: str
    local_port: int
    remote_host: str
    remote_port: int


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _local_port_is_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_tunnel_config(settings: Settings | None = None) -> TunnelConfig | None:
    """Return a tunnel config only when the current database points at localhost."""

    runtime = settings or Settings()
    if not runtime.ssh_host or not runtime.ssh_user or not runtime.ssh_key_file:
        return None
    if not _is_loopback_host(runtime.db_host):
        return None

    ssh_key_file = Path(runtime.ssh_key_file).expanduser()
    if not ssh_key_file.exists():
        raise FileNotFoundError(f"SSH key file does not exist: {ssh_key_file}")

    return TunnelConfig(
        ssh_host=runtime.ssh_host,
        ssh_user=runtime.ssh_user,
        ssh_key_file=ssh_key_file,
        ssh_port=runtime.ssh_port,
        local_host=runtime.db_host,
        local_port=runtime.db_port,
        remote_host=runtime.mysql_host,
        remote_port=runtime.mysql_port,
    )


def build_ssh_tunnel_command(config: TunnelConfig) -> list[str]:
    """Build the SSH command that keeps the MySQL tunnel open."""

    forward_target = f"{config.local_host}:{config.local_port}:{config.remote_host}:{config.remote_port}"
    return [
        "ssh",
        "-i",
        str(config.ssh_key_file),
        "-p",
        str(config.ssh_port),
        "-N",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        "-o",
        "ControlPersist=no",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-L",
        forward_target,
        f"{config.ssh_user}@{config.ssh_host}",
    ]


def _ssh_subprocess_env() -> dict[str, str]:
    """Strip conda OpenSSL overrides so the system ssh binary can start cleanly."""

    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    return env


def _wait_for_tunnel(config: TunnelConfig, process: subprocess.Popen[bytes], timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _local_port_is_open(config.local_host, config.local_port):
            return
        if process.poll() is not None:
            stderr_output = ""
            if process.stderr is not None:
                try:
                    stderr_output = process.stderr.read().decode("utf-8", errors="replace").strip()
                except Exception:
                    stderr_output = ""
            details = f" SSH stderr: {stderr_output}" if stderr_output else ""
            raise RuntimeError(
                "SSH tunnel process exited before the local MySQL port became available. "
                "Check SSH_HOST, SSH_USER, SSH_KEY_FILE, DB_PORT, and network access."
                f"{details}"
            )
        time.sleep(0.2)

    process.terminate()
    raise TimeoutError(
        f"Timed out waiting for SSH tunnel on {config.local_host}:{config.local_port}. "
        "Check the remote host and port forwarding settings."
    )


def ensure_mysql_tunnel(settings: Settings | None = None, timeout_seconds: float = 10.0) -> None:
    """Start the SSH tunnel if the runtime settings point to a forwarded MySQL port."""

    config = build_tunnel_config(settings)
    if config is None:
        return
    if _local_port_is_open(config.local_host, config.local_port):
        return

    with _TUNNEL_LOCK:
        global _ACTIVE_TUNNEL
        process = _ACTIVE_TUNNEL
        if process is None or process.poll() is not None:
            if shutil.which("ssh") is None:
                raise RuntimeError("ssh is not available in PATH, so the MySQL tunnel cannot be started")
            command = build_ssh_tunnel_command(config)
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=_ssh_subprocess_env(),
            )
            _ACTIVE_TUNNEL = process

    _wait_for_tunnel(config, process, timeout_seconds)


def close_mysql_tunnel() -> None:
    """Terminate the background SSH tunnel if one is running."""

    global _ACTIVE_TUNNEL
    process = _ACTIVE_TUNNEL
    _ACTIVE_TUNNEL = None
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


atexit.register(close_mysql_tunnel)
