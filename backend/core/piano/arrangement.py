"""Generate a simple two-hand piano arrangement from a melody line."""

from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from typing import Any
from uuid import uuid4

from backend.core.guitar.lead_sheet import generate_guitar_lead_sheet
from backend.core.score.note_mapping import beats_per_measure, note_to_midi, quantize_beats


NOTE_NAME_TO_PITCH_CLASS = {
    "C": 0,
    "B#": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "Fb": 4,
    "F": 5,
    "E#": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
    "Cb": 11,
}
PITCH_CLASS_TO_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH_CLASS_TO_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
CHORD_INTERVALS = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "dim": (0, 3, 6),
    "7": (0, 4, 7, 10),
}
HAND_SPLIT_POINT_MIDI = 60
LOW_MELODY_THRESHOLD_MIDI = 55
RIGHT_HAND_MIN_MIDI = 60
RIGHT_HAND_MAX_MIDI = 84
LEFT_HAND_MIN_MIDI = 36
LEFT_HAND_MAX_MIDI = 59
MIN_HAND_GAP_SEMITONES = 5
LONG_NOTE_CHORD_TONE_FILL_ENABLED = False


def _parse_chord_symbol(symbol: str) -> tuple[str, str]:
    token = str(symbol or "").strip()
    if not token:
        return "C", ""
    root = token[0].upper()
    suffix = token[1:]
    if suffix.startswith(("#", "b")):
        root += suffix[0]
        suffix = suffix[1:]
    if suffix.startswith("maj7"):
        suffix = ""
    if suffix not in CHORD_INTERVALS:
        if suffix.startswith("m"):
            suffix = "m"
        elif "dim" in suffix:
            suffix = "dim"
        elif "7" in suffix:
            suffix = "7"
        else:
            suffix = ""
    return root, suffix


def _pitch_class_to_name(pitch_class: int, *, prefer_flats: bool) -> str:
    names = PITCH_CLASS_TO_FLAT if prefer_flats else PITCH_CLASS_TO_SHARP
    return names[int(pitch_class) % 12]


def _prefer_flats(key_signature: str) -> bool:
    normalized = str(key_signature or "C").strip()
    tonic = normalized[:-1] if normalized.endswith("m") else normalized
    return "b" in tonic


def _closest_midi_for_pitch_class(
    pitch_class: int,
    *,
    target: int,
    minimum: int,
    maximum: int,
) -> int:
    best = minimum
    best_distance = abs(best - target)
    for midi in range(minimum, maximum + 1):
        if midi % 12 != pitch_class:
            continue
        distance = abs(midi - target)
        if distance < best_distance:
            best = midi
            best_distance = distance
    return best


def _midi_to_spelled_note(midi: int, *, prefer_flats: bool) -> str:
    pitch_class = int(midi % 12)
    octave = midi // 12 - 1
    return f"{_pitch_class_to_name(pitch_class, prefer_flats=prefer_flats)}{octave}"


def _extract_melody_notes(measures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    melody: list[dict[str, Any]] = []
    for measure in measures:
        measure_no = int(measure.get("measure_no") or 1)
        for note in measure.get("notes") or []:
            pitch = str(note.get("pitch") or "")
            if note.get("is_rest") or pitch == "Rest":
                continue
            beats = float(note.get("beats") or 0.0)
            start_beat = float(note.get("start_beat") or 1.0)
            melody.append(
                {
                    "measure_no": measure_no,
                    "start_beat": start_beat,
                    "beats": beats,
                    "end_beat": round(start_beat + beats, 3),
                    "pitch": pitch,
                    "midi": note_to_midi(pitch),
                }
            )
    return melody


def _transpose_pitch_by_octaves(pitch: str, octave_shift: int) -> str:
    token = str(pitch or "").strip()
    if token == "Rest" or octave_shift == 0:
        return token
    match = re.fullmatch(r"([A-G](?:#|b)?)(-?\d+)", token)
    if not match:
        return token
    note_name, octave_text = match.groups()
    return f"{note_name}{int(octave_text) + int(octave_shift)}"


def _transpose_note_payload_by_octaves(note: dict[str, Any], octave_shift: int) -> dict[str, Any]:
    if octave_shift == 0 or note.get("is_rest") or str(note.get("pitch") or "") == "Rest":
        return deepcopy(note)
    shifted = deepcopy(note)
    shifted["pitch"] = _transpose_pitch_by_octaves(str(note.get("pitch") or ""), octave_shift)
    shifted["frequency"] = 0.0
    return shifted


def _global_melody_octave_shift(melody_notes: list[dict[str, Any]]) -> int:
    playable_midis = [int(note["midi"]) for note in melody_notes if note.get("midi") is not None]
    if not playable_midis:
        return 0

    shift = 0
    current_min = min(playable_midis)
    current_max = max(playable_midis)
    while current_min + shift * 12 < RIGHT_HAND_MIN_MIDI and current_max + (shift + 1) * 12 <= RIGHT_HAND_MAX_MIDI + 12:
        shift += 1
    while current_max + shift * 12 > RIGHT_HAND_MAX_MIDI and current_min + (shift - 1) * 12 >= RIGHT_HAND_MIN_MIDI - 12:
        shift -= 1
    return shift


def _normalize_right_hand_range(measures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    melody_notes = _extract_melody_notes(measures)
    global_shift = _global_melody_octave_shift(melody_notes)
    normalized_measures: list[dict[str, Any]] = []
    transposed_note_count = 0

    for measure in measures:
        updated_measure = deepcopy(measure)
        updated_notes: list[dict[str, Any]] = []
        for note in measure.get("notes") or []:
            updated_note = _transpose_note_payload_by_octaves(note, global_shift)
            pitch = str(updated_note.get("pitch") or "")
            midi = note_to_midi(pitch) if pitch != "Rest" else None
            local_shift = 0
            while midi is not None and midi < RIGHT_HAND_MIN_MIDI:
                midi += 12
                local_shift += 1
            while midi is not None and midi > RIGHT_HAND_MAX_MIDI:
                midi -= 12
                local_shift -= 1
            if local_shift:
                updated_note = _transpose_note_payload_by_octaves(updated_note, local_shift)
            if global_shift or local_shift:
                transposed_note_count += 1
            updated_notes.append(updated_note)
        updated_measure["notes"] = updated_notes
        normalized_measures.append(updated_measure)

    return normalized_measures, {
        "target_range": {"low": "C4", "high": "C6", "low_midi": RIGHT_HAND_MIN_MIDI, "high_midi": RIGHT_HAND_MAX_MIDI},
        "global_octave_shift": global_shift,
        "transposed_note_count": transposed_note_count,
    }


def _choose_texture_pattern(tempo: int, time_signature: str) -> dict[str, Any]:
    if time_signature == "3/4":
        return {
            "name": "waltz_bass_chord",
            "description": "第 1 拍低音，第 2/3 拍和声音型，适合民谣和抒情三拍。",
            "pulse_cycle": ("bass", "chord", "chord"),
        }
    if tempo <= 88:
        return {
            "name": "ballad_root_shell",
            "description": "慢速抒情型：低音与和声音壳交替，保留主旋律空间。",
            "pulse_cycle": ("bass", "chord", "bass_alt", "chord"),
        }
    return {
        "name": "pop_root_chord",
        "description": "流行型：强拍低音、弱拍和声音壳，方便形成稳定律动。",
        "pulse_cycle": ("bass", "chord", "bass_alt", "chord"),
    }


def _active_melody_floor(
    melody_by_measure: dict[int, list[dict[str, Any]]],
    *,
    measure_no: int,
    start_beat: float,
    end_beat: float,
) -> int | None:
    active_midis = [
        int(note["midi"])
        for note in melody_by_measure.get(measure_no, [])
        if note.get("midi") is not None
        and float(note["start_beat"]) < end_beat - 1e-6
        and float(note["end_beat"]) > start_beat + 1e-6
    ]
    return min(active_midis) if active_midis else None


def _shell_midis_for_chord(symbol: str, *, prefer_flats: bool) -> list[int]:
    root, quality = _parse_chord_symbol(symbol)
    root_pitch_class = NOTE_NAME_TO_PITCH_CLASS.get(root, 0)
    intervals = CHORD_INTERVALS.get(quality, CHORD_INTERVALS[""])
    if quality == "7":
        shell_pitch_classes = (
            (root_pitch_class + intervals[1]) % 12,
            (root_pitch_class + intervals[3]) % 12,
        )
    else:
        shell_pitch_classes = (
            (root_pitch_class + intervals[1]) % 12,
            (root_pitch_class + intervals[2]) % 12,
        )

    return [
        _closest_midi_for_pitch_class(
            pitch_class,
            target=50 + index * 3,
            minimum=43,
            maximum=LEFT_HAND_MAX_MIDI,
        )
        for index, pitch_class in enumerate(shell_pitch_classes)
    ]


def _bass_midi_for_chord(symbol: str, *, use_fifth: bool = False) -> int:
    root, quality = _parse_chord_symbol(symbol)
    root_pitch_class = NOTE_NAME_TO_PITCH_CLASS.get(root, 0)
    intervals = CHORD_INTERVALS.get(quality, CHORD_INTERVALS[""])
    pitch_class = (root_pitch_class + (intervals[2] if use_fifth and len(intervals) >= 3 else 0)) % 12
    return _closest_midi_for_pitch_class(
        pitch_class,
        target=40,
        minimum=LEFT_HAND_MIN_MIDI,
        maximum=50,
    )


def _build_note(
    *,
    pitch: str,
    beats: float,
    start_beat: float,
    staff: int,
    voice: int,
    chord_with_previous: bool = False,
) -> dict[str, Any]:
    return {
        "note_id": f"n_{uuid4().hex[:8]}",
        "pitch": pitch,
        "frequency": 0.0,
        "beats": quantize_beats(beats),
        "start_beat": round(start_beat, 3),
        "duration": None,
        "is_rest": pitch == "Rest",
        "staff": int(staff),
        "voice": int(voice),
        "hand": "right" if int(staff) == 1 else "left",
        "chord_with_previous": bool(chord_with_previous),
    }


def _append_shell_notes(
    output: list[dict[str, Any]],
    *,
    symbol: str,
    start_beat: float,
    beats: float,
    prefer_flats: bool,
    melody_floor_midi: int | None,
) -> None:
    shell_midis = _shell_midis_for_chord(symbol, prefer_flats=prefer_flats)
    if melody_floor_midi is not None:
        while shell_midis and max(shell_midis) >= melody_floor_midi - 2 and min(shell_midis) - 12 >= LEFT_HAND_MIN_MIDI:
            shell_midis = [midi - 12 for midi in shell_midis]
    ordered = sorted(shell_midis)
    for index, midi in enumerate(ordered):
        output.append(
            _build_note(
                pitch=_midi_to_spelled_note(midi, prefer_flats=prefer_flats),
                beats=beats,
                start_beat=start_beat,
                staff=2,
                voice=2,
                chord_with_previous=index > 0,
            )
        )


def _pulse_events_for_chord(
    chord: dict[str, Any],
    *,
    texture_pattern: dict[str, Any],
    melody_floor_midi: int | None,
    prefer_flats: bool,
) -> list[dict[str, Any]]:
    pulses: list[dict[str, Any]] = []
    slot_beats = max(float(chord.get("beats") or 0.0), 0.25)
    start_beat = float(chord.get("beat_in_measure") or 1.0)
    cycle = tuple(texture_pattern.get("pulse_cycle") or ("bass", "chord"))
    pulse_index = 0
    consumed = 0.0

    while consumed < slot_beats - 1e-6:
        remaining = round(slot_beats - consumed, 3)
        pulse_beats = min(1.0, remaining)
        pulse_kind = cycle[pulse_index % len(cycle)]
        pulse_start = round(start_beat + consumed, 3)
        if pulse_kind == "chord" or remaining < 1.0:
            _append_shell_notes(
                pulses,
                symbol=str(chord.get("symbol") or "C"),
                start_beat=pulse_start,
                beats=pulse_beats,
                prefer_flats=prefer_flats,
                melody_floor_midi=melody_floor_midi,
            )
        else:
            bass_midi = _bass_midi_for_chord(
                str(chord.get("symbol") or "C"),
                use_fifth=pulse_kind == "bass_alt",
            )
            pulses.append(
                _build_note(
                    pitch=_midi_to_spelled_note(bass_midi, prefer_flats=prefer_flats),
                    beats=pulse_beats,
                    start_beat=pulse_start,
                    staff=2,
                    voice=2,
                )
            )
        consumed = round(consumed + pulse_beats, 3)
        pulse_index += 1

    return pulses


def _fill_measure_with_rests(
    notes: list[dict[str, Any]],
    *,
    total_beats: float,
    staff: int,
    voice: int,
) -> list[dict[str, Any]]:
    ordered = sorted(
        [deepcopy(note) for note in notes],
        key=lambda item: (float(item.get("start_beat", 1.0)), bool(item.get("chord_with_previous")), str(item.get("note_id") or "")),
    )
    if not ordered:
        return [_build_note(pitch="Rest", beats=total_beats, start_beat=1.0, staff=staff, voice=voice)]

    rebuilt: list[dict[str, Any]] = []
    cursor = 1.0
    for note in ordered:
        start_beat = round(float(note.get("start_beat") or 1.0), 3)
        beats = round(float(note.get("beats") or 0.0), 3)
        if not bool(note.get("chord_with_previous")) and start_beat - cursor > 1e-6:
            rebuilt.append(_build_note(pitch="Rest", beats=start_beat - cursor, start_beat=cursor, staff=staff, voice=voice))
        rebuilt.append(note)
        if not bool(note.get("chord_with_previous")):
            cursor = round(start_beat + beats, 3)

    if total_beats + 1.0 - cursor > 1e-6:
        rebuilt.append(
            _build_note(
                pitch="Rest",
                beats=total_beats + 1.0 - cursor,
                start_beat=cursor,
                staff=staff,
                voice=voice,
            )
        )
    return rebuilt


def _active_right_hand_min_midi(
    notes: list[dict[str, Any]],
    *,
    start_beat: float,
    end_beat: float,
) -> int | None:
    active_midis = []
    for note in notes:
        if note.get("is_rest") or str(note.get("pitch") or "") == "Rest":
            continue
        note_start = float(note.get("start_beat") or 1.0)
        note_end = round(note_start + float(note.get("beats") or 0.0), 3)
        if note_start < end_beat - 1e-6 and note_end > start_beat + 1e-6:
            midi = note_to_midi(str(note.get("pitch") or ""))
            if midi is not None:
                active_midis.append(int(midi))
    return min(active_midis) if active_midis else None


def _resolve_hand_spacing(
    right_hand_notes: list[dict[str, Any]],
    left_hand_notes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    adjusted_right = [deepcopy(note) for note in right_hand_notes]
    adjusted_left = [deepcopy(note) for note in left_hand_notes]
    right_octave_lifts = 0
    left_octave_drops = 0

    for left_note in adjusted_left:
        if left_note.get("is_rest") or str(left_note.get("pitch") or "") == "Rest":
            continue
        left_start = float(left_note.get("start_beat") or 1.0)
        left_end = round(left_start + float(left_note.get("beats") or 0.0), 3)
        left_midi = note_to_midi(str(left_note.get("pitch") or ""))
        if left_midi is None:
            continue
        right_floor = _active_right_hand_min_midi(adjusted_right, start_beat=left_start, end_beat=left_end)
        if right_floor is None or left_midi <= right_floor - MIN_HAND_GAP_SEMITONES:
            continue
        if left_midi - 12 >= LEFT_HAND_MIN_MIDI:
            left_note["pitch"] = _transpose_pitch_by_octaves(str(left_note.get("pitch") or ""), -1)
            left_octave_drops += 1
            continue
        for right_note in adjusted_right:
            if right_note.get("is_rest") or str(right_note.get("pitch") or "") == "Rest":
                continue
            right_start = float(right_note.get("start_beat") or 1.0)
            right_end = round(right_start + float(right_note.get("beats") or 0.0), 3)
            if right_start >= left_end - 1e-6 or right_end <= left_start + 1e-6:
                continue
            right_midi = note_to_midi(str(right_note.get("pitch") or ""))
            if right_midi is None:
                continue
            if right_midi + 12 <= RIGHT_HAND_MAX_MIDI + 12:
                right_note["pitch"] = _transpose_pitch_by_octaves(str(right_note.get("pitch") or ""), 1)
                right_octave_lifts += 1

    return adjusted_right, adjusted_left, right_octave_lifts, left_octave_drops


def generate_piano_arrangement(
    *,
    melody_measures: list[dict[str, Any]],
    key_signature: str,
    tempo: int,
    time_signature: str = "4/4",
    title: str | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    total_beats = beats_per_measure(time_signature)
    normalized_melody_measures, right_hand_range = _normalize_right_hand_range(melody_measures)
    melody_notes = _extract_melody_notes(normalized_melody_measures)
    preferred_style = style or ("ballad" if int(tempo) <= 88 else "pop")
    lead_sheet = generate_guitar_lead_sheet(
        key=key_signature,
        tempo=int(tempo),
        style=preferred_style,
        melody=melody_notes,
        time_signature=time_signature,
        title=title,
    )
    texture_pattern = _choose_texture_pattern(int(tempo), time_signature)
    prefer_flats = _prefer_flats(key_signature)
    melody_by_measure: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for note in melody_notes:
            melody_by_measure[int(note["measure_no"])].append(note)

    melody_measure_map = {
        int(measure.get("measure_no") or 1): {
            **deepcopy(measure),
            "right_hand_notes": [
                {
                    **deepcopy(note),
                    "staff": 1,
                    "voice": 1,
                    "hand": "right",
                    "chord_with_previous": False,
                }
                for note in (measure.get("notes") or [])
            ],
        }
        for measure in normalized_melody_measures
    }

    left_hand_by_measure: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for chord in lead_sheet.get("chords") or []:
        measure_no = int(chord.get("measure_no") or 1)
        start_beat = float(chord.get("beat_in_measure") or 1.0)
        end_beat = round(start_beat + float(chord.get("beats") or 0.0), 3)
        melody_floor_midi = _active_melody_floor(
            melody_by_measure,
            measure_no=measure_no,
            start_beat=start_beat,
            end_beat=end_beat,
        )
        left_hand_by_measure[measure_no].extend(
            _pulse_events_for_chord(
                chord,
                texture_pattern=texture_pattern,
                melody_floor_midi=melody_floor_midi,
                prefer_flats=prefer_flats,
            )
        )

    measure_numbers = sorted(set(melody_measure_map) | set(left_hand_by_measure) or {1})
    arranged_measures: list[dict[str, Any]] = []
    for measure_no in measure_numbers:
        measure = deepcopy(
            melody_measure_map.get(
                measure_no,
                {
                    "measure_no": measure_no,
                    "notes": [],
                    "total_beats": total_beats,
                    "used_beats": 0.0,
                    "right_hand_notes": [],
                },
            )
        )
        right_hand_notes = _fill_measure_with_rests(
            list(measure.get("right_hand_notes") or []),
            total_beats=total_beats,
            staff=1,
            voice=1,
        )
        left_hand_notes = _fill_measure_with_rests(
            list(left_hand_by_measure.get(measure_no) or []),
            total_beats=total_beats,
            staff=2,
            voice=2,
        )
        right_hand_notes, left_hand_notes, measure_right_lifts, measure_left_drops = _resolve_hand_spacing(
            right_hand_notes,
            left_hand_notes,
        )
        measure["right_hand_notes"] = right_hand_notes
        measure["left_hand_notes"] = left_hand_notes
        measure["notes"] = right_hand_notes
        measure["spacing_adjustments"] = {
            "right_octave_lifts": measure_right_lifts,
            "left_octave_drops": measure_left_drops,
        }
        arranged_measures.append(measure)

    accompaniment_note_count = sum(
        1
        for measure in arranged_measures
        for note in measure.get("left_hand_notes") or []
        if not note.get("is_rest")
    )
    total_right_octave_lifts = sum(int(measure.get("spacing_adjustments", {}).get("right_octave_lifts") or 0) for measure in arranged_measures)
    total_left_octave_drops = sum(int(measure.get("spacing_adjustments", {}).get("left_octave_drops") or 0) for measure in arranged_measures)
    return {
        "arrangement_type": "piano_solo",
        "title": title or "Untitled Piano Arrangement",
        "key": key_signature,
        "tempo": int(tempo),
        "time_signature": time_signature,
        "style": preferred_style,
        "split_point": {
            "note": "C4",
            "midi": HAND_SPLIT_POINT_MIDI,
        },
        "hand_assignment": {
            "melody_hand": "right",
            "accompaniment_hand": "left",
            "melody_target_range": {
                "low": "C4",
                "high": "C6",
                "low_midi": RIGHT_HAND_MIN_MIDI,
                "high_midi": RIGHT_HAND_MAX_MIDI,
            },
            "low_melody_threshold": {
                "note": "G3",
                "midi": LOW_MELODY_THRESHOLD_MIDI,
            },
            "rule_summary": [
                "主旋律优先固定在右手，并尽量保持在 C4-C6 的可唱奏区间。",
                "如果旋律整体过低，会优先整体上移八度再进入编配。",
                "当双手距离过近时，优先下移左手；如果左手已到下限，再上移右手以避免交叉。",
                "长音补和弦音的填充首版默认关闭，先保留清晰主旋律。",
            ],
        },
        "left_hand_pattern": texture_pattern,
        "right_hand_range_adjustment": right_hand_range,
        "spacing_strategy": {
            "minimum_gap_semitones": MIN_HAND_GAP_SEMITONES,
            "right_octave_lifts": total_right_octave_lifts,
            "left_octave_drops": total_left_octave_drops,
        },
        "long_note_chord_tone_fill": {
            "enabled": LONG_NOTE_CHORD_TONE_FILL_ENABLED,
            "reason": "初版优先保持主旋律清晰，暂不在长音上自动补和弦音。",
        },
        "chords": deepcopy(lead_sheet.get("chords") or []),
        "measures": deepcopy(lead_sheet.get("measures") or []),
        "harmonic_strategy": deepcopy(lead_sheet.get("harmonic_strategy") or {}),
        "arranged_measures": arranged_measures,
        "melody_note_count": len(melody_notes),
        "accompaniment_note_count": accompaniment_note_count,
    }
