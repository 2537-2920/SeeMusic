"""Pitch detection stubs."""

from __future__ import annotations

from math import sin
from typing import Iterable

from backend.core.score.note_mapping import frequency_to_note


def detect_pitch_sequence(
    file_name: str,
    sample_rate: int | None = None,
    frame_ms: int = 20,
    hop_ms: int = 10,
    algorithm: str = "yin",
    duration: float | None = None,
    audio_bytes: bytes | None = None,
) -> list[dict]:
    sample_rate = sample_rate or 16000
    duration = duration or max(round((len(audio_bytes) / max(sample_rate * 2, 1)) if audio_bytes else 4.0, 2), 1.0)
    points: list[dict] = []
    total_frames = max(int(duration * 1000 / max(hop_ms, 1)), 1)
    for index in range(min(total_frames, 12)):
        time_point = round(index * hop_ms / 1000.0, 2)
        frequency = round(440.0 + sin(index / 3.0) * 6.0, 2)
        points.append(
            {
                "time": time_point,
                "frequency": frequency,
                "note": frequency_to_note(frequency),
                "confidence": round(0.95 - index * 0.01, 2),
                "algorithm": algorithm,
            }
        )
    return points

