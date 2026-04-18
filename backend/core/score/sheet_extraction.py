"""Convert pitch sequences into normalized score structures."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

from backend.core.pitch.pitch_sequence_utils import is_note_event_item
from backend.core.score.musicxml_utils import build_musicxml_from_measures
from backend.core.score.note_mapping import beats_per_measure, beats_to_duration_label, beats_to_seconds, frequency_to_note, quantize_beats, seconds_to_beats
from backend.core.score.score_utils import create_score

GAP_TOLERANCE_SECONDS = 0.05
MERGE_TOLERANCE_SECONDS = 0.05
SMALL_SAME_PITCH_GAP_BEATS = 0.25
MIN_REST_BEATS_TO_KEEP = 0.5


def _normalize_pitch_items(pitch_sequence: List[Dict[str, Any]], tempo: int) -> List[Dict[str, Any]]:
    items = sorted(
        pitch_sequence,
        key=lambda item: float(item.get("start", item.get("time", 0.0))),
    )
    if not items:
        return []

    default_duration_seconds = beats_to_seconds(1.0, tempo)
    events: List[Dict[str, Any]] = []
    cursor_time = 0.0

    for index, item in enumerate(items):
        if is_note_event_item(item):
            start_time = round(float(item.get("start", 0.0)), 3)
            end_time = round(float(item.get("end", start_time)), 3)
            if end_time <= start_time:
                end_time = round(start_time + beats_to_seconds(0.25, tempo), 3)
            duration_seconds = round(max(end_time - start_time, beats_to_seconds(0.25, tempo)), 3)
            frequency = round(float(item.get("frequency_avg", 0.0) or 0.0), 2)
            pitch = str(item.get("note") or frequency_to_note(frequency))
            is_rest = pitch == "Rest" or frequency <= 0.0

            if start_time - cursor_time > GAP_TOLERANCE_SECONDS:
                rest_duration = round(start_time - cursor_time, 3)
                if events and events[-1]["is_rest"]:
                    events[-1]["duration_seconds"] = round(events[-1]["duration_seconds"] + rest_duration, 3)
                    events[-1]["end_time"] = start_time
                else:
                    events.append(
                        {
                            "pitch": "Rest",
                            "frequency": 0.0,
                            "duration_seconds": rest_duration,
                            "is_rest": True,
                            "start_time": cursor_time,
                            "end_time": start_time,
                        }
                    )
                cursor_time = start_time

            events.append(
                {
                    "pitch": "Rest" if is_rest else pitch,
                    "frequency": 0.0 if is_rest else frequency,
                    "duration_seconds": duration_seconds,
                    "is_rest": is_rest,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            cursor_time = max(cursor_time, end_time)
            continue

        start_time = round(float(item.get("time", 0.0)), 3)
        frequency = round(float(item.get("frequency", 0.0)), 2)
        next_time = None
        if index + 1 < len(items):
            next_time = round(float(items[index + 1].get("time", start_time)), 3)

        raw_duration = float(item.get("duration") or 0.0)
        if raw_duration <= 0:
            raw_duration = (next_time - start_time) if next_time is not None else default_duration_seconds
        duration_seconds = round(max(raw_duration, beats_to_seconds(0.25, tempo)), 3)
        end_time = round(start_time + duration_seconds, 3)

        if start_time - cursor_time > GAP_TOLERANCE_SECONDS:
            rest_duration = round(start_time - cursor_time, 3)
            if events and events[-1]["is_rest"]:
                events[-1]["duration_seconds"] = round(events[-1]["duration_seconds"] + rest_duration, 3)
                events[-1]["end_time"] = start_time
            else:
                events.append(
                    {
                        "pitch": "Rest",
                        "frequency": 0.0,
                        "duration_seconds": rest_duration,
                        "is_rest": True,
                        "start_time": cursor_time,
                        "end_time": start_time,
                    }
                )
            cursor_time = start_time

        pitch = frequency_to_note(frequency)
        is_rest = pitch == "Rest"
        if (
            events
            and not is_rest
            and not events[-1]["is_rest"]
            and events[-1]["pitch"] == pitch
            and abs(start_time - events[-1]["end_time"]) <= MERGE_TOLERANCE_SECONDS
        ):
            events[-1]["duration_seconds"] = round(events[-1]["duration_seconds"] + duration_seconds, 3)
            events[-1]["end_time"] = end_time
        else:
            events.append(
                {
                    "pitch": pitch,
                    "frequency": frequency if not is_rest else 0.0,
                    "duration_seconds": duration_seconds,
                    "is_rest": is_rest,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
        cursor_time = max(cursor_time, end_time)

    return events


def _empty_measure(measure_no: int, total_beats: float) -> Dict[str, Any]:
    return {
        "measure_no": measure_no,
        "notes": [],
        "total_beats": total_beats,
        "used_beats": 0.0,
    }


def _merge_consecutive_rests(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for event in events:
        item = dict(event)
        if merged and item["is_rest"] and merged[-1]["is_rest"]:
            merged[-1]["duration_seconds"] = round(
                float(merged[-1]["duration_seconds"]) + float(item["duration_seconds"]),
                3,
            )
            continue
        merged.append(item)
    return merged


def _rebuild_event_timings(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cursor = 0.0
    rebuilt: List[Dict[str, Any]] = []
    for event in events:
        item = dict(event)
        duration = round(max(float(item.get("duration_seconds") or 0.0), 0.0), 3)
        item["start_time"] = round(cursor, 3)
        item["duration_seconds"] = duration
        cursor = round(cursor + duration, 3)
        item["end_time"] = cursor
        rebuilt.append(item)
    return rebuilt


def _merge_adjacent_same_pitch(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for event in events:
        item = dict(event)
        if (
            merged
            and not item["is_rest"]
            and not merged[-1]["is_rest"]
            and merged[-1]["pitch"] == item["pitch"]
        ):
            merged[-1]["duration_seconds"] = round(
                float(merged[-1]["duration_seconds"]) + float(item["duration_seconds"]),
                3,
            )
            continue
        merged.append(item)
    return merged


def _simplify_events_for_readability(events: List[Dict[str, Any]], tempo: int) -> List[Dict[str, Any]]:
    if not events:
        return []

    merge_gap_seconds = beats_to_seconds(SMALL_SAME_PITCH_GAP_BEATS, tempo)
    min_rest_seconds = beats_to_seconds(MIN_REST_BEATS_TO_KEEP, tempo)
    working = _merge_consecutive_rests(events)
    simplified: List[Dict[str, Any]] = []
    index = 0

    while index < len(working):
        current = dict(working[index])
        if current["is_rest"]:
            duration = float(current["duration_seconds"])
            if duration < min_rest_seconds:
                if simplified and not simplified[-1]["is_rest"]:
                    simplified[-1]["duration_seconds"] = round(
                        float(simplified[-1]["duration_seconds"]) + duration,
                        3,
                    )
                elif index + 1 < len(working) and not working[index + 1]["is_rest"]:
                    working[index + 1]["duration_seconds"] = round(
                        float(working[index + 1]["duration_seconds"]) + duration,
                        3,
                    )
                else:
                    simplified.append(current)
            else:
                simplified.append(current)
            index += 1
            continue

        while (
            index + 2 < len(working)
            and working[index + 1]["is_rest"]
            and float(working[index + 1]["duration_seconds"]) <= merge_gap_seconds
            and not working[index + 2]["is_rest"]
            and working[index + 2]["pitch"] == current["pitch"]
        ):
            current["duration_seconds"] = round(
                float(current["duration_seconds"])
                + float(working[index + 1]["duration_seconds"])
                + float(working[index + 2]["duration_seconds"]),
                3,
            )
            index += 2

        simplified.append(current)
        index += 1

    return _rebuild_event_timings(_merge_adjacent_same_pitch(_merge_consecutive_rests(simplified)))


def _materialize_measures(events: List[Dict[str, Any]], tempo: int, time_signature: str) -> List[Dict[str, Any]]:
    total_beats = beats_per_measure(time_signature)
    measures = [_empty_measure(1, total_beats)]
    measure_no = 1
    position_in_measure = 0.0
    global_position_beats = 0.0

    for event in events:
        remaining_beats = quantize_beats(seconds_to_beats(event["duration_seconds"], tempo))
        event_group_id = f"evt_{uuid4().hex[:8]}"
        segment_index = 0

        while remaining_beats > 1e-6:
            while len(measures) < measure_no:
                measures.append(_empty_measure(len(measures) + 1, total_beats))
            measure = measures[measure_no - 1]
            available_beats = round(total_beats - position_in_measure, 3)
            if available_beats <= 1e-6:
                measure_no += 1
                position_in_measure = 0.0
                continue

            segment_beats = round(min(remaining_beats, available_beats), 3)
            start_beat = round(position_in_measure + 1.0, 3)
            note = {
                "note_id": f"n_{uuid4().hex[:8]}",
                "source_event_id": event_group_id,
                "pitch": event["pitch"],
                "frequency": event["frequency"],
                "beats": segment_beats,
                "duration": beats_to_duration_label(segment_beats),
                "start_beat": start_beat,
                "time": beats_to_seconds(global_position_beats, tempo),
                "duration_seconds": beats_to_seconds(segment_beats, tempo),
                "is_rest": event["is_rest"],
                "tied_from_previous": segment_index > 0 and not event["is_rest"],
                "tied_to_next": remaining_beats - segment_beats > 1e-6 and not event["is_rest"],
            }
            measure["notes"].append(note)
            measure["used_beats"] = round(measure["used_beats"] + segment_beats, 3)

            remaining_beats = round(remaining_beats - segment_beats, 3)
            position_in_measure = round(position_in_measure + segment_beats, 3)
            global_position_beats = round(global_position_beats + segment_beats, 3)
            segment_index += 1

            if position_in_measure >= total_beats - 1e-6:
                measure_no += 1
                position_in_measure = 0.0

    return measures

def build_score_from_pitch_sequence(
    pitch_sequence: List[Dict[str, Any]],
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str = "C",
    title: str | None = None,
) -> Dict[str, Any]:
    events = _normalize_pitch_items(pitch_sequence, tempo)
    events = _simplify_events_for_readability(events, tempo)
    measures = _materialize_measures(events, tempo, time_signature) if events else [_empty_measure(1, beats_per_measure(time_signature))]
    musicxml = build_musicxml_from_measures(
        measures,
        tempo=tempo,
        time_signature=time_signature,
        key_signature=key_signature,
        title=title,
    )
    return create_score(
        musicxml=musicxml,
        title=title,
    )
