"""Convert pitch sequences into normalized score structures."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

from backend.core.piano.arrangement import generate_piano_arrangement
from backend.core.pitch.pitch_sequence_utils import is_note_event_item
from backend.core.score.key_detection import detect_key_signature, normalize_key_signature_text, respell_pitch_sequence_for_key
from backend.core.score.melody_materialization import materialize_melody_from_pitch_sequence as shared_materialize_melody_from_pitch_sequence
from backend.core.score.musicxml_utils import build_musicxml_from_measures
from backend.core.score.note_mapping import (
    beats_per_measure,
    beats_to_duration_label,
    beats_to_seconds,
    frequency_to_note,
    midi_to_frequency,
    midi_to_note,
    note_to_midi,
    quantize_beats,
    seconds_to_beats,
)
from backend.core.score.score_utils import create_score

GAP_TOLERANCE_SECONDS = 0.05
MERGE_TOLERANCE_SECONDS = 0.05
SMALL_SAME_PITCH_GAP_BEATS = 0.25
MIN_REST_BEATS_TO_KEEP = 0.5
MIN_NOTATED_NOTE_BEATS = 0.25
PITCH_OUTLIER_SHORT_NOTE_BEATS = 0.5
PITCH_OUTLIER_MIN_JUMP_SEMITONES = 5
PITCH_OUTLIER_ANCHOR_TOLERANCE_SEMITONES = 3


def _fit_event_to_cursor(
    start_time: float,
    duration_seconds: float,
    cursor_time: float,
) -> tuple[float, float]:
    normalized_start = round(float(start_time), 3)
    normalized_duration = round(max(float(duration_seconds), 0.0), 3)
    if normalized_duration <= 0:
        return normalized_start, 0.0

    if normalized_start < cursor_time - GAP_TOLERANCE_SECONDS:
        original_end = round(normalized_start + normalized_duration, 3)
        normalized_start = round(cursor_time, 3)
        normalized_duration = round(max(original_end - normalized_start, 0.0), 3)
    return normalized_start, normalized_duration


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
            duration_seconds = round(max(end_time - start_time, 0.0), 3)
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

            start_time, duration_seconds = _fit_event_to_cursor(start_time, duration_seconds, cursor_time)
            if duration_seconds <= 0:
                continue
            end_time = round(start_time + duration_seconds, 3)

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
        duration_seconds = round(max(raw_duration, 0.0), 3)
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

        start_time, duration_seconds = _fit_event_to_cursor(start_time, duration_seconds, cursor_time)
        if duration_seconds <= 0:
            continue
        end_time = round(start_time + duration_seconds, 3)

        pitch = str(item.get("note") or frequency_to_note(frequency))
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


def _absorb_short_ornaments(events: List[Dict[str, Any]], tempo: int) -> List[Dict[str, Any]]:
    if not events:
        return []

    min_note_seconds = beats_to_seconds(MIN_NOTATED_NOTE_BEATS, tempo)
    working = [dict(event) for event in events]
    absorbed: List[Dict[str, Any]] = []
    index = 0

    while index < len(working):
        current = dict(working[index])
        duration = float(current.get("duration_seconds") or 0.0)
        next_item = working[index + 1] if index + 1 < len(working) else None

        if (
            not current.get("is_rest")
            and duration < min_note_seconds - 1e-6
            and next_item is not None
            and not bool(next_item.get("is_rest"))
        ):
            next_item["duration_seconds"] = round(float(next_item.get("duration_seconds") or 0.0) + duration, 3)
            index += 1
            continue

        absorbed.append(current)
        index += 1

    return absorbed


def _remove_too_short_notes(events: List[Dict[str, Any]], tempo: int) -> List[Dict[str, Any]]:
    if not events:
        return []

    min_note_seconds = beats_to_seconds(MIN_NOTATED_NOTE_BEATS, tempo)
    working = [dict(event) for event in events]
    cleaned: List[Dict[str, Any]] = []
    index = 0

    while index < len(working):
        current = dict(working[index])
        duration = float(current.get("duration_seconds") or 0.0)

        if not current.get("is_rest") and duration < min_note_seconds - 1e-6:
            if index + 1 < len(working):
                working[index + 1]["duration_seconds"] = round(
                    float(working[index + 1].get("duration_seconds") or 0.0) + duration,
                    3,
                )
            elif cleaned:
                cleaned[-1]["duration_seconds"] = round(
                    float(cleaned[-1].get("duration_seconds") or 0.0) + duration,
                    3,
                )
            index += 1
            continue

        cleaned.append(current)
        index += 1

    return cleaned


def _median_filter_pitch_outliers(events: List[Dict[str, Any]], tempo: int) -> List[Dict[str, Any]]:
    if len(events) < 3:
        return [dict(event) for event in events]

    short_note_seconds = beats_to_seconds(PITCH_OUTLIER_SHORT_NOTE_BEATS, tempo)
    filtered = [dict(event) for event in events]

    for index in range(1, len(filtered) - 1):
        previous = filtered[index - 1]
        current = filtered[index]
        following = filtered[index + 1]
        if previous.get("is_rest") or current.get("is_rest") or following.get("is_rest"):
            continue
        if float(current.get("duration_seconds") or 0.0) > short_note_seconds + 1e-6:
            continue

        previous_midi = note_to_midi(str(previous.get("pitch") or ""))
        current_midi = note_to_midi(str(current.get("pitch") or ""))
        following_midi = note_to_midi(str(following.get("pitch") or ""))
        if previous_midi is None or current_midi is None or following_midi is None:
            continue
        if abs(previous_midi - following_midi) > PITCH_OUTLIER_ANCHOR_TOLERANCE_SEMITONES:
            continue
        if (
            abs(current_midi - previous_midi) < PITCH_OUTLIER_MIN_JUMP_SEMITONES
            or abs(current_midi - following_midi) < PITCH_OUTLIER_MIN_JUMP_SEMITONES
        ):
            continue

        corrected_midi = sorted((previous_midi, current_midi, following_midi))[1]
        filtered[index]["pitch"] = midi_to_note(corrected_midi)
        filtered[index]["frequency"] = midi_to_frequency(corrected_midi)

    return filtered


def _simplify_events_for_readability(events: List[Dict[str, Any]], tempo: int) -> List[Dict[str, Any]]:
    if not events:
        return []

    merge_gap_seconds = beats_to_seconds(SMALL_SAME_PITCH_GAP_BEATS, tempo)
    min_rest_seconds = beats_to_seconds(MIN_REST_BEATS_TO_KEEP, tempo)
    working = _median_filter_pitch_outliers(events, tempo)
    working = _absorb_short_ornaments(working, tempo)
    working = _remove_too_short_notes(working, tempo)
    working = _merge_consecutive_rests(working)
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
        raw_beats = round(seconds_to_beats(event["duration_seconds"], tempo), 3)
        # Keep full length for notes that exceed one measure so they can be split with ties.
        remaining_beats = raw_beats if raw_beats > total_beats + 1e-6 else quantize_beats(raw_beats)
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


def materialize_melody_from_pitch_sequence(
    pitch_sequence: List[Dict[str, Any]],
    *,
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str | None = "C",
    auto_detect_key: bool = False,
) -> Dict[str, Any]:
    return shared_materialize_melody_from_pitch_sequence(
        pitch_sequence,
        tempo=tempo,
        time_signature=time_signature,
        key_signature=key_signature,
        auto_detect_key=auto_detect_key,
    )


def build_score_from_pitch_sequence(
    pitch_sequence: List[Dict[str, Any]],
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str | None = "C",
    title: str | None = None,
    auto_detect_key: bool = False,
    arrangement_mode: str = "piano_solo",
) -> Dict[str, Any]:
    resolved_arrangement_mode = "piano_solo" if str(arrangement_mode or "piano_solo").strip().lower() == "piano_solo" else "melody"
    melody_materialized = materialize_melody_from_pitch_sequence(
        pitch_sequence,
        tempo=tempo,
        time_signature=time_signature,
        key_signature=key_signature,
        auto_detect_key=auto_detect_key,
    )
    resolved_key_signature = str(melody_materialized["key_signature"])
    measures = list(melody_materialized["measures"])
    arrangement_payload: Dict[str, Any] | None = None
    measures_for_export = measures
    if resolved_arrangement_mode == "piano_solo":
        arrangement_payload = generate_piano_arrangement(
            melody_measures=measures,
            key_signature=resolved_key_signature,
            tempo=int(tempo),
            time_signature=time_signature,
            title=title,
        )
        measures_for_export = list(arrangement_payload.get("arranged_measures") or measures)
    musicxml = build_musicxml_from_measures(
        measures_for_export,
        tempo=tempo,
        time_signature=time_signature,
        key_signature=resolved_key_signature,
        title=title,
    )
    score = create_score(
        musicxml=musicxml,
        title=title,
    )
    score["arrangement_mode"] = resolved_arrangement_mode
    if arrangement_payload is not None:
        score["piano_arrangement"] = arrangement_payload
        score["score_mode"] = "piano_two_hand_arrangement"
    else:
        score["score_mode"] = "melody_transcription"
    return score
