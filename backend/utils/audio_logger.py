"""Audio logging helpers for in-memory and on-disk debugging."""

from __future__ import annotations

import io
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import soundfile as sf

from backend.config.settings import settings
from backend.core.pitch.audio_utils import estimate_duration_from_bytes


AUDIO_LOGS: list[dict[str, Any]] = []
DEFAULT_AUDIO_LOG_FILE = settings.storage_dir / "logs" / "audio_logs.jsonl"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def inspect_audio_bytes(audio_bytes: bytes, file_name: str = "audio") -> dict[str, Any]:
    """Inspect raw audio bytes and return debug-friendly metadata."""
    # Import at top of function to avoid UnboundLocalError
    from pathlib import Path as PathlibPath
    import tempfile
    
    byte_size = len(audio_bytes)
    suffix = PathlibPath(file_name).suffix.lower().removeprefix(".") or None
    metadata: dict[str, Any] = {
        "byte_size": byte_size,
        "file_extension": suffix,
        "sample_rate": None,
        "duration": None,
        "channels": None,
        "frame_count": None,
        "audio_format": suffix,
        "subtype": None,
    }

    if not audio_bytes:
        metadata["duration"] = 0.0
        return metadata

    temp_path = None
    try:
        # Write bytes to temporary file for soundfile inspection
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name
            f.write(audio_bytes)
            f.flush()  # Ensure data is written to disk
        
        # Read file info after temp file is created
        info = sf.info(temp_path)
        
        duration = round(float(info.frames) / info.samplerate, 4) if info.samplerate else 0.0
        metadata.update(
            {
                "sample_rate": int(info.samplerate) if info.samplerate else None,
                "duration": duration,
                "channels": int(info.channels) if info.channels else None,
                "frame_count": int(info.frames) if info.frames else None,
                "audio_format": (info.format or suffix or "unknown").lower(),
                "subtype": info.subtype,
            }
        )
    except Exception:
        metadata["duration"] = estimate_duration_from_bytes(audio_bytes)
    finally:
        # Clean up temporary file
        if temp_path and PathlibPath(temp_path).exists():
            PathlibPath(temp_path).unlink(missing_ok=True)
    
    return metadata


def build_audio_log_payload(
    *,
    file_name: str,
    sample_rate: int | None = None,
    duration: float | None = None,
    analysis_id: str | None = None,
    params: Optional[dict[str, Any]] = None,
    audio_bytes: bytes | None = None,
    source: str = "system",
    stage: str = "general",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a normalized audio log payload with derived metadata."""
    params = deepcopy(params or {})
    extra = deepcopy(extra or {})

    inspected = inspect_audio_bytes(audio_bytes or b"", file_name=file_name)
    resolved_sample_rate = sample_rate or inspected.get("sample_rate")
    resolved_duration = _safe_float(duration)
    if resolved_duration is None:
        resolved_duration = _safe_float(inspected.get("duration")) or 0.0

    payload: dict[str, Any] = {
        "file_name": file_name,
        "analysis_id": analysis_id,
        "sample_rate": int(resolved_sample_rate) if resolved_sample_rate else None,
        "duration": round(float(resolved_duration), 4),
        "channels": inspected.get("channels"),
        "frame_count": inspected.get("frame_count"),
        "byte_size": inspected.get("byte_size"),
        "audio_format": inspected.get("audio_format"),
        "file_extension": inspected.get("file_extension"),
        "subtype": inspected.get("subtype"),
        "source": source,
        "stage": stage,
        "params": params,
        **extra,
    }
    return payload


def _persist_audio_log(entry: dict[str, Any], log_file: Path | None = None) -> None:
    log_file = log_file or DEFAULT_AUDIO_LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_audio_log(payload: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
    """Record a normalized audio log entry."""
    entry = {
        "log_id": f"log_{uuid4().hex[:8]}",
        "created_at": _utc_timestamp(),
        **payload,
    }
    AUDIO_LOGS.append(deepcopy(entry))
    if persist:
        _persist_audio_log(entry)
    return entry


def record_audio_processing_log(
    *,
    file_name: str,
    audio_bytes: bytes | None = None,
    sample_rate: int | None = None,
    duration: float | None = None,
    analysis_id: str | None = None,
    params: Optional[dict[str, Any]] = None,
    source: str = "system",
    stage: str = "general",
    extra: Optional[dict[str, Any]] = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Build and store an audio log entry for processing/debug flows."""
    payload = build_audio_log_payload(
        file_name=file_name,
        audio_bytes=audio_bytes,
        sample_rate=sample_rate,
        duration=duration,
        analysis_id=analysis_id,
        params=params,
        source=source,
        stage=stage,
        extra=extra,
    )
    return record_audio_log(payload, persist=persist)


def get_audio_logs(analysis_id: str | None = None, stage: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve audio logs from in-memory cache, optionally filtered by analysis_id or stage."""
    logs = AUDIO_LOGS
    if analysis_id:
        logs = [log for log in logs if log.get("analysis_id") == analysis_id]
    if stage:
        logs = [log for log in logs if log.get("stage") == stage]
    return logs[-limit:] if limit else logs


def read_audio_logs_from_file(log_file: Path | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Read audio logs from jsonl file with optional limit."""
    log_file = log_file or DEFAULT_AUDIO_LOG_FILE
    if not log_file.exists():
        return []
    
    logs = []
    try:
        with log_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    logs.append(json.loads(line))
    except Exception:
        return []
    
    return logs[-limit:] if limit else logs


def clear_audio_logs() -> None:
    """Clear in-memory audio logs (for testing)."""
    global AUDIO_LOGS
    AUDIO_LOGS = []
