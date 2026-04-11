"""Beat detection stubs."""

from __future__ import annotations


def detect_beats(
    file_name: str,
    bpm_hint: int | None = None,
    sensitivity: float = 0.5,
    audio_bytes: bytes | None = None,
) -> dict:
    bpm = float(bpm_hint or 120)
    beat_times = [round(index * 0.5, 2) for index in range(8)]
    return {"bpm": bpm, "beat_times": beat_times, "sensitivity": sensitivity, "file_name": file_name}

