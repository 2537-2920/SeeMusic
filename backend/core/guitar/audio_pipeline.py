"""Audio-to-guitar lead sheet pipeline."""

from __future__ import annotations

from typing import Any

from backend.core.guitar.lead_sheet import generate_guitar_lead_sheet
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.score.melody_audio_pipeline import (
    DEFAULT_SEPARATION_SAMPLE_RATE,
    extract_melody_from_audio,
    pick_best_melody_track,
    sequence_quality,
)
from backend.core.separation.multi_track_separation import separate_tracks


def generate_guitar_lead_sheet_from_audio(
    *,
    file_name: str,
    audio_bytes: bytes,
    analysis_id: str,
    tempo: int,
    time_signature: str,
    style: str,
    title: str | None = None,
    key: str | None = None,
    sample_rate: int = 16000,
    frame_ms: int = 20,
    hop_ms: int = 10,
    algorithm: str = "yin",
    separation_model: str = "demucs",
    separation_stems: int = 2,
) -> dict[str, Any]:
    extraction = extract_melody_from_audio(
        file_name=file_name,
        audio_bytes=audio_bytes,
        analysis_id=analysis_id,
        fallback_tempo=tempo,
        time_signature=time_signature,
        sample_rate=sample_rate,
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        algorithm=algorithm,
        separation_model=separation_model,
        separation_stems=separation_stems,
        detect_pitch_sequence_fn=detect_pitch_sequence,
        separate_tracks_fn=separate_tracks,
        enable_beat_detection=False,
        key_hint=key,
    )

    lead_sheet = generate_guitar_lead_sheet(
        key=extraction["resolved_key_signature"],
        tempo=tempo,
        time_signature=time_signature,
        style=style,
        melody=list(extraction["pitch_sequence"]),
        title=title or "Untitled Guitar Lead Sheet",
    )

    return {
        **lead_sheet,
        "analysis_id": analysis_id,
        "pitch_sequence": list(extraction["raw_pitch_sequence"]),
        "detected_key_signature": extraction["detected_key_signature"],
        "key_detection": extraction["key_detection"],
        "melody_track": extraction["melody_track"],
        "melody_track_candidates": extraction["melody_track_candidates"],
        "separation": extraction["separation"],
        "warnings": extraction["warnings"],
        "pipeline": extraction["pipeline"],
    }


__all__ = [
    "DEFAULT_SEPARATION_SAMPLE_RATE",
    "generate_guitar_lead_sheet_from_audio",
    "pick_best_melody_track",
    "sequence_quality",
]
