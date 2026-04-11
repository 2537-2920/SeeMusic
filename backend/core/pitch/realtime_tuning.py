"""Realtime tuning stub."""

from __future__ import annotations

from backend.core.score.note_mapping import frequency_to_note


def analyze_audio_frame(pcm: bytes, sample_rate: int, reference_frequency: float | None = None) -> dict:
    frequency = reference_frequency or 440.0
    cents_offset = 0.0 if reference_frequency is None else round((frequency - reference_frequency) / max(reference_frequency, 1) * 1200, 2)
    return {
        "time": 0.0,
        "frequency": round(frequency, 2),
        "note": frequency_to_note(frequency),
        "cents_offset": cents_offset,
        "confidence": 0.9,
    }

