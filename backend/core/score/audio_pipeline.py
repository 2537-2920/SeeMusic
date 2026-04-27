"""Audio-to-score helpers for piano melody extraction."""

from __future__ import annotations

from typing import Any, Callable

from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.rhythm.beat_detection import detect_beats
from backend.core.score.melody_audio_pipeline import (
    DEFAULT_SEPARATION_SAMPLE_RATE,
    MIN_RELIABLE_BEAT_CONFIDENCE,
    MIN_RELIABLE_BEAT_COUNT,
    extract_melody_from_audio,
    pick_best_melody_track,
    resolve_tempo_detection,
    sequence_quality,
)
from backend.core.separation.multi_track_separation import separate_tracks


def prepare_piano_score_from_audio(
    *,
    file_name: str,
    audio_bytes: bytes,
    analysis_id: str,
    fallback_tempo: int,
    time_signature: str,
    sample_rate: int = 16000,
    frame_ms: int = 20,
    hop_ms: int = 10,
    algorithm: str = "yin",
    bpm_hint: int | None = None,
    beat_sensitivity: float = 0.5,
    separation_model: str = "demucs",
    separation_stems: int = 2,
    stage_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    extraction = extract_melody_from_audio(
        file_name=file_name,
        audio_bytes=audio_bytes,
        analysis_id=analysis_id,
        fallback_tempo=fallback_tempo,
        time_signature=time_signature,
        sample_rate=sample_rate,
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        algorithm=algorithm,
        separation_model=separation_model,
        separation_stems=separation_stems,
        detect_pitch_sequence_fn=detect_pitch_sequence,
        separate_tracks_fn=separate_tracks,
        detect_beats_fn=detect_beats,
        bpm_hint=bpm_hint,
        beat_sensitivity=beat_sensitivity,
        enable_beat_detection=True,
        stage_callback=stage_callback,
    )

    return {
        "analysis_id": analysis_id,
        "tempo": int(extraction["tempo"]),
        "time_signature": time_signature,
        "pitch_sequence": list(extraction["pitch_sequence"]),
        "detected_key_signature": extraction["resolved_key_signature"],
        "key_detection": extraction["key_detection"],
        "beat_result": extraction["beat_result"],
        "tempo_detection": extraction["tempo_detection"],
        "melody_track": extraction["melody_track"],
        "melody_track_candidates": extraction["melody_track_candidates"],
        "separation": extraction["separation"],
        "warnings": extraction["warnings"],
        "pipeline": extraction["pipeline"],
    }


__all__ = [
    "DEFAULT_SEPARATION_SAMPLE_RATE",
    "MIN_RELIABLE_BEAT_CONFIDENCE",
    "MIN_RELIABLE_BEAT_COUNT",
    "pick_best_melody_track",
    "prepare_piano_score_from_audio",
    "resolve_tempo_detection",
    "sequence_quality",
]
