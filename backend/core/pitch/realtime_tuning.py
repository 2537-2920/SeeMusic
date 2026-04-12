"""Realtime tuning logic for microphone audio frames."""

from __future__ import annotations

import base64
import math
from typing import Any

from backend.core.pitch.pitch_detection import audio_bytes_to_samples, detect_single_pitch
from backend.core.score.note_mapping import frequency_to_midi, frequency_to_note, midi_to_frequency


def _decode_possible_base64(pcm: bytes) -> bytes:
    """Accept raw PCM bytes or the base64 text used by the WebSocket API."""

    if not pcm:
        return b""
    try:
        text = pcm.decode("ascii").strip()
    except UnicodeDecodeError:
        return pcm
    if not text or len(text) % 4 != 0:
        return pcm
    try:
        decoded = base64.b64decode(text, validate=True)
    except ValueError:
        return pcm
    return decoded or pcm


def cents_between(frequency: float, reference_frequency: float) -> float:
    if frequency <= 0 or reference_frequency <= 0:
        return 0.0
    return round(1200 * math.log2(frequency / reference_frequency), 2)


def classify_tuning(cents_offset: float, confidence: float) -> str:
    if confidence <= 0:
        return "silence"
    if abs(cents_offset) <= 5:
        return "in_tune"
    if cents_offset > 5:
        return "sharp"
    return "flat"


def analyze_audio_frame(
    pcm: bytes,
    sample_rate: int,
    reference_frequency: float | None = None,
    timestamp: float = 0.0,
    algorithm: str = "yin",
) -> dict[str, Any]:
    """Analyze a realtime PCM frame and return frontend WebSocket payload data.

    The returned shape mirrors `API.md`: `frequency`, `note`, `cents_offset`,
    and `confidence` are always present. Additional status fields let the
    frontend show tuner direction and silence/invalid-input states.
    """

    decoded_pcm = _decode_possible_base64(pcm)
    samples, actual_rate = audio_bytes_to_samples(decoded_pcm, sample_rate)
    detected = detect_single_pitch(samples, actual_rate, algorithm=algorithm)

    frequency = float(detected["frequency"])
    confidence = float(detected["confidence"])

    # Preserve the existing API behavior for silent calibration frames: if a
    # reference is provided and no voice is detected, report the reference note.
    if frequency <= 0 and reference_frequency:
        frequency = float(reference_frequency)
        confidence = 0.0 if decoded_pcm.strip(b"\x00") else 0.9

    note = frequency_to_note(frequency) if frequency > 0 else "Rest"
    nearest_midi = frequency_to_midi(frequency) if frequency > 0 else None
    nearest_frequency = reference_frequency or midi_to_frequency(nearest_midi)
    cents_offset = cents_between(frequency, nearest_frequency) if nearest_frequency else 0.0
    status = classify_tuning(cents_offset, confidence if frequency > 0 else 0.0)

    return {
        "time": round(float(timestamp), 3),
        "frequency": round(frequency, 2),
        "note": note,
        "target_frequency": round(float(nearest_frequency or 0.0), 2),
        "cents_offset": cents_offset,
        "confidence": round(confidence, 2),
        "status": status,
        "is_in_tune": status == "in_tune",
        "algorithm": algorithm,
        "voiced": bool(detected.get("voiced", False)) or bool(reference_frequency and frequency > 0),
        "rms": detected.get("rms", 0.0),
        "zcr": detected.get("zcr", 0.0),
    }


def evaluate_realtime_accuracy(
    frames: list[bytes],
    sample_rate: int,
    expected_frequencies: list[float],
    tolerance_cents: float = 25.0,
) -> dict[str, Any]:
    """Score realtime pitch accuracy across different audio input frames."""

    total = min(len(frames), len(expected_frequencies))
    if total == 0:
        return {"accuracy": 0.0, "total": 0, "passed": 0, "results": []}

    results: list[dict[str, Any]] = []
    passed = 0
    for index, (frame, expected) in enumerate(zip(frames, expected_frequencies)):
        result = analyze_audio_frame(frame, sample_rate, reference_frequency=expected, timestamp=index)
        within_tolerance = abs(result["cents_offset"]) <= tolerance_cents
        if within_tolerance:
            passed += 1
        results.append({**result, "expected_frequency": expected, "within_tolerance": within_tolerance})

    return {
        "accuracy": round(passed / total * 100, 2),
        "total": total,
        "passed": passed,
        "tolerance_cents": tolerance_cents,
        "results": results,
    }
