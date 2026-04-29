"""Generate guitar chord-singing lead sheets from melody context."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from copy import deepcopy
from typing import Any

from backend.core.score.key_detection import normalize_key_signature_text
from backend.core.score.note_mapping import beats_per_measure, note_to_midi, parse_time_signature


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
QUALITY_INTERVALS = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "dim": (0, 3, 6),
    "7": (0, 4, 7, 10),
}
ROMAN_PROGRESSIONS_MAJOR = {
    None: {"I": 1.0, "vi": 0.8, "IV": 0.7, "V": 0.65},
    "I": {"V": 1.2, "vi": 0.95, "IV": 0.9, "ii": 0.75},
    "ii": {"V": 1.4, "IV": 0.8, "vi": 0.6},
    "iii": {"vi": 0.7, "IV": 0.55},
    "IV": {"I": 1.0, "V": 1.1, "ii": 0.7},
    "V": {"I": 1.6, "vi": 1.0, "IV": 0.45},
    "vi": {"IV": 1.1, "ii": 0.75, "V": 0.9},
    "vii°": {"I": 1.4, "iii": 0.4},
}
ROMAN_PROGRESSIONS_MINOR = {
    None: {"i": 1.0, "VI": 0.8, "iv": 0.75, "V": 0.7},
    "i": {"VI": 0.95, "iv": 0.9, "V": 1.15, "III": 0.7},
    "ii°": {"V": 1.45, "iv": 0.65},
    "III": {"VI": 0.8, "iv": 0.55},
    "iv": {"i": 1.05, "V": 1.15, "VII": 0.65},
    "V": {"i": 1.7, "VI": 0.75, "III": 0.5},
    "VI": {"III": 0.7, "iv": 1.05, "V": 0.8},
    "VII": {"III": 0.75, "i": 0.85},
}
OPEN_GUITAR_SHAPES = {
    "A": {"fingering": "x02220", "display_name": "A", "difficulty": "easy", "family": "open"},
    "A7": {"fingering": "x02020", "display_name": "A7", "difficulty": "easy", "family": "open"},
    "Am": {"fingering": "x02210", "display_name": "Am", "difficulty": "easy", "family": "open"},
    "B7": {"fingering": "x21202", "display_name": "B7", "difficulty": "medium", "family": "open"},
    "C": {"fingering": "x32010", "display_name": "C", "difficulty": "easy", "family": "open"},
    "C7": {"fingering": "x32310", "display_name": "C7", "difficulty": "easy", "family": "open"},
    "D": {"fingering": "xx0232", "display_name": "D", "difficulty": "easy", "family": "open"},
    "D7": {"fingering": "xx0212", "display_name": "D7", "difficulty": "easy", "family": "open"},
    "Dm": {"fingering": "xx0231", "display_name": "Dm", "difficulty": "easy", "family": "open"},
    "Dsus4": {"fingering": "xx0233", "display_name": "Dsus4", "difficulty": "easy", "family": "open"},
    "E": {"fingering": "022100", "display_name": "E", "difficulty": "easy", "family": "open"},
    "E7": {"fingering": "020100", "display_name": "E7", "difficulty": "easy", "family": "open"},
    "Em": {"fingering": "022000", "display_name": "Em", "difficulty": "easy", "family": "open"},
    "F": {"fingering": "133211", "display_name": "F", "difficulty": "medium", "family": "barre"},
    "G": {"fingering": "320003", "display_name": "G", "difficulty": "easy", "family": "open"},
    "G7": {"fingering": "320001", "display_name": "G7", "difficulty": "easy", "family": "open"},
}
BARRE_SHAPE_FALLBACKS = {
    "": {"template": "E-shape barre", "difficulty": "medium", "family": "barre"},
    "m": {"template": "Em-shape barre", "difficulty": "medium", "family": "barre"},
    "7": {"template": "E7-shape barre", "difficulty": "medium", "family": "barre"},
    "dim": {"template": "diminished grip", "difficulty": "hard", "family": "movable"},
}
STRUMMING_ARROW_MAP = {
    "D": "↓",
    "U": "↑",
    None: "·",
}
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_child_text(parent: ET.Element | None, child_name: str) -> str:
    if parent is None:
        return ""
    child = next((item for item in parent if _local_name(item.tag) == child_name), None)
    return str(child.text or "").strip() if child is not None else ""


def _note_pitch_class(note: str | None) -> int | None:
    if not note:
        return None
    midi = note_to_midi(str(note))
    if midi is None:
        return None
    return int(midi % 12)


def _pitch_class_to_name(pitch_class: int, *, prefer_flats: bool) -> str:
    names = PITCH_CLASS_TO_FLAT if prefer_flats else PITCH_CLASS_TO_SHARP
    return names[int(pitch_class) % 12]


def _key_mode(key_signature: str) -> str:
    return "minor" if key_signature.endswith("m") else "major"


def _key_root_name(key_signature: str) -> str:
    return key_signature[:-1] if key_signature.endswith("m") else key_signature


def _prefer_flats(key_signature: str) -> bool:
    return "b" in _key_root_name(key_signature)


def _build_scale_names(key_signature: str) -> list[str]:
    tonic = _key_root_name(key_signature)
    is_minor = _key_mode(key_signature) == "minor"
    tonic_pitch_class = _note_pitch_class(f"{tonic}4")
    if tonic_pitch_class is None:
        tonic_pitch_class = 0

    intervals = (0, 2, 3, 5, 7, 8, 10) if is_minor else (0, 2, 4, 5, 7, 9, 11)
    prefer_flats = _prefer_flats(key_signature)
    return [
        _pitch_class_to_name(tonic_pitch_class + interval, prefer_flats=prefer_flats)
        for interval in intervals
    ]


def _build_candidate(
    root_name: str,
    quality: str,
    roman: str,
    harmonic_function: str,
    *,
    source: str = "diatonic",
    target_roman: str | None = None,
) -> dict[str, Any] | None:
    root_pitch_class = _note_pitch_class(f"{root_name}4")
    if root_pitch_class is None:
        return None
    symbol = f"{root_name}{quality}"
    intervals = QUALITY_INTERVALS.get(quality, QUALITY_INTERVALS[""])
    return {
        "symbol": symbol,
        "roman": roman,
        "quality": quality,
        "function": harmonic_function,
        "source": source,
        "target_roman": target_roman,
        "root": root_name,
        "root_pitch_class": root_pitch_class,
        "pitch_classes": {int((root_pitch_class + interval) % 12) for interval in intervals},
    }


def _merge_palette_candidates(*candidate_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in candidate_groups:
        for candidate in group:
            symbol = str(candidate.get("symbol") or "").strip()
            if symbol and symbol not in merged:
                merged[symbol] = candidate
    return list(merged.values())


def _build_diatonic_palette(key_signature: str) -> list[dict[str, Any]]:
    normalized_key = normalize_key_signature_text(key_signature, default="C")
    scale_names = _build_scale_names(normalized_key)
    if _key_mode(normalized_key) == "minor":
        qualities = ("m", "dim", "", "m", "", "", "")
        romans = ("i", "ii°", "III", "iv", "V", "VI", "VII")
        functions = ("tonic", "predominant", "tonic", "predominant", "dominant", "tonic", "dominant")
    else:
        qualities = ("", "m", "m", "", "", "m", "dim")
        romans = ("I", "ii", "iii", "IV", "V", "vi", "vii°")
        functions = ("tonic", "predominant", "tonic", "predominant", "dominant", "tonic", "dominant")

    palette: list[dict[str, Any]] = []
    for root_name, quality, roman, harmonic_function in zip(scale_names, qualities, romans, functions):
        candidate = _build_candidate(root_name, quality, roman, harmonic_function)
        if candidate is not None:
            palette.append(candidate)

    dominant = next((candidate for candidate in palette if candidate["roman"] == "V"), None)
    if dominant is not None and dominant["quality"] == "":
        candidate = _build_candidate(
            dominant["root"],
            "7",
            dominant["roman"],
            dominant["function"],
            source="diatonic",
        )
        if candidate is not None:
            palette.append(candidate)
    return palette


def _build_secondary_dominant_palette(
    key_signature: str,
    diatonic_palette: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prefer_flats = _prefer_flats(key_signature)
    palette: list[dict[str, Any]] = []
    tonic_roman = "i" if _key_mode(key_signature) == "minor" else "I"
    for target in diatonic_palette:
        target_roman = str(target.get("roman") or "")
        if not target_roman or target_roman == tonic_roman or str(target.get("quality") or "") == "dim":
            continue
        dominant_root = _pitch_class_to_name(int(target["root_pitch_class"]) + 7, prefer_flats=prefer_flats)
        candidate = _build_candidate(
            dominant_root,
            "7",
            f"V/{target_roman}",
            "dominant",
            source="secondary_dominant",
            target_roman=target_roman,
        )
        if candidate is not None:
            palette.append(candidate)
    return palette


def _build_borrowed_palette(key_signature: str) -> list[dict[str, Any]]:
    tonic_pitch_class = _note_pitch_class(f"{_key_root_name(key_signature)}4") or 0
    base_prefer_flats = _prefer_flats(key_signature)
    borrowed_specs = (
        [
            (5, "m", "iv", "predominant"),
            (8, "", "bVI", "predominant"),
            (10, "", "bVII", "dominant"),
            (3, "", "bIII", "tonic"),
        ]
        if _key_mode(key_signature) == "major"
        else [
            (5, "", "IV", "predominant"),
            (1, "", "bII", "predominant"),
            (0, "", "I", "tonic"),
        ]
    )

    palette: list[dict[str, Any]] = []
    for interval, quality, roman, harmonic_function in borrowed_specs:
        prefer_flats = True if roman.startswith("b") else base_prefer_flats
        root_name = _pitch_class_to_name(tonic_pitch_class + interval, prefer_flats=prefer_flats)
        candidate = _build_candidate(
            root_name,
            quality,
            roman,
            harmonic_function,
            source="borrowed",
        )
        if candidate is not None:
            palette.append(candidate)
    return palette


def _build_chord_palette(key_signature: str) -> list[dict[str, Any]]:
    normalized_key = normalize_key_signature_text(key_signature, default="C")
    diatonic_palette = _build_diatonic_palette(normalized_key)
    secondary_dominants = _build_secondary_dominant_palette(normalized_key, diatonic_palette)
    borrowed_palette = _build_borrowed_palette(normalized_key)
    return _merge_palette_candidates(diatonic_palette, secondary_dominants, borrowed_palette)


def _shape_for_chord(symbol: str) -> dict[str, Any]:
    known = OPEN_GUITAR_SHAPES.get(symbol)
    if known is not None:
        return {"symbol": symbol, **deepcopy(known)}

    match = re.fullmatch(r"([A-G](?:#|b)?)(m|7|dim)?", symbol)
    if not match:
        return {
            "symbol": symbol,
            "display_name": symbol,
            "fingering": "see arranger",
            "difficulty": "medium",
            "family": "custom",
        }
    root, quality = match.groups()
    quality = quality or ""
    fallback = BARRE_SHAPE_FALLBACKS.get(quality, BARRE_SHAPE_FALLBACKS[""])
    return {
        "symbol": symbol,
        "display_name": symbol,
        "fingering": fallback["template"],
        "difficulty": fallback["difficulty"],
        "family": fallback["family"],
    }


def _resolve_slot_layout(time_signature: str) -> list[tuple[float, float]]:
    numerator, denominator = parse_time_signature(time_signature)
    total_beats = beats_per_measure(time_signature)
    if denominator == 8 and numerator >= 6 and numerator % 3 == 0:
        half = round(total_beats / 2.0, 3)
        return [(1.0, half), (1.0 + half, half)]
    if total_beats >= 4:
        half = round(total_beats / 2.0, 3)
        return [(1.0, half), (1.0 + half, half)]
    return [(1.0, total_beats)]


def _normalize_melody(
    melody: list[dict[str, Any]],
    *,
    time_signature: str,
    tempo: int,
) -> list[dict[str, Any]]:
    total_beats = beats_per_measure(time_signature)
    normalized: list[dict[str, Any]] = []
    for item in melody:
        pitch = str(item.get("pitch") or item.get("note") or "").strip()
        if not pitch or pitch == "Rest":
            continue

        beats = float(item.get("beats") or 0.0)
        if beats <= 0:
            duration_seconds = float(item.get("duration") or 0.0)
            beats = duration_seconds * tempo / 60 if duration_seconds > 0 else 1.0

        measure_no = item.get("measure_no")
        start_beat = item.get("start_beat")
        if measure_no is None or start_beat is None:
            time_seconds = float(item.get("time") or item.get("start") or 0.0)
            absolute_beats = time_seconds * tempo / 60.0
            measure_no = int(absolute_beats // total_beats) + 1
            start_beat = round(absolute_beats % total_beats + 1.0, 3)

        normalized.append(
            {
                "measure_no": max(int(measure_no), 1),
                "start_beat": max(float(start_beat), 1.0),
                "beats": round(max(beats, 0.25), 3),
                "pitch": pitch,
            }
        )
    return normalized


def _slot_note_windows(
    melody: list[dict[str, Any]],
    *,
    time_signature: str,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    highest_measure = 0
    for item in melody:
        measure_no = max(int(item.get("measure_no") or 1), 1)
        highest_measure = max(highest_measure, measure_no)
        grouped[measure_no].append(dict(item))

    slot_layout = _resolve_slot_layout(time_signature)
    slots: list[dict[str, Any]] = []
    for measure_no in range(1, max(highest_measure, 1) + 1):
        measure_notes = grouped.get(measure_no, [])
        for start_beat, slot_beats in slot_layout:
            slot_end = round(start_beat + slot_beats, 3)
            slot_notes: list[dict[str, Any]] = []
            for note in measure_notes:
                note_start = float(note.get("start_beat") or 1.0)
                note_end = note_start + max(float(note.get("beats") or 0.0), 0.0)
                overlap = round(min(slot_end, note_end) - max(start_beat, note_start), 3)
                if overlap <= 0:
                    continue
                note_pitch_class = _note_pitch_class(str(note.get("pitch") or ""))
                if note_pitch_class is None:
                    continue
                slot_notes.append(
                    {
                        **note,
                        "pitch_class": note_pitch_class,
                        "weight": overlap,
                    }
                )
            slots.append(
                {
                    "measure_no": measure_no,
                    "start_beat": start_beat,
                    "beats": slot_beats,
                    "notes": slot_notes,
                }
            )
    return slots


def _progression_bonus(previous_roman: str | None, current_roman: str, *, mode: str) -> float:
    table = ROMAN_PROGRESSIONS_MINOR if mode == "minor" else ROMAN_PROGRESSIONS_MAJOR
    return float(table.get(previous_roman, {}).get(current_roman, 0.0))


def _normalize_progression_roman(roman: str | None) -> str | None:
    if not roman:
        return None
    if roman.startswith("V/"):
        return "V"
    if roman in {"bIII", "III"}:
        return "III"
    if roman in {"bVI", "VI"}:
        return "VI"
    if roman in {"bVII", "VII"}:
        return "VII"
    if roman == "bII":
        return "ii"
    return roman


def _build_segment_contexts(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not slots:
        return []

    segment_slot_indexes: dict[int, list[int]] = defaultdict(list)
    segment_pitch_totals: dict[int, dict[int, float]] = defaultdict(dict)
    highest_segment = 1
    for index, slot in enumerate(slots):
        segment_no = int((int(slot.get("measure_no") or 1) - 1) // 4) + 1
        highest_segment = max(highest_segment, segment_no)
        segment_slot_indexes[segment_no].append(index)
        for note in slot.get("notes") or []:
            pitch_class = int(note.get("pitch_class") or 0)
            weight = float(note.get("weight") or 0.0)
            segment_pitch_totals[segment_no][pitch_class] = segment_pitch_totals[segment_no].get(pitch_class, 0.0) + weight

    contexts: list[dict[str, Any]] = []
    for index, slot in enumerate(slots):
        segment_no = int((int(slot.get("measure_no") or 1) - 1) // 4) + 1
        segment_indexes = segment_slot_indexes.get(segment_no) or [index]
        slot_position = segment_indexes.index(index)
        totals = segment_pitch_totals.get(segment_no) or {}
        weight_sum = sum(totals.values()) or 1.0
        normalized_totals = {
            pitch_class: weight / weight_sum
            for pitch_class, weight in totals.items()
        }
        contexts.append(
            {
                "segment_no": segment_no,
                "segment_size": len(segment_indexes),
                "slot_position": slot_position,
                "is_start": slot_position == 0,
                "is_end": slot_position == len(segment_indexes) - 1,
                "is_final_segment": segment_no == highest_segment,
                "pitch_class_weights": normalized_totals,
            }
        )
    return contexts


def _fallback_tonic_candidate(key_signature: str) -> dict[str, Any]:
    tonic_roman = "i" if _key_mode(key_signature) == "minor" else "I"
    candidate = _build_candidate(
        _key_root_name(key_signature),
        "m" if tonic_roman == "i" else "",
        tonic_roman,
        "tonic",
        source="fallback",
    )
    if candidate is None:
        return {
            "symbol": key_signature,
            "roman": tonic_roman,
            "quality": "",
            "function": "tonic",
            "source": "fallback",
            "target_roman": None,
            "root": _key_root_name(key_signature),
            "root_pitch_class": _note_pitch_class(f"{_key_root_name(key_signature)}4") or 0,
            "pitch_classes": set(),
        }
    return candidate


def _note_support_score(notes: list[dict[str, Any]], candidate: dict[str, Any]) -> float:
    score = 0.0
    for note in notes:
        weight = float(note.get("weight") or 0.0)
        pitch_class = int(note["pitch_class"])
        if pitch_class == candidate["root_pitch_class"]:
            score += 2.45 * weight
        elif pitch_class in candidate["pitch_classes"]:
            score += 1.75 * weight
        elif candidate.get("source") == "secondary_dominant" and (pitch_class - candidate["root_pitch_class"]) % 12 in {1, 11}:
            score += 0.4 * weight
        else:
            score -= 0.9 * weight
    return score


def _score_chord_candidate(
    slot: dict[str, Any],
    *,
    candidate: dict[str, Any],
    key_signature: str,
    segment_context: dict[str, Any],
) -> float:
    mode = _key_mode(key_signature)
    tonic_roman = "i" if mode == "minor" else "I"
    notes = list(slot.get("notes") or [])
    score = _note_support_score(notes, candidate)

    segment_weights = segment_context.get("pitch_class_weights") or {}
    segment_support = sum(
        float(segment_weights.get(pitch_class) or 0.0)
        for pitch_class in candidate.get("pitch_classes") or set()
    )
    score += 0.42 * segment_support
    score += 0.2 * float(segment_weights.get(candidate["root_pitch_class"]) or 0.0)

    if not notes and candidate.get("source") == "diatonic":
        score += 0.15
    if slot["start_beat"] == 1.0 and candidate["function"] == "tonic":
        score += 0.3
    if slot["start_beat"] > 1.0 and candidate["function"] == "dominant":
        score += 0.14

    if segment_context.get("is_start"):
        if candidate["function"] == "tonic":
            score += 0.42
        elif candidate["function"] == "predominant":
            score += 0.16

    if segment_context.get("is_end"):
        if segment_context.get("is_final_segment"):
            if candidate["roman"] == tonic_roman:
                score += 1.2
            elif candidate["function"] == "dominant":
                score += 0.15
        else:
            if candidate["function"] == "dominant":
                score += 0.48
            if candidate.get("source") == "secondary_dominant":
                score += 0.28

    if candidate.get("source") == "borrowed":
        score -= 0.12
        if segment_support > 0.45:
            score += 0.1
    if candidate.get("source") == "secondary_dominant":
        score -= 0.08
    return score


def _score_chord_transition(
    previous_chord: dict[str, Any],
    current_chord: dict[str, Any],
    *,
    mode: str,
    same_segment: bool,
) -> float:
    score = _progression_bonus(
        _normalize_progression_roman(previous_chord.get("roman")),
        _normalize_progression_roman(current_chord.get("roman")),
        mode=mode,
    )

    if previous_chord["symbol"] == current_chord["symbol"]:
        score += 0.7
    elif same_segment:
        score -= 0.08

    if previous_chord["function"] == "dominant" and current_chord["function"] == "tonic":
        score += 0.38
    if previous_chord.get("source") == "secondary_dominant" and previous_chord.get("target_roman") == current_chord.get("roman"):
        score += 1.35
    if previous_chord.get("source") == "borrowed" and current_chord["function"] in {"dominant", "tonic"}:
        score += 0.18
    if previous_chord.get("source") == "borrowed" and current_chord.get("source") == "borrowed":
        score -= 0.42

    root_motion = (int(current_chord["root_pitch_class"]) - int(previous_chord["root_pitch_class"])) % 12
    if root_motion in {5, 7}:
        score += 0.18
    elif root_motion in {1, 11}:
        score -= 0.06
    return score


def _choose_chords_for_slots(
    slots: list[dict[str, Any]],
    *,
    palette: list[dict[str, Any]],
    key_signature: str,
) -> list[dict[str, Any]]:
    if not slots:
        return []

    candidates = palette or [_fallback_tonic_candidate(key_signature)]
    contexts = _build_segment_contexts(slots)
    mode = _key_mode(key_signature)

    candidate_scores: list[list[float]] = [
        [
            _score_chord_candidate(slot, candidate=candidate, key_signature=key_signature, segment_context=contexts[index])
            for candidate in candidates
        ]
        for index, slot in enumerate(slots)
    ]

    dynamic_scores: list[list[float]] = [[candidate_scores[0][index] for index in range(len(candidates))]]
    backpointers: list[list[int]] = [[-1 for _ in candidates]]

    for slot_index in range(1, len(slots)):
        slot_scores: list[float] = []
        slot_backpointer: list[int] = []
        same_segment = contexts[slot_index]["segment_no"] == contexts[slot_index - 1]["segment_no"]
        for candidate_index, candidate in enumerate(candidates):
            best_score = float("-inf")
            best_previous_index = 0
            base_score = candidate_scores[slot_index][candidate_index]
            for previous_index, previous_candidate in enumerate(candidates):
                transition_score = _score_chord_transition(
                    previous_candidate,
                    candidate,
                    mode=mode,
                    same_segment=same_segment,
                )
                total = dynamic_scores[-1][previous_index] + transition_score + base_score
                if total > best_score:
                    best_score = total
                    best_previous_index = previous_index
            slot_scores.append(best_score)
            slot_backpointer.append(best_previous_index)
        dynamic_scores.append(slot_scores)
        backpointers.append(slot_backpointer)

    final_index = max(range(len(candidates)), key=lambda index: dynamic_scores[-1][index])
    chosen_indexes = [final_index]
    for slot_index in range(len(slots) - 1, 0, -1):
        final_index = backpointers[slot_index][final_index]
        chosen_indexes.append(final_index)
    chosen_indexes.reverse()
    return [candidates[index] for index in chosen_indexes]


def _group_slots_into_measures(chords: list[dict[str, Any]], *, time_signature: str) -> list[dict[str, Any]]:
    total_beats = beats_per_measure(time_signature)
    measures: dict[int, dict[str, Any]] = {}
    for chord in chords:
        measure_no = int(chord["measure_no"])
        measure = measures.setdefault(
            measure_no,
            {
                "measure_no": measure_no,
                "beats": total_beats,
                "chords": [],
            },
        )
        measure["chords"].append(chord)
    return [measures[index] for index in sorted(measures)]


def _measure_cadence_type(measure: dict[str, Any]) -> str:
    chords = list(measure.get("chords") or [])
    if not chords:
        return "open"
    last_chord = chords[-1]
    if last_chord.get("function") == "tonic":
        return "resolved"
    if last_chord.get("function") == "dominant":
        return "half"
    if any(chord.get("source") == "secondary_dominant" for chord in chords):
        return "applied"
    return "open"


def _section_label(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index <= len(alphabet):
        return alphabet[index - 1]
    quotient, remainder = divmod(index - 1, len(alphabet))
    return f"{alphabet[quotient - 1]}{alphabet[remainder]}"


def _target_measures_per_line(time_signature: str, total_measures: int) -> int:
    numerator, denominator = parse_time_signature(time_signature)
    if total_measures <= 2:
        return total_measures or 1
    if denominator == 8 and numerator >= 6 and numerator % 3 == 0:
        return 2 if total_measures <= 6 else 4
    if time_signature == "3/4":
        return 2 if total_measures <= 8 else 4
    return 4


def _build_display_lines(measures: list[dict[str, Any]], *, time_signature: str) -> list[dict[str, Any]]:
    if not measures:
        return []

    target_size = _target_measures_per_line(time_signature, len(measures))
    lines: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    line_no = 1

    for index, measure in enumerate(measures):
        current.append(measure)
        cadence = _measure_cadence_type(measure)
        at_last_measure = index == len(measures) - 1
        reached_target = len(current) >= target_size
        cadence_break = len(current) >= max(target_size - 1, 1) and cadence in {"resolved", "half"}
        overflow_break = len(current) >= max(target_size + 1, 2)
        if not (at_last_measure or reached_target or cadence_break or overflow_break):
            continue

        line_measures = list(current)
        lines.append(
            {
                "line_no": line_no,
                "line_label": f"第 {line_no} 行",
                "measure_start": int(line_measures[0]["measure_no"]),
                "measure_end": int(line_measures[-1]["measure_no"]),
                "measure_count": len(line_measures),
                "cadence": _measure_cadence_type(line_measures[-1]),
                "measures": line_measures,
            }
        )
        current = []
        line_no += 1

    return lines


def _build_sections(
    lines: list[dict[str, Any]],
    *,
    time_signature: str,
) -> list[dict[str, Any]]:
    if not lines:
        return []

    target_section_measures = 8 if _target_measures_per_line(time_signature, 8) >= 4 else 4
    sections: list[dict[str, Any]] = []
    current_lines: list[dict[str, Any]] = []
    section_no = 1

    for index, line in enumerate(lines):
        current_lines.append(line)
        measure_count = sum(int(item.get("measure_count") or 0) for item in current_lines)
        at_last_line = index == len(lines) - 1
        cadence = str(line.get("cadence") or "open")
        cadence_break = len(current_lines) >= 2 and cadence in {"resolved", "half"}
        reached_target = measure_count >= target_section_measures
        overflow_break = measure_count >= target_section_measures + 4
        if not (at_last_line or cadence_break or reached_target or overflow_break):
            continue

        start_measure = int(current_lines[0]["measure_start"])
        end_measure = int(current_lines[-1]["measure_end"])
        section_label = _section_label(section_no)
        sections.append(
            {
                "section_no": section_no,
                "section_label": section_label,
                "section_title": f"段落 {section_label}",
                "measure_start": start_measure,
                "measure_end": end_measure,
                "measure_count": end_measure - start_measure + 1,
                "line_start": int(current_lines[0]["line_no"]),
                "line_end": int(current_lines[-1]["line_no"]),
                "cadence": cadence,
                "lines": current_lines,
            }
        )
        current_lines = []
        section_no += 1

    return sections


def _build_display_line_tokens(measures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for measure_index, measure in enumerate(measures):
        measure_no = int(measure.get("measure_no") or (measure_index + 1))
        tokens.append({"type": "bar", "measure_no": measure_no})
        chords = list(measure.get("chords") or [])
        if not chords:
            tokens.append({"type": "spacer", "measure_no": measure_no, "width": "measure"})
        else:
            for chord_index, chord in enumerate(chords):
                tokens.append(
                    {
                        "type": "chord",
                        "symbol": chord.get("symbol"),
                        "measure_no": int(chord.get("measure_no") or measure_no),
                        "beat_in_measure": float(chord.get("beat_in_measure") or 1.0),
                        "source": chord.get("source") or "diatonic",
                    }
                )
                if chord_index < len(chords) - 1:
                    tokens.append({"type": "spacer", "measure_no": measure_no, "width": "beat"})
    return tokens


def _normalize_display_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_lines: list[dict[str, Any]] = []
    for line in lines:
        measures = list(line.get("measures") or [])
        normalized_lines.append(
            {
                "line_no": int(line.get("line_no") or (len(normalized_lines) + 1)),
                "line_label": line.get("line_label") or f"第 {len(normalized_lines) + 1} 行",
                "measure_start": int(line.get("measure_start") or (measures[0]["measure_no"] if measures else 1)),
                "measure_end": int(line.get("measure_end") or (measures[-1]["measure_no"] if measures else 1)),
                "measure_count": int(line.get("measure_count") or len(measures)),
                "cadence": line.get("cadence") or "open",
                "measures": measures,
                "tokens": _build_display_line_tokens(measures),
            }
        )
    return normalized_lines


def _parse_chord_symbol(symbol: str) -> tuple[str, str]:
    match = re.fullmatch(r"([A-G](?:#|b)?)(.*)", symbol)
    if not match:
        return symbol, ""
    return match.group(1), match.group(2)


def _transpose_chord_symbol(symbol: str, semitones: int, *, prefer_flats: bool) -> str:
    root, suffix = _parse_chord_symbol(symbol)
    pitch_class = NOTE_NAME_TO_PITCH_CLASS.get(root)
    if pitch_class is None:
        return symbol
    transposed_root = _pitch_class_to_name(pitch_class - semitones, prefer_flats=prefer_flats)
    return f"{transposed_root}{suffix}"


def _suggest_capo(chords: list[dict[str, Any]], *, key_signature: str) -> dict[str, Any]:
    if not chords:
        return {"capo": 0, "transposed_key": key_signature, "open_chord_ratio": 1.0}

    prefer_flats = _prefer_flats(key_signature)
    best = {"capo": 0, "score": -1.0, "transposed_key": key_signature, "open_chord_ratio": 0.0}
    total = len(chords)
    for capo in range(0, 6):
        open_hits = 0
        for chord in chords:
            transposed = _transpose_chord_symbol(str(chord["symbol"]), capo, prefer_flats=prefer_flats)
            if transposed in OPEN_GUITAR_SHAPES:
                open_hits += 1
        ratio = open_hits / total if total else 0.0
        weighted_score = ratio - capo * 0.03
        if weighted_score > best["score"]:
            transposed_key = _transpose_chord_symbol(key_signature, capo, prefer_flats=prefer_flats)
            best = {
                "capo": capo,
                "score": weighted_score,
                "transposed_key": transposed_key,
                "open_chord_ratio": round(ratio, 2),
            }
    return {key: value for key, value in best.items() if key != "score"}


def _normalize_strumming_style(style: str) -> str:
    normalized = (style or "pop").strip().lower()
    if any(token in normalized for token in ("folk", "ballad", "acoustic", "民谣", "弹唱", "抒情")):
        return "folk"
    if any(token in normalized for token in ("rock", "band", "摇滚", "乐队")):
        return "rock"
    return "pop"


def _counting_slots_for_meter(time_signature: str, slot_count: int) -> list[str]:
    numerator, denominator = parse_time_signature(time_signature)
    if denominator == 8 and numerator % 3 == 0 and slot_count == numerator:
        counting: list[str] = []
        for beat in range(1, numerator // 3 + 1):
            counting.extend([str(beat), "la", "li"])
        return counting
    if denominator == 4 and slot_count == numerator * 2:
        counting = []
        for beat in range(1, numerator + 1):
            counting.extend([str(beat), "&"])
        return counting
    if slot_count == 6:
        return ["1", "&", "2", "&", "3", "&"]
    return ["1", "&", "2", "&", "3", "&", "4", "&"][:slot_count]


def _accent_indices_for_meter(time_signature: str, slot_count: int) -> set[int]:
    numerator, denominator = parse_time_signature(time_signature)
    if denominator == 8 and numerator % 3 == 0 and slot_count == numerator:
        return {index * 3 for index in range(max(numerator // 3, 1))}
    if denominator == 4 and slot_count == numerator * 2:
        accents = {0}
        if numerator >= 4:
            accents.add(4)
        return accents
    if slot_count >= 8:
        return {0, 4}
    return {0}


def _stroke_display(stroke: str | None) -> str:
    return STRUMMING_ARROW_MAP.get(stroke, STRUMMING_ARROW_MAP[None])


def _build_strumming_pattern_payload(
    *,
    role: str,
    role_label: str,
    pattern: str,
    slots: list[str | None],
    description: str,
    difficulty: str,
    feel: str,
    time_signature: str,
    practice_tip: str,
) -> dict[str, Any]:
    counting_slots = _counting_slots_for_meter(time_signature, len(slots))
    accent_indices = _accent_indices_for_meter(time_signature, len(slots))
    stroke_grid = [
        {
            "index": index,
            "count": counting_slots[index] if index < len(counting_slots) else str(index + 1),
            "stroke": stroke,
            "display_stroke": _stroke_display(stroke),
            "accent": index in accent_indices,
        }
        for index, stroke in enumerate(slots)
    ]
    return {
        "role": role,
        "role_label": role_label,
        "pattern": pattern,
        "display_pattern": " ".join(_stroke_display(stroke) for stroke in slots),
        "counting": " ".join(item["count"] for item in stroke_grid),
        "stroke_grid": stroke_grid,
        "description": description,
        "difficulty": difficulty,
        "feel": feel,
        "practice_tip": practice_tip,
    }


def _base_strumming_patterns(style: str, time_signature: str, tempo: int) -> dict[str, dict[str, Any]]:
    style_family = _normalize_strumming_style(style)
    if time_signature == "3/4":
        return {
            "global": _build_strumming_pattern_payload(
                role="base",
                role_label="基础型",
                pattern="D - DU",
                slots=["D", None, None, None, "D", "U"],
                description="适合三拍民谣/华尔兹，先稳住第 1 拍，再把句尾轻轻带起。",
                difficulty="easy",
                feel="waltz",
                time_signature=time_signature,
                practice_tip="先把第 1 拍扫稳，再让第 3 拍的上扬把旋律托起来。",
            ),
            "verse": _build_strumming_pattern_payload(
                role="verse",
                role_label="主歌",
                pattern="D - DU",
                slots=["D", None, None, None, "D", "U"],
                description="主歌保持留白，让人声更靠前。",
                difficulty="easy",
                feel="waltz_verse",
                time_signature=time_signature,
                practice_tip="第 2 拍先留空，句尾再轻轻提起，听感会更像弹唱伴奏。",
            ),
            "chorus": _build_strumming_pattern_payload(
                role="chorus",
                role_label="副歌",
                pattern="D - D - DU",
                slots=["D", None, "D", None, "D", "U"],
                description="副歌把三拍都带起来，推进感会更明显。",
                difficulty="medium",
                feel="waltz_chorus",
                time_signature=time_signature,
                practice_tip="副歌把第 2 拍也带出来，但不要压过主旋律。",
            ),
        }

    if style_family == "rock":
        return {
            "global": _build_strumming_pattern_payload(
                role="base",
                role_label="基础型",
                pattern="D DU DUDU",
                slots=["D", None, "D", "U", "D", "U", "D", "U"],
                description="更有推进力的流行摇滚扫弦，适合先把整首歌扫顺。",
                difficulty="medium",
                feel="driving_pop",
                time_signature=time_signature,
                practice_tip="先抓住第 1 拍和第 3 拍，再把后半拍扫匀。",
            ),
            "verse": _build_strumming_pattern_payload(
                role="verse",
                role_label="主歌",
                pattern="D DU DUDU",
                slots=["D", None, "D", "U", "D", "U", "D", "U"],
                description="主歌先保持稳步推进，不要扫得太满。",
                difficulty="medium",
                feel="rock_verse",
                time_signature=time_signature,
                practice_tip="下拍更明显一点，上拍不要过重，旋律会更清楚。",
            ),
            "chorus": _build_strumming_pattern_payload(
                role="chorus",
                role_label="副歌",
                pattern="DUDUDUDU",
                slots=["D", "U", "D", "U", "D", "U", "D", "U"],
                description="副歌连续 8 分扫弦更容易把能量顶起来。",
                difficulty="medium",
                feel="rock_chorus",
                time_signature=time_signature,
                practice_tip="副歌把上下拍扫匀，情绪起来就够，不必再额外加花。",
            ),
        }

    global_pattern = _build_strumming_pattern_payload(
        role="base",
        role_label="基础型",
        pattern="D DU UDU",
        slots=["D", None, "D", "U", None, "U", "D", "U"],
        description="适合流行/民谣弹唱的基础 8 分扫弦，先用它把整首歌扫顺最稳。",
        difficulty="easy",
        feel="steady_pop",
        time_signature=time_signature,
        practice_tip="先把第 1 拍和第 3 拍扫稳，空拍留给歌声，整首歌都会更顺。",
    )
    verse_pattern = _build_strumming_pattern_payload(
        role="verse",
        role_label="主歌",
        pattern="D DU UDU",
        slots=["D", None, "D", "U", None, "U", "D", "U"],
        description="主歌保留呼吸感，适合把旋律线条托住。",
        difficulty="easy",
        feel="verse_pop",
        time_signature=time_signature,
        practice_tip="第 2 拍和第 3 拍中间先留一点空，弹唱会更松。",
    )
    chorus_pattern = _build_strumming_pattern_payload(
        role="chorus",
        role_label="副歌",
        pattern="D DU DUDU",
        slots=["D", None, "D", "U", "D", "U", "D", "U"],
        description="副歌把后半小节填满一点，推进感会更强。",
        difficulty="medium" if int(tempo or 0) >= 118 else "easy",
        feel="chorus_pop",
        time_signature=time_signature,
        practice_tip="副歌把第 3、4 拍扫得更连一些，情绪会更容易立起来。",
    )
    return {
        "global": global_pattern,
        "verse": verse_pattern,
        "chorus": chorus_pattern,
    }


def _build_section_strumming_patterns(
    sections: list[dict[str, Any]],
    *,
    style: str,
    time_signature: str,
    tempo: int,
) -> list[dict[str, Any]]:
    templates = _base_strumming_patterns(style, time_signature, tempo)
    total_sections = len(sections)
    role_counts = {"verse": 0, "chorus": 0}
    section_patterns: list[dict[str, Any]] = []

    for index, section in enumerate(sections):
        section_role = "verse" if total_sections <= 1 or index % 2 == 0 else "chorus"
        role_counts[section_role] += 1
        template = deepcopy(templates.get(section_role) or templates["global"])
        role_label = "主歌" if section_role == "verse" else "副歌"
        template["section_role"] = section_role
        template["section_role_label"] = role_label
        template["section_title"] = (
            role_label
            if total_sections <= 1
            else f"{role_label} {role_counts[section_role]}"
        )
        template["section_label"] = section.get("section_label")
        template["source_section_title"] = section.get("section_title")
        template["measure_start"] = int(section.get("measure_start") or 1)
        template["measure_end"] = int(section.get("measure_end") or template["measure_start"])
        template["measure_count"] = int(section.get("measure_count") or (template["measure_end"] - template["measure_start"] + 1))
        template["cadence"] = section.get("cadence")
        section_patterns.append(template)

    if not section_patterns:
        global_pattern = deepcopy(templates["global"])
        global_pattern["section_role"] = "verse"
        global_pattern["section_role_label"] = "主歌"
        global_pattern["section_title"] = "主歌"
        global_pattern["measure_start"] = 1
        global_pattern["measure_end"] = 1
        global_pattern["measure_count"] = 1
        global_pattern["cadence"] = "open"
        section_patterns.append(global_pattern)

    return section_patterns


def _suggest_strumming_pattern(
    style: str,
    time_signature: str,
    tempo: int,
    *,
    sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    templates = _base_strumming_patterns(style, time_signature, tempo)
    global_pattern = deepcopy(templates["global"])
    global_pattern["section_patterns"] = _build_section_strumming_patterns(
        sections or [],
        style=style,
        time_signature=time_signature,
        tempo=tempo,
    )
    return global_pattern


def _build_display_sections(
    sections: list[dict[str, Any]],
    *,
    style: str,
    time_signature: str,
    tempo: int,
) -> list[dict[str, Any]]:
    display_sections: list[dict[str, Any]] = []
    section_patterns = _build_section_strumming_patterns(
        sections,
        style=style,
        time_signature=time_signature,
        tempo=tempo,
    )
    for index, section in enumerate(sections):
        pattern = section_patterns[index] if index < len(section_patterns) else None
        display_lines = _normalize_display_lines(list(section.get("lines") or []))
        display_sections.append(
            {
                "section_no": int(section.get("section_no") or (index + 1)),
                "section_label": section.get("section_label") or _section_label(index + 1),
                "section_title": (pattern or {}).get("section_title") or section.get("section_title") or f"段落 {_section_label(index + 1)}",
                "section_role": (pattern or {}).get("section_role") or "verse",
                "measure_start": int(section.get("measure_start") or (display_lines[0]["measure_start"] if display_lines else 1)),
                "measure_end": int(section.get("measure_end") or (display_lines[-1]["measure_end"] if display_lines else 1)),
                "measure_count": int(section.get("measure_count") or sum(int(line.get("measure_count") or 0) for line in display_lines)),
                "cadence": section.get("cadence") or (display_lines[-1]["cadence"] if display_lines else "open"),
                "lines": display_lines,
                "display_lines": display_lines,
            }
        )
    return display_sections


def _build_chord_diagrams(
    chosen_chords: list[dict[str, Any]],
    unique_shapes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = {}
    for index, chord in enumerate(chosen_chords):
        symbol = str(chord.get("symbol") or "").strip()
        if not symbol:
            continue
        item = usage.setdefault(
            symbol,
            {
                "use_count": 0,
                "first_index": index,
                "first_measure": int(chord.get("measure_no") or 1),
                "source": chord.get("source") or "diatonic",
            },
        )
        item["use_count"] += 1
        item["first_measure"] = min(int(item["first_measure"]), int(chord.get("measure_no") or item["first_measure"]))

    diagrams: list[dict[str, Any]] = []
    for symbol, shape in unique_shapes.items():
        stats = usage.get(symbol, {})
        diagrams.append(
            {
                "symbol": symbol,
                **deepcopy(shape),
                "use_count": int(stats.get("use_count") or 0),
                "first_measure": int(stats.get("first_measure") or 1),
                "source": stats.get("source") or "diatonic",
            }
        )

    diagrams.sort(key=lambda item: (-int(item.get("use_count") or 0), int(item.get("first_measure") or 1), str(item.get("symbol") or "")))
    return diagrams


def _extract_user_techniques(note_el: "ET.Element") -> list[str]:
    """Read user-set MusicXML <notations> on a <note> element and return a
    canonical list of technique tags. These tags are honored by the
    guzheng/dizi pipelines (see ``_technique_tags`` in each notation module)
    so that manual edits made in the frontend round-trip into the final
    LilyPond/PDF export.

    Tags use the same vocabulary as the heuristic "*候选" tags so the export
    label-mapping table stays uniform; "user_*" prefix marks them as
    user-asserted (not heuristic) and lets the merge step give them priority.
    """
    notations = next((item for item in note_el if _local_name(item.tag) == "notations"), None)
    if notations is None:
        return []
    tags: list[str] = []
    for child in notations:
        local = _local_name(child.tag)
        if local == "ornaments":
            for orn in child:
                orn_local = _local_name(orn.tag)
                if orn_local == "trill-mark":
                    tags.append("user_trill")
                elif orn_local in {"mordent", "inverted-mordent"}:
                    tags.append("user_mordent")
                elif orn_local == "tremolo":
                    tags.append("user_tremolo")
        elif local == "technical":
            for tech in child:
                tech_local = _local_name(tech.tag)
                if tech_local == "harmonic":
                    tags.append("user_harmonic")
        elif local == "articulations":
            for art in child:
                art_local = _local_name(art.tag)
                if art_local == "staccato":
                    tags.append("user_staccato")
                elif art_local == "accent":
                    tags.append("user_accent")
        elif local in {"glissando", "slide"}:
            tags.append("user_glissando")
    return tags


def extract_lead_sheet_source_from_musicxml(musicxml: str) -> dict[str, Any]:
    root = ET.fromstring(musicxml.encode("utf-8"))
    part = next((child for child in root if _local_name(child.tag) == "part"), None)
    if part is None:
        return {"melody": []}

    melody: list[dict[str, Any]] = []
    lyric_events: list[dict[str, Any]] = []
    current_divisions = 8
    for fallback_index, measure in enumerate(part, start=1):
        if _local_name(measure.tag) != "measure":
            continue
        measure_no = int(measure.attrib.get("number") or fallback_index)
        cursor_by_staff: dict[str, float] = defaultdict(float)
        for child in measure:
            tag = _local_name(child.tag)
            if tag == "attributes":
                divisions = next((item for item in child if _local_name(item.tag) == "divisions"), None)
                if divisions is not None and (divisions.text or "").strip().isdigit():
                    current_divisions = max(int(divisions.text.strip()), 1)
                continue
            if tag != "note":
                continue

            staff_no = _first_child_text(child, "staff") or "1"
            duration_el = next((item for item in child if _local_name(item.tag) == "duration"), None)
            duration = float(duration_el.text or 0.0) if duration_el is not None else 0.0
            beats = round(duration / current_divisions, 3) if duration > 0 else 0.0
            is_chord_tone = any(_local_name(item.tag) == "chord" for item in child)
            cursor = float(cursor_by_staff.get(staff_no, 0.0))
            if not is_chord_tone:
                start_divisions = cursor
                cursor_by_staff[staff_no] = cursor + duration
            else:
                start_divisions = max(cursor - duration, 0.0)
            if any(_local_name(item.tag) == "rest" for item in child):
                continue
            if staff_no != "1":
                continue

            pitch_el = next((item for item in child if _local_name(item.tag) == "pitch"), None)
            if pitch_el is None:
                continue
            step = _first_child_text(pitch_el, "step") or "C"
            alter_text = _first_child_text(pitch_el, "alter") or "0"
            octave = _first_child_text(pitch_el, "octave") or "4"
            alter = int(float(alter_text or 0))
            accidental = "#" if alter == 1 else "b" if alter == -1 else ""
            user_techniques = _extract_user_techniques(child)
            melody.append(
                {
                    "measure_no": measure_no,
                    "start_beat": round(start_divisions / current_divisions + 1.0, 3),
                    "beats": beats,
                    "pitch": f"{step}{accidental}{octave}",
                    "user_techniques": user_techniques,
                }
            )
    return {"melody": melody}


def extract_melody_from_musicxml(musicxml: str) -> list[dict[str, Any]]:
    return list(extract_lead_sheet_source_from_musicxml(musicxml).get("melody") or [])


def generate_guitar_lead_sheet(
    *,
    key: str,
    tempo: int,
    style: str,
    melody: list[dict[str, Any]],
    time_signature: str = "4/4",
    title: str | None = None,
    lyric_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_key = normalize_key_signature_text(key, default="C")
    normalized_melody = _normalize_melody(melody, time_signature=time_signature, tempo=tempo)
    palette = _build_chord_palette(normalized_key)
    slots = _slot_note_windows(normalized_melody, time_signature=time_signature)
    chosen_chords: list[dict[str, Any]] = []
    chosen_candidates = _choose_chords_for_slots(slots, palette=palette, key_signature=normalized_key)

    for slot, chosen in zip(slots, chosen_candidates):
        chord_entry = {
            "measure_no": int(slot["measure_no"]),
            "beat_in_measure": float(slot["start_beat"]),
            "beats": float(slot["beats"]),
            "time": round(
                (
                    (int(slot["measure_no"]) - 1) * beats_per_measure(time_signature)
                    + (float(slot["start_beat"]) - 1.0)
                )
                * 60.0
                / max(int(tempo), 1),
                3,
            ),
            "symbol": chosen["symbol"],
            "roman": chosen["roman"],
            "function": chosen["function"],
            "source": chosen.get("source", "diatonic"),
            "target_roman": chosen.get("target_roman"),
            "shape": _shape_for_chord(chosen["symbol"]),
            "melody_notes": [str(note["pitch"]) for note in slot["notes"]],
        }
        chosen_chords.append(chord_entry)

    unique_shapes = {
        chord["symbol"]: deepcopy(chord["shape"])
        for chord in chosen_chords
    }
    measures = _group_slots_into_measures(chosen_chords, time_signature=time_signature)
    display_lines = _normalize_display_lines(_build_display_lines(measures, time_signature=time_signature))
    sections = _build_sections(display_lines, time_signature=time_signature)
    capo_suggestion = _suggest_capo(chosen_chords, key_signature=normalized_key)
    strumming_pattern = _suggest_strumming_pattern(
        style,
        time_signature,
        int(tempo),
        sections=sections,
    )
    display_sections = _build_display_sections(
        sections,
        style=style,
        time_signature=time_signature,
        tempo=int(tempo),
    )
    chord_diagrams = _build_chord_diagrams(chosen_chords, unique_shapes)

    return {
        "lead_sheet_type": "guitar_chord_chart",
        "title": title or "Untitled Guitar Lead Sheet",
        "artist": "",
        "subtitle": "Generated Lead Sheet",
        "key": normalized_key,
        "tempo": int(tempo),
        "time_signature": time_signature,
        "style": style,
        "layout_mode": "screen",
        "melody_size": len(normalized_melody),
        "chords": chosen_chords,
        "measures": measures,
        "display_lines": display_lines,
        "sections": sections,
        "display_sections": display_sections,
        "guitar_shapes": unique_shapes,
        "chord_diagrams": chord_diagrams,
        "capo_suggestion": capo_suggestion,
        "strumming_pattern": strumming_pattern,
        "harmonic_strategy": {
            "secondary_dominants_enabled": True,
            "borrowed_chords_enabled": True,
            "segment_smoothing_enabled": True,
        },
    }


def generate_guitar_lead_sheet_from_musicxml(
    *,
    musicxml: str,
    key: str,
    tempo: int,
    style: str,
    time_signature: str = "4/4",
    title: str | None = None,
) -> dict[str, Any]:
    source = extract_lead_sheet_source_from_musicxml(musicxml)
    return generate_guitar_lead_sheet(
        key=key,
        tempo=tempo,
        style=style,
        melody=list(source.get("melody") or []),
        time_signature=time_signature,
        title=title,
        lyric_events=list(source.get("lyric_events") or []),
    )
