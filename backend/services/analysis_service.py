"""End-to-end audio analysis orchestration."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.pitch.audio_utils import infer_audio_metadata
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.rhythm.beat_detection import detect_beats
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.utils.audio_logger import record_audio_log
from backend.utils.data_visualizer import build_pitch_curve


def analyze_audio(file_name: str, audio_bytes: bytes, sample_rate: int | None = None) -> dict[str, Any]:
    metadata = infer_audio_metadata(file_name, sample_rate=sample_rate, duration=None)
    pitch_sequence = detect_pitch_sequence(
        file_name=file_name,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        audio_bytes=audio_bytes,
    )
    beat_result = detect_beats(file_name, audio_bytes=audio_bytes)
    score = build_score_from_pitch_sequence(pitch_sequence)
    pitch_curve = build_pitch_curve(pitch_sequence, pitch_sequence)
    log_entry = record_audio_log(
        {
            "file_name": file_name,
            "sample_rate": metadata["sample_rate"],
            "duration": metadata["duration"],
            "analysis_id": metadata["analysis_id"],
        }
    )
    return {
        "analysis_id": metadata["analysis_id"],
        "pitch_sequence": pitch_sequence,
        "beat_result": beat_result,
        "score": score,
        "pitch_curve": pitch_curve,
        "log": log_entry,
    }

