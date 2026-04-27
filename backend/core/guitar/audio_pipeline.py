"""Audio-to-guitar lead sheet pipeline."""

from __future__ import annotations

from typing import Any

from backend.core.guitar.lead_sheet import generate_guitar_lead_sheet, generate_guitar_lead_sheet_from_musicxml
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
    lyrics_payload: dict[str, Any] | None = None,
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

    lyrics_import: dict[str, Any] | None = None
    if lyrics_payload is not None:
        from backend.core.score.sheet_extraction import build_score_from_pitch_sequence

        temporary_score = build_score_from_pitch_sequence(
            list(extraction["pitch_sequence"]),
            tempo=tempo,
            time_signature=time_signature,
            key_signature=extraction["resolved_key_signature"],
            title=title or "Untitled Guitar Lead Sheet",
            auto_detect_key=False,
            arrangement_mode="melody",
            lyrics_payload=lyrics_payload,
        )
        lead_sheet = generate_guitar_lead_sheet_from_musicxml(
            musicxml=temporary_score["musicxml"],
            key=extraction["resolved_key_signature"],
            tempo=tempo,
            time_signature=time_signature,
            style=style,
            title=title or "Untitled Guitar Lead Sheet",
        )
        lyrics_import = temporary_score.get("lyrics_import")
    else:
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
        "melody_pitch_sequence": list(extraction["pitch_sequence"]),
        "detected_key_signature": extraction["detected_key_signature"],
        "key_detection": extraction["key_detection"],
        "melody_track": extraction["melody_track"],
        "melody_track_candidates": extraction["melody_track_candidates"],
        "separation": extraction["separation"],
        "warnings": list(
            dict.fromkeys(
                list(extraction.get("warnings") or [])
                + list((lyrics_import or {}).get("warnings") or [])
            )
        ),
        "pipeline": extraction["pipeline"],
        "lyrics_import": lyrics_import,
    }


__all__ = [
    "DEFAULT_SEPARATION_SAMPLE_RATE",
    "generate_guitar_lead_sheet_from_audio",
    "pick_best_melody_track",
    "sequence_quality",
]
