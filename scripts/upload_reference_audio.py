#!/usr/bin/env python3
"""Batch upload reference audio files and register their storage URLs in MySQL."""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from backend.config.settings import ROOT_DIR
from backend.db.session import get_session_factory, init_database
from backend.services import reference_track_service
from backend.services.reference_track_service import build_reference_audio_url


DEFAULT_ENV_FILE = ROOT_DIR / ".env"
DEFAULT_SOURCE_DIR = ROOT_DIR / "Music"
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".flac"}
PATTERN_NUMBER_ARTIST_TITLE = re.compile(r"^(?P<number>\d{4})-(?P<artist>.+)-(?P<title>.+)$")
PATTERN_ARTIST_TITLE = re.compile(r"^(?P<artist>.+)-(?P<title>.+)$")
PATTERN_NUMBER_DOT_ARTIST_TITLE = re.compile(r"^(?P<number>\d{4})\.(?P<artist>.+)-(?P<title>.+)$")
PATTERN_NUMBER_TITLE_ARTIST = re.compile(r"^(?P<number>\d{4})\.(?P<title>.+)\.(?P<artist>.+)$")


@dataclass(frozen=True)
class ParsedTrack:
    file_path: Path
    song_name: str
    artist_name: str


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


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    return env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload Music/ reference audio files and register them in MySQL.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Path to .env file. Default: project-root/.env")
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Local source directory. Default: project-root/Music",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without uploading or writing DB.")
    return parser.parse_args()


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f"Required command not found in PATH: {name}")


def parse_track_filename(file_path: Path) -> ParsedTrack:
    stem = file_path.stem.strip()
    for pattern, song_group, artist_group in (
        (PATTERN_NUMBER_DOT_ARTIST_TITLE, "title", "artist"),
        (PATTERN_NUMBER_ARTIST_TITLE, "title", "artist"),
        (PATTERN_ARTIST_TITLE, "title", "artist"),
        (PATTERN_NUMBER_TITLE_ARTIST, "title", "artist"),
    ):
        match = pattern.fullmatch(stem)
        if not match:
            continue
        song_name = match.group(song_group).strip()
        artist_name = match.group(artist_group).strip()
        if song_name and artist_name:
            return ParsedTrack(file_path=file_path, song_name=song_name, artist_name=artist_name)

    if stem:
        return ParsedTrack(
            file_path=file_path,
            song_name=stem,
            artist_name=reference_track_service.DEFAULT_ARTIST_NAME,
        )
    raise ValueError(f"Unable to parse track metadata from file name: {file_path.name}")


def iter_local_audio_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Local source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Local source path is not a directory: {source_dir}")
    return sorted(
        file_path
        for file_path in source_dir.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def run_command(command: list[str], *, dry_run: bool) -> None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"$ {printable}")
    if not dry_run:
        subprocess.run(command, check=True, env=build_subprocess_env())


def run_capture(command: list[str], *, dry_run: bool) -> subprocess.CompletedProcess[str] | None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return None
    return subprocess.run(
        command,
        check=False,
        env=build_subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def remote_quote(value: str) -> str:
    return shlex.quote(value)


def build_ssh_base(host: str, ssh_user: str, key_file: Path, ssh_port: int) -> list[str]:
    return [
        "ssh",
        "-i",
        str(key_file),
        "-p",
        str(ssh_port),
        f"{ssh_user}@{host}",
    ]


def build_scp_base(host: str, ssh_user: str, key_file: Path, ssh_port: int) -> list[str]:
    return [
        "scp",
        "-i",
        str(key_file),
        "-P",
        str(ssh_port),
    ]


def remote_file_exists(ssh_base: list[str], remote_path: str, *, dry_run: bool) -> bool:
    result = run_capture(ssh_base + [f"test -f {remote_quote(remote_path)}"], dry_run=dry_run)
    return False if result is None else result.returncode == 0


def main() -> int:
    args = parse_args()
    require_binary("ssh")
    require_binary("scp")

    env = load_env_file(Path(args.env_file).expanduser().resolve())
    host = env.get("SSH_HOST", "").strip()
    ssh_user = env.get("SSH_USER", "").strip()
    ssh_port = int(env.get("SSH_PORT", "22").strip() or "22")
    key_file_raw = env.get("SSH_KEY_FILE", "").strip()
    remote_dir = env.get("REFERENCE_AUDIO_REMOTE_DIR", "").strip()
    if not host or not ssh_user or not key_file_raw or not remote_dir:
        raise ValueError("Missing SSH_HOST, SSH_USER, SSH_KEY_FILE, or REFERENCE_AUDIO_REMOTE_DIR in .env")

    source_dir = Path(args.source_dir).expanduser().resolve()
    local_files = iter_local_audio_files(source_dir)
    key_file = Path(key_file_raw).expanduser().resolve()
    ssh_base = build_ssh_base(host, ssh_user, key_file, ssh_port)
    scp_base = build_scp_base(host, ssh_user, key_file, ssh_port)

    parsed_tracks: list[ParsedTrack] = []
    parse_failures: list[str] = []
    for file_path in local_files:
        try:
            parsed_tracks.append(parse_track_filename(file_path))
        except ValueError as exc:
            parse_failures.append(str(exc))

    run_command(
        ssh_base + [f"mkdir -p {remote_quote(remote_dir)}"],
        dry_run=args.dry_run,
    )

    uploaded_count = 0
    skipped_count = 0
    db_count = 0
    upload_failures: list[str] = []

    if not args.dry_run:
        init_database()
        reference_track_service.set_db_session_factory(get_session_factory())
        reference_track_service.USE_DB = True

    for track in parsed_tracks:
        remote_path = posixpath.join(remote_dir.rstrip("/"), track.file_path.name)
        audio_url = build_reference_audio_url(track.file_path.name)
        try:
            if remote_file_exists(ssh_base, remote_path, dry_run=args.dry_run):
                skipped_count += 1
                print(f"SKIP remote file exists: {track.file_path.name}")
                continue

            run_command(
                scp_base + [str(track.file_path), f"{ssh_user}@{host}:{remote_path}"],
                dry_run=args.dry_run,
            )
            uploaded_count += 1

            if args.dry_run:
                print(
                    f"DRY-RUN upsert reference_track song_name={track.song_name!r} "
                    f"artist_name={track.artist_name!r} audio_url={audio_url!r}"
                )
            else:
                reference_track_service.upsert_reference_track(
                    song_name=track.song_name,
                    artist_name=track.artist_name,
                    audio_url=audio_url,
                )
                db_count += 1
        except Exception as exc:
            upload_failures.append(f"{track.file_path.name}: {exc}")

    print("Summary")
    print(f"  total_files={len(local_files)}")
    print(f"  parsed_success={len(parsed_tracks)}")
    print(f"  parse_failures={len(parse_failures)}")
    print(f"  uploaded={uploaded_count}")
    print(f"  skipped={skipped_count}")
    print(f"  db_upserts={db_count if not args.dry_run else len(parsed_tracks) - skipped_count - len(upload_failures)}")
    print(f"  upload_failures={len(upload_failures)}")

    for message in parse_failures:
        print(f"PARSE-FAIL {message}")
    for message in upload_failures:
        print(f"UPLOAD-FAIL {message}")

    return 0 if not parse_failures and not upload_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
