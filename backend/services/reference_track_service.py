"""Reference track persistence and lookup helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from backend.config.settings import settings
from backend.db.models import ReferenceTrack


USE_DB: bool = True
_session_factory = None
STORAGE_PREFIX = "/storage/"
DEFAULT_ARTIST_NAME = "未知歌手"


def set_db_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


def _session_scope():
    if _session_factory is None:
        raise RuntimeError("reference track DB session factory is not configured")
    return _session_factory()


def normalize_artist_name(artist_name: str | None) -> str:
    cleaned = str(artist_name or "").strip()
    return cleaned or DEFAULT_ARTIST_NAME


def build_ref_id(song_name: str, artist_name: str) -> str:
    base = f"{song_name.strip()}-{normalize_artist_name(artist_name)}"
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", base).strip("-").lower()
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    prefix = slug[:48] if slug else "reference-track"
    return f"{prefix}-{digest}"


def build_reference_audio_url(file_name: str) -> str:
    safe_name = Path(file_name).name
    if not safe_name:
        raise ValueError("reference audio file_name is required")
    return f"{STORAGE_PREFIX}reference_audio/{safe_name}"


def resolve_storage_url_path(file_url: str | None) -> Path:
    if not file_url:
        raise FileNotFoundError("reference audio url is empty")

    relative_path = file_url
    if relative_path.startswith(STORAGE_PREFIX):
        relative_path = relative_path[len(STORAGE_PREFIX) :]
    resolved = (settings.storage_dir / relative_path.lstrip("/\\")).resolve()
    storage_root = settings.storage_dir.resolve()
    if resolved != storage_root and storage_root not in resolved.parents:
        raise FileNotFoundError("reference audio path is outside the storage directory")
    return resolved


def serialize_reference_track(track: ReferenceTrack) -> dict[str, Any]:
    return {
        "id": int(track.id),
        "ref_id": str(track.ref_id),
        "song_name": str(track.song_name),
        "artist_name": str(track.artist_name),
        "audio_url": str(track.audio_url),
        "is_active": bool(track.is_active),
    }


def get_reference_track_by_ref_id(ref_id: str) -> dict[str, Any] | None:
    if not USE_DB or not ref_id:
        return None
    session = _session_scope()
    try:
        statement = select(ReferenceTrack).where(
            ReferenceTrack.ref_id == ref_id,
            ReferenceTrack.is_active.is_(True),
        )
        track = session.execute(statement).scalar_one_or_none()
        return serialize_reference_track(track) if track is not None else None
    finally:
        session.close()


def search_reference_tracks(keyword: str, *, limit: int = 20) -> list[dict[str, Any]]:
    if not USE_DB:
        return []
    normalized = str(keyword or "").strip()
    if not normalized:
        return []
    session = _session_scope()
    try:
        statement = (
            select(ReferenceTrack)
            .where(ReferenceTrack.is_active.is_(True))
            .where(
                (func.lower(ReferenceTrack.song_name).contains(normalized.lower()))
                | (func.lower(ReferenceTrack.artist_name).contains(normalized.lower()))
            )
            .order_by(ReferenceTrack.song_name.asc(), ReferenceTrack.artist_name.asc())
            .limit(max(1, min(limit, 50)))
        )
        return [serialize_reference_track(track) for track in session.execute(statement).scalars().all()]
    finally:
        session.close()


def upsert_reference_track(*, song_name: str, artist_name: str | None, audio_url: str) -> dict[str, Any]:
    if not USE_DB:
        raise RuntimeError("reference track DB mode is disabled")

    normalized_song_name = str(song_name or "").strip()
    if not normalized_song_name:
        raise ValueError("song_name is required")
    normalized_artist_name = normalize_artist_name(artist_name)

    session = _session_scope()
    try:
        statement = select(ReferenceTrack).where(
            ReferenceTrack.song_name == normalized_song_name,
            ReferenceTrack.artist_name == normalized_artist_name,
        )
        existing = session.execute(statement).scalar_one_or_none()
        if existing is None:
            track = ReferenceTrack(
                ref_id=build_ref_id(normalized_song_name, normalized_artist_name),
                song_name=normalized_song_name,
                artist_name=normalized_artist_name,
                audio_url=audio_url,
                is_active=True,
            )
            session.add(track)
        else:
            existing.audio_url = audio_url
            existing.is_active = True
            session.add(existing)
            track = existing
        session.commit()
        session.refresh(track)
        return serialize_reference_track(track)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
