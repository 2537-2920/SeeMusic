"""Audio-to-guzheng jianpu pipeline."""

from __future__ import annotations

from typing import Any

from backend.core.guzheng.notation import generate_guzheng_score_from_pitch_sequence
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.rhythm.beat_detection import detect_beats
from backend.core.score.melody_audio_pipeline import extract_melody_from_audio
from backend.core.separation.multi_track_separation import separate_tracks


def generate_guzheng_score_from_audio(
    *,
    file_name: str,
    audio_bytes: bytes,
    analysis_id: str,
    tempo: int,
    time_signature: str,
    title: str | None = None,
    key: str | None = None,
    style: str = "traditional",
    sample_rate: int = 16000,
    frame_ms: int = 20,
    hop_ms: int = 10,
    algorithm: str = "yin",
    bpm_hint: int | None = None,
    beat_sensitivity: float = 0.5,
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
        detect_beats_fn=detect_beats,
        bpm_hint=bpm_hint,
        beat_sensitivity=beat_sensitivity,
        enable_beat_detection=True,
        key_hint=key,
    )

    score = generate_guzheng_score_from_pitch_sequence(
        pitch_sequence=list(extraction["pitch_sequence"]),
        tempo=int(extraction["tempo"]),
        time_signature=time_signature,
        key=extraction["resolved_key_signature"],
        title=title or "Untitled Guzheng Chart",
        style=style,
    )

    return {
        **score,
        "analysis_id": analysis_id,
        "pitch_sequence": list(extraction["pitch_sequence"]),
        "detected_key_signature": extraction["detected_key_signature"],
        "key_detection": extraction["key_detection"],
        "beat_result": extraction["beat_result"],
        "tempo_detection": extraction["tempo_detection"],
        "melody_track": extraction["melody_track"],
        "melody_track_candidates": extraction["melody_track_candidates"],
        "separation": extraction["separation"],
        "warnings": extraction["warnings"],
        "pipeline": extraction["pipeline"],
    }
