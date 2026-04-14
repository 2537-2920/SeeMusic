"""Pitch sequence loading, alignment, and report payload builders."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from backend.config.settings import settings


def resolve_pitch_json_path(path_str: str) -> Path:
    """Resolve a pitch JSON path from absolute or project-relative input."""
    candidate = Path(path_str).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [Path.cwd() / candidate, settings.storage_dir / candidate]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(f"Pitch JSON file not found: {path_str}")


def normalize_pitch_sequence(sequence: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize pitch points into a sorted internal representation."""
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(sequence):
        if not isinstance(item, dict):
            raise ValueError(f"Pitch item at index {index} must be an object")

        time_value = item.get("time", item.get("timestamp"))
        if time_value is None:
            raise ValueError(f"Pitch item at index {index} is missing time")

        frequency_value = item.get("frequency", item.get("frequency_hz", item.get("hz")))
        time_point = float(time_value)
        if not math.isfinite(time_point):
            raise ValueError(f"Pitch item at index {index} has invalid time")

        frequency: Optional[float]
        if frequency_value is None:
            frequency = None
        else:
            raw_frequency = float(frequency_value)
            frequency = raw_frequency if math.isfinite(raw_frequency) and raw_frequency > 0 else None

        confidence_value = item.get("confidence")
        confidence = None if confidence_value is None else float(confidence_value)
        if confidence is not None and not math.isfinite(confidence):
            confidence = None

        normalized.append(
            {
                "time": round(time_point, 4),
                "frequency": None if frequency is None else round(frequency, 4),
                "confidence": confidence,
                "note": item.get("note"),
            }
        )

    normalized.sort(key=lambda pitch_item: float(pitch_item["time"]))
    return normalized


def load_pitch_sequence_json(path_str: str) -> list[dict[str, Any]]:
    """Load pitch sequence data from JSON file."""
    path = resolve_pitch_json_path(path_str)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        sequence = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("pitch_sequence"), list):
            sequence = payload["pitch_sequence"]
        elif isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("pitch_sequence"), list):
            sequence = payload["data"]["pitch_sequence"]
        else:
            raise ValueError(f"Unsupported pitch JSON structure in {path}")
    else:
        raise ValueError(f"Unsupported pitch JSON type in {path}")

    return normalize_pitch_sequence(sequence)


def _trim_sequence_to_range(
    sequence: list[dict[str, Any]],
    start_time: Optional[float],
    end_time: Optional[float],
) -> list[dict[str, Any]]:
    if start_time is None and end_time is None:
        return sequence

    trimmed: list[dict[str, Any]] = []
    for item in sequence:
        time_point = float(item["time"])
        if start_time is not None and time_point < start_time:
            continue
        if end_time is not None and time_point > end_time:
            continue
        trimmed.append(item)
    return trimmed


def _infer_time_step(reference_curve: list[dict[str, Any]], user_curve: list[dict[str, Any]]) -> float:
    deltas: list[float] = []
    for curve in (reference_curve, user_curve):
        deltas.extend(
            max(float(curve[index + 1]["time"]) - float(curve[index]["time"]), 0.0)
            for index in range(len(curve) - 1)
        )

    positive = [delta for delta in deltas if delta > 1e-6]
    if not positive:
        return 0.05

    median_delta = float(np.median(np.array(positive, dtype=float)))
    return round(min(max(median_delta, 0.01), 0.5), 4)


def _build_time_axis(
    reference_curve: list[dict[str, Any]],
    user_curve: list[dict[str, Any]],
    *,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> tuple[list[float], float]:
    if not reference_curve and not user_curve:
        return [], 0.05

    inferred_step = _infer_time_step(reference_curve, user_curve)

    curve_starts = [float(curve[0]["time"]) for curve in (reference_curve, user_curve) if curve]
    curve_ends = [float(curve[-1]["time"]) for curve in (reference_curve, user_curve) if curve]

    default_start = min(curve_starts)
    default_end = max(curve_ends)
    overlap_start = max(curve_starts)
    overlap_end = min(curve_ends)

    axis_start = overlap_start if overlap_start <= overlap_end else default_start
    axis_end = overlap_end if overlap_start <= overlap_end else default_end

    if start_time is not None:
        axis_start = max(axis_start, start_time)
    if end_time is not None:
        axis_end = min(axis_end, end_time)

    if axis_end < axis_start:
        axis_start, axis_end = axis_end, axis_start

    time_axis = np.arange(axis_start, axis_end + inferred_step / 2.0, inferred_step, dtype=float)
    return [round(float(time_point), 4) for time_point in time_axis.tolist()], inferred_step


def _sample_curve(
    sequence: list[dict[str, Any]],
    time_axis: list[float],
    *,
    time_step: float,
) -> list[Optional[float]]:
    if not sequence:
        return [None for _ in time_axis]

    valid_points = [
        (float(item["time"]), float(item["frequency"]))
        for item in sequence
        if item.get("frequency") is not None
    ]
    if not valid_points:
        return [None for _ in time_axis]

    valid_times = np.array([time_value for time_value, _ in valid_points], dtype=float)
    valid_frequencies = np.array([frequency for _, frequency in valid_points], dtype=float)

    sampled = np.interp(np.array(time_axis, dtype=float), valid_times, valid_frequencies)
    sampled_array: list[Optional[float]] = []
    min_time = float(valid_times[0])
    max_time = float(valid_times[-1])
    gap_limit = max(time_step * 4.0, 0.2)

    for time_point, frequency in zip(time_axis, sampled.tolist()):
        if time_point < min_time or time_point > max_time:
            sampled_array.append(None)
            continue

        gap_is_too_large = False
        insert_index = int(np.searchsorted(valid_times, time_point, side="left"))
        if 0 < insert_index < len(valid_times):
            left = float(valid_times[insert_index - 1])
            right = float(valid_times[insert_index])
            if right - left > gap_limit and left < time_point < right:
                gap_is_too_large = True

        sampled_array.append(None if gap_is_too_large else round(float(frequency), 4))

    return sampled_array


def _build_deviation_rows(
    time_axis: list[float],
    reference_curve: list[Optional[float]],
    user_curve: list[Optional[float]],
) -> tuple[list[Optional[float]], list[Optional[float]], list[dict[str, float]]]:
    deviation_hz: list[Optional[float]] = []
    deviation_cents: list[Optional[float]] = []
    deviation_rows: list[dict[str, float]] = []

    for time_point, reference_frequency, user_frequency in zip(time_axis, reference_curve, user_curve):
        if reference_frequency is None or user_frequency is None:
            deviation_hz.append(None)
            deviation_cents.append(None)
            continue

        hz_offset = round(user_frequency - reference_frequency, 4)
        cents_offset = round(1200.0 * math.log2(user_frequency / reference_frequency), 4)
        deviation_hz.append(hz_offset)
        deviation_cents.append(cents_offset)
        deviation_rows.append(
            {
                "time": time_point,
                "hz_offset": hz_offset,
                "cents_offset": cents_offset,
            }
        )

    return deviation_hz, deviation_cents, deviation_rows


def _build_summary(
    deviation_hz: list[Optional[float]],
    deviation_cents: list[Optional[float]],
    matched_points: int,
    aligned_points: int,
) -> dict[str, Any]:
    valid_hz = [abs(value) for value in deviation_hz if value is not None]
    valid_cents = [abs(value) for value in deviation_cents if value is not None]
    mean_abs_hz = round(float(np.mean(valid_hz)), 4) if valid_hz else 0.0
    mean_abs_cents = round(float(np.mean(valid_cents)), 4) if valid_cents else 0.0
    max_abs_cents = round(float(np.max(valid_cents)), 4) if valid_cents else 0.0
    within_25 = round(sum(value <= 25.0 for value in valid_cents) / matched_points, 4) if matched_points else 0.0
    within_50 = round(sum(value <= 50.0 for value in valid_cents) / matched_points, 4) if matched_points else 0.0

    accuracy = 0.0 if matched_points == 0 else round(max(0.0, 100.0 - min(mean_abs_cents, 100.0)), 2)
    return {
        "accuracy": accuracy,
        "matched_points": matched_points,
        "aligned_points": aligned_points,
        "coverage_ratio": round(matched_points / aligned_points, 4) if aligned_points else 0.0,
        "average_deviation": mean_abs_hz,
        "average_deviation_hz": mean_abs_hz,
        "average_deviation_cents": mean_abs_cents,
        "max_deviation_cents": max_abs_cents,
        "within_25_cents_ratio": within_25,
        "within_50_cents_ratio": within_50,
    }


def build_pitch_comparison_payload(
    reference_curve: Iterable[dict[str, Any]],
    user_curve: Iterable[dict[str, Any]],
    *,
    time_range: Optional[dict[str, float]] = None,
    mode: str = "compare",
) -> dict[str, Any]:
    """Align reference/user pitch sequences and build chart/report payloads."""
    normalized_reference = normalize_pitch_sequence(reference_curve)
    normalized_user = normalize_pitch_sequence(user_curve)

    start_time = None if not time_range else time_range.get("start_time")
    end_time = None if not time_range else time_range.get("end_time")
    normalized_reference = _trim_sequence_to_range(normalized_reference, start_time, end_time)
    normalized_user = _trim_sequence_to_range(normalized_user, start_time, end_time)

    time_axis, time_step = _build_time_axis(
        normalized_reference,
        normalized_user,
        start_time=start_time,
        end_time=end_time,
    )
    aligned_reference = _sample_curve(normalized_reference, time_axis, time_step=time_step)
    aligned_user = _sample_curve(normalized_user, time_axis, time_step=time_step)

    deviation_hz, deviation_cents, deviation_rows = _build_deviation_rows(
        time_axis,
        aligned_reference,
        aligned_user,
    )
    matched_points = len(deviation_rows)
    aligned_points = len(time_axis)
    summary = _build_summary(deviation_hz, deviation_cents, matched_points, aligned_points)

    report_payload = {
        "chart_type": "pitch_comparison",
        "title": "Reference vs User Pitch",
        "mode": mode,
        "x_axis": time_axis,
        "series": [
            {"id": "reference", "label": "Reference Pitch", "unit": "Hz", "values": aligned_reference},
            {"id": "user", "label": "User Pitch", "unit": "Hz", "values": aligned_user},
            {"id": "deviation_cents", "label": "Pitch Deviation", "unit": "cents", "values": deviation_cents},
        ],
        "summary": summary,
    }

    return {
        "mode": mode,
        "time_step": time_step,
        "x_axis": time_axis,
        "reference_curve": aligned_reference,
        "user_curve": aligned_user,
        "deviation_curve": deviation_hz,
        "deviation_cents_curve": deviation_cents,
        "deviation": deviation_rows,
        "summary": summary,
        "alignment": {
            "start_time": time_axis[0] if time_axis else start_time,
            "end_time": time_axis[-1] if time_axis else end_time,
            "time_step": time_step,
            "aligned_points": aligned_points,
            "matched_points": matched_points,
        },
        "report_payload": report_payload,
        "reference_points": normalized_reference,
        "user_points": normalized_user,
    }
