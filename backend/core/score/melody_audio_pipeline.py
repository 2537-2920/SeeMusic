"""Shared audio-to-melody extraction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from backend.core.score.key_detection import (
    analyze_key_signature,
    normalize_key_signature_text,
    respell_pitch_sequence_for_key,
)

DEFAULT_SEPARATION_SAMPLE_RATE = 44100
DEFAULT_TRACK_PRIORITY = {
    "vocal": 3.0,
    "vocals": 3.0,
    "lead_vocal": 3.0,
    "guitar": 2.0,
    "piano": 1.7,
    "other": 1.1,
    "accompaniment": 0.5,
    "bass": 0.0,
    "drums": -0.4,
}
MIN_RELIABLE_BEAT_CONFIDENCE = 0.05
MIN_RELIABLE_BEAT_COUNT = 3


def _track_priority(name: str | None) -> float:
    normalized = str(name or "").strip().lower()
    return DEFAULT_TRACK_PRIORITY.get(normalized, 0.25)


def _read_track_audio_bytes(track: dict[str, Any]) -> bytes:
    file_path = Path(str(track.get("file_path") or "").strip())
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Separated track file not found: {file_path}")
    return file_path.read_bytes()


def sequence_quality(pitch_sequence: list[dict[str, Any]]) -> dict[str, float]:
    total_points = len(pitch_sequence)
    voiced_points = [
        point
        for point in pitch_sequence
        if float(point.get("frequency") or 0.0) > 0.0 and bool(point.get("voiced", True))
    ]
    voiced_count = len(voiced_points)
    voiced_ratio = voiced_count / total_points if total_points else 0.0
    average_confidence = (
        sum(float(point.get("confidence") or 0.0) for point in voiced_points) / voiced_count
        if voiced_count
        else 0.0
    )
    average_frequency = (
        sum(float(point.get("frequency") or 0.0) for point in voiced_points) / voiced_count
        if voiced_count
        else 0.0
    )
    return {
        "point_count": float(total_points),
        "voiced_count": float(voiced_count),
        "voiced_ratio": round(voiced_ratio, 4),
        "average_confidence": round(average_confidence, 4),
        "average_frequency": round(average_frequency, 2),
    }


def _track_quality_score(track_name: str, metrics: dict[str, float]) -> float:
    voiced_ratio = float(metrics.get("voiced_ratio") or 0.0)
    average_confidence = float(metrics.get("average_confidence") or 0.0)
    voiced_count = float(metrics.get("voiced_count") or 0.0)
    return (
        _track_priority(track_name)
        + voiced_ratio * 3.4
        + average_confidence * 1.8
        + min(voiced_count / 24.0, 1.0)
    )


def pick_best_melody_track(
    tracks: list[dict[str, Any]],
    *,
    sample_rate: int,
    frame_ms: int,
    hop_ms: int,
    algorithm: str,
    detect_pitch_sequence_fn: Callable[..., list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    evaluations: list[dict[str, Any]] = []
    warnings: list[str] = []
    best_choice: dict[str, Any] | None = None

    for track in tracks:
        track_name = str(track.get("name") or "track")
        try:
            track_audio = _read_track_audio_bytes(track)
            pitch_sequence = detect_pitch_sequence_fn(
                file_name=f"{track_name}.wav",
                sample_rate=sample_rate,
                frame_ms=frame_ms,
                hop_ms=hop_ms,
                algorithm=algorithm,
                duration=float(track.get("duration") or 0.0) or None,
                audio_bytes=track_audio,
            )
        except Exception as exc:
            warnings.append(f"{track_name} 轨旋律识别失败：{exc}")
            continue

        metrics = sequence_quality(pitch_sequence)
        evaluation = {
            "name": track_name,
            "file_name": track.get("file_name"),
            "duration": float(track.get("duration") or 0.0),
            "metrics": metrics,
            "score": round(_track_quality_score(track_name, metrics), 4),
            "pitch_sequence": pitch_sequence,
        }
        evaluations.append(evaluation)

        if metrics["voiced_count"] <= 0:
            continue
        if best_choice is None or float(evaluation["score"]) > float(best_choice["score"]):
            best_choice = evaluation

    evaluations.sort(key=lambda item: float(item["score"]), reverse=True)
    return best_choice, evaluations, warnings


def resolve_tempo_detection(
    beat_result: dict[str, Any] | None,
    *,
    fallback_tempo: int,
) -> dict[str, Any]:
    result = dict(beat_result or {})
    detected_tempo = int(round(float(result.get("bpm", 0) or 0))) or None
    confidence = float(result.get("beat_quality", {}).get("confidence", 0.0) or 0.0)
    beat_count = int(result.get("num_beats") or len(result.get("beat_times") or []))
    resolved_tempo = int(fallback_tempo or 120)
    used_detected_tempo = False
    fallback_reason = ""

    if (
        detected_tempo
        and confidence >= MIN_RELIABLE_BEAT_CONFIDENCE
        and beat_count >= MIN_RELIABLE_BEAT_COUNT
    ):
        resolved_tempo = detected_tempo
        used_detected_tempo = True
    elif not detected_tempo:
        fallback_reason = "missing_detected_tempo"
    elif confidence < MIN_RELIABLE_BEAT_CONFIDENCE:
        fallback_reason = "low_confidence"
    else:
        fallback_reason = "insufficient_beats"

    return {
        "detected_tempo": detected_tempo,
        "resolved_tempo": resolved_tempo,
        "used_detected_tempo": used_detected_tempo,
        "confidence": round(confidence, 4),
        "beat_count": beat_count,
        "fallback_reason": fallback_reason or None,
    }


def _disabled_tempo_detection(*, fallback_tempo: int) -> dict[str, Any]:
    return {
        "detected_tempo": None,
        "resolved_tempo": int(fallback_tempo or 120),
        "used_detected_tempo": False,
        "confidence": 0.0,
        "beat_count": 0,
        "fallback_reason": "disabled",
    }


def extract_melody_from_audio(
    *,
    file_name: str,
    audio_bytes: bytes,
    analysis_id: str,
    fallback_tempo: int,
    time_signature: str,
    sample_rate: int,
    frame_ms: int,
    hop_ms: int,
    algorithm: str,
    separation_model: str,
    separation_stems: int,
    detect_pitch_sequence_fn: Callable[..., list[dict[str, Any]]],
    separate_tracks_fn: Callable[..., dict[str, Any]],
    detect_beats_fn: Callable[..., dict[str, Any]] | None = None,
    bpm_hint: int | None = None,
    beat_sensitivity: float = 0.5,
    enable_beat_detection: bool = True,
    key_hint: str | None = None,
    stage_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    beat_result: dict[str, Any] | None = None
    if enable_beat_detection and detect_beats_fn is not None:
        beat_result = detect_beats_fn(
            file_name,
            bpm_hint=float(bpm_hint) if bpm_hint is not None else None,
            sensitivity=beat_sensitivity,
            audio_bytes=audio_bytes,
        )
        tempo_detection = resolve_tempo_detection(beat_result, fallback_tempo=fallback_tempo)
    else:
        tempo_detection = _disabled_tempo_detection(fallback_tempo=fallback_tempo)

    if stage_callback is not None:
        stage_callback("separation")
    separation_result = separate_tracks_fn(
        file_name,
        model=separation_model,
        stems=separation_stems,
        audio_bytes=audio_bytes,
        sample_rate=max(DEFAULT_SEPARATION_SAMPLE_RATE, int(sample_rate or 16000)),
    )
    warnings.extend(list(separation_result.get("warnings") or []))

    selected_track: dict[str, Any] | None = None
    track_evaluations: list[dict[str, Any]] = []
    raw_pitch_sequence: list[dict[str, Any]] = []
    pitch_stage_marked = False

    if separation_result.get("status") == "completed":
        if stage_callback is not None:
            stage_callback("pitch_detection")
            pitch_stage_marked = True
        selected_track, track_evaluations, evaluation_warnings = pick_best_melody_track(
            list(separation_result.get("tracks") or []),
            sample_rate=sample_rate,
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            detect_pitch_sequence_fn=detect_pitch_sequence_fn,
        )
        warnings.extend(evaluation_warnings)
        if selected_track is not None:
            raw_pitch_sequence = list(selected_track["pitch_sequence"])

    if not raw_pitch_sequence:
        warnings.append("未能从分离轨中稳定提取主旋律，已回退为直接对混音进行旋律识别。")
        if stage_callback is not None and not pitch_stage_marked:
            stage_callback("pitch_detection")
        raw_pitch_sequence = detect_pitch_sequence_fn(
            file_name=file_name,
            sample_rate=sample_rate,
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            audio_bytes=audio_bytes,
        )

    if not raw_pitch_sequence:
        raise ValueError("未能从音频中检测到可用旋律。")

    key_detection = analyze_key_signature(raw_pitch_sequence)
    preferred_key = str(key_hint or "").strip() or key_detection["key_signature"]
    resolved_key = normalize_key_signature_text(preferred_key, default=key_detection["key_signature"] or "C")
    respelled_sequence = respell_pitch_sequence_for_key(raw_pitch_sequence, resolved_key)

    if selected_track is not None:
        chosen_track_payload = {
            "name": selected_track["name"],
            "file_name": selected_track.get("file_name"),
            "duration": selected_track.get("duration"),
            **selected_track["metrics"],
            "selection_score": selected_track["score"],
            "source": "separated_track",
        }
    else:
        chosen_track_payload = {
            "name": "mix",
            "file_name": file_name,
            "duration": None,
            **sequence_quality(raw_pitch_sequence),
            "selection_score": 0.0,
            "source": "mixed_audio_fallback",
        }

    return {
        "analysis_id": analysis_id,
        "tempo": int(tempo_detection["resolved_tempo"]),
        "time_signature": time_signature,
        "raw_pitch_sequence": raw_pitch_sequence,
        "pitch_sequence": respelled_sequence,
        "detected_key_signature": key_detection["key_signature"],
        "resolved_key_signature": resolved_key,
        "key_detection": key_detection,
        "beat_result": beat_result,
        "tempo_detection": tempo_detection,
        "melody_track": chosen_track_payload,
        "melody_track_candidates": [
            {
                "name": item["name"],
                "file_name": item.get("file_name"),
                "duration": item.get("duration"),
                **item["metrics"],
                "selection_score": item["score"],
            }
            for item in track_evaluations
        ],
        "separation": separation_result,
        "warnings": warnings,
        "pipeline": {
            "separation_enabled": True,
            "beat_detection_enabled": bool(enable_beat_detection and detect_beats_fn is not None),
            "pitch_source": str(chosen_track_payload.get("source") or "unknown"),
            "separation_model": separation_model,
            "separation_stems": separation_stems,
            "pitch_algorithm": algorithm,
        },
    }
