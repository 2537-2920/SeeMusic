"""Helpers for storing and replaying pitch sequences efficiently."""

from __future__ import annotations

import math
from typing import Any, Iterable

from backend.core.score.note_mapping import frequency_to_note


DEFAULT_HOP_MS = 10


def is_note_event_item(item: dict[str, Any]) -> bool:
    return isinstance(item, dict) and "start" in item and "end" in item and "time" not in item


def is_note_event_sequence(sequence: Iterable[dict[str, Any]] | None) -> bool:
    sequence_list = list(sequence or [])
    return bool(sequence_list) and all(is_note_event_item(item) for item in sequence_list)


def _positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _resolve_note_name(item: dict[str, Any], frequency: float) -> str:
    note = str(item.get("note") or "").strip()
    if note:
        return note
    return frequency_to_note(frequency)


def compress_pitch_sequence_to_note_events(
    pitch_sequence: list[dict[str, Any]] | None,
    *,
    hop_ms: int = DEFAULT_HOP_MS,
) -> list[dict[str, Any]]:
    items = sorted(list(pitch_sequence or []), key=lambda item: float(item.get("time", 0.0)))
    if not items:
        return []

    hop_seconds = max(float(hop_ms or DEFAULT_HOP_MS) / 1000.0, 0.001)
    merge_gap = max(hop_seconds * 1.5, 0.03)
    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush_current() -> None:
        nonlocal current
        if current is None:
            return
        sample_count = max(int(current.pop("sample_count", 1)), 1)
        events.append(
            {
                "start": round(float(current["start"]), 4),
                "end": round(float(current["end"]), 4),
                "note": str(current["note"]),
                "frequency_avg": round(float(current["frequency_sum"]) / sample_count, 4),
            }
        )
        current = None

    for item in items:
        frequency = _positive_float(item.get("frequency"))
        if frequency is None or item.get("voiced", True) is False:
            flush_current()
            continue

        start = round(float(item.get("time", 0.0)), 4)
        duration = _positive_float(item.get("duration")) or hop_seconds
        end = round(start + max(duration, hop_seconds), 4)
        note = _resolve_note_name(item, frequency)

        if (
            current is not None
            and current["note"] == note
            and start - float(current["end"]) <= merge_gap
        ):
            current["end"] = max(float(current["end"]), end)
            current["frequency_sum"] = float(current["frequency_sum"]) + frequency
            current["sample_count"] = int(current["sample_count"]) + 1
            continue

        flush_current()
        current = {
            "start": start,
            "end": end,
            "note": note,
            "frequency_sum": frequency,
            "sample_count": 1,
        }

    flush_current()
    return events


def expand_note_events_to_pitch_sequence(
    note_events: list[dict[str, Any]] | None,
    *,
    hop_ms: int = DEFAULT_HOP_MS,
) -> list[dict[str, Any]]:
    events = sorted(list(note_events or []), key=lambda item: float(item.get("start", 0.0)))
    if not events:
        return []

    hop_seconds = max(float(hop_ms or DEFAULT_HOP_MS) / 1000.0, 0.001)
    sequence: list[dict[str, Any]] = []

    for event in events:
        start = float(event.get("start", 0.0))
        end = float(event.get("end", start))
        if not math.isfinite(start) or not math.isfinite(end):
            continue
        if end <= start:
            end = start + hop_seconds

        frequency = _positive_float(event.get("frequency_avg"))
        note = str(event.get("note") or "").strip()
        if frequency is None:
            continue
        if not note:
            note = frequency_to_note(frequency)

        cursor = start
        while cursor < end - 1e-6:
            duration = min(hop_seconds, end - cursor)
            sequence.append(
                {
                    "time": round(cursor, 4),
                    "frequency": round(frequency, 4),
                    "duration": round(duration, 4),
                    "note": note,
                    "confidence": None,
                }
            )
            cursor = round(cursor + hop_seconds, 6)

    return sequence


def extract_note_events_from_result(
    result_data: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(result_data, dict):
        return [], {}
    if result_data.get("pitch_sequence_format") != "note_events":
        return [], {}
    note_events = list(result_data.get("pitch_sequence") or [])
    if not is_note_event_sequence(note_events):
        return [], {}
    pitch_meta = result_data.get("pitch_meta")
    return note_events, pitch_meta if isinstance(pitch_meta, dict) else {}
