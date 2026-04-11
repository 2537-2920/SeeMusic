"""Audio helpers for pitch analysis."""

from __future__ import annotations

from uuid import uuid4


def infer_audio_metadata(file_name: str, sample_rate: int | None = None, duration: float | None = None) -> dict:
    return {
        "analysis_id": f"an_{uuid4().hex[:12]}",
        "file_name": file_name,
        "sample_rate": sample_rate or 16000,
        "duration": duration or 60.0,
    }


def estimate_duration_from_bytes(audio_bytes: bytes, sample_rate: int = 16000) -> float:
    if not audio_bytes:
        return 0.0
    return round(len(audio_bytes) / max(sample_rate * 2, 1), 2)

