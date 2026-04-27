"""Generate dizi-oriented jianpu charts from melody material."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from backend.core.guitar.lead_sheet import extract_melody_from_musicxml
from backend.core.score.key_detection import normalize_key_signature_text
from backend.core.score.melody_materialization import materialize_melody_from_pitch_sequence
from backend.core.score.note_mapping import beats_per_measure, note_to_midi, parse_time_signature
from backend.core.traditional.jianpu_ir import build_jianpu_ir, build_jianpu_note_ir
from backend.core.traditional.traditional_instruments import get_traditional_instruments

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
PITCH_CLASS_TO_NOTE = {
    0: "C",
    1: "C#",
    2: "D",
    3: "D#",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "G#",
    9: "A",
    10: "Bb",
    11: "B",
}
SUPPORTED_FLUTE_TYPES = ("C", "D", "E", "F", "G", "A", "Bb")
FINGERING_PATTERNS = {
    1: "●●● ●●●",
    2: "●●● ●●○",
    3: "●●● ●○○",
    4: "●●● ○○○",
    5: "●●○ ○○○",
    6: "●○○ ○○○",
    7: "○○○ ○○○",
}
BLOW_HINT_SEQUENCE = ("平吹", "轻吐", "连吹")
REGISTER_LABELS = {
    "high": "高音区",
    "middle": "中音区",
    "low": "低音区",
}
MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
FLUTE_TYPE_PROFILES = {
    "C": {"tonic_midi": 60},
    "D": {"tonic_midi": 62},
    "E": {"tonic_midi": 64},
    "F": {"tonic_midi": 65},
    "G": {"tonic_midi": 67},
    "A": {"tonic_midi": 69},
    "Bb": {"tonic_midi": 70},
}


def normalize_flute_type(flute_type: str | None, default: str = "G") -> str:
    raw = str(flute_type or "").strip().replace("♭", "b")
    if not raw:
        raw = default
    lowered = raw.lower()
    if lowered == "bb":
        return "Bb"
    upper = raw.upper()
    if upper in {"C", "D", "E", "F", "G", "A"}:
        return upper
    if upper == "BB":
        return "Bb"
    return default


def _signed_interval(diff: int, target: int) -> int:
    delta = diff - target
    if delta > 6:
        delta -= 12
    if delta < -6:
        delta += 12
    return delta


def _midi_to_pitch_name(midi: int | None) -> str | None:
    if midi is None:
        return None
    normalized = int(midi)
    octave = normalized // 12 - 1
    pitch_class = normalized % 12
    return f"{PITCH_CLASS_TO_NOTE[pitch_class]}{octave}"


def _resolve_flute_profile(flute_type: str) -> dict[str, Any]:
    normalized = normalize_flute_type(flute_type)
    profile = dict(FLUTE_TYPE_PROFILES.get(normalized) or FLUTE_TYPE_PROFILES["G"])
    tonic_midi = int(profile["tonic_midi"])
    lowest_midi = tonic_midi - 2
    highest_midi = tonic_midi + 26
    return {
        "flute_type": normalized,
        "tonic_midi": tonic_midi,
        "tonic_pitch": _midi_to_pitch_name(tonic_midi),
        "lowest_midi": lowest_midi,
        "highest_midi": highest_midi,
        "range_text": f"{_midi_to_pitch_name(lowest_midi)}-{_midi_to_pitch_name(highest_midi)}",
    }


def _resolve_degree_payload(pitch: str, flute_type: str) -> dict[str, Any]:
    midi = note_to_midi(pitch)
    if midi is None:
        return {
            "degree_no": 1,
            "degree_label": "1",
            "degree_display": "1",
            "accidental": None,
            "is_scale_tone": False,
        }

    tonic_pc = NOTE_NAME_TO_PITCH_CLASS.get(normalize_flute_type(flute_type), 7)
    diff = int((midi - tonic_pc) % 12)
    if diff in MAJOR_SCALE_INTERVALS:
        degree_no = MAJOR_SCALE_INTERVALS.index(diff) + 1
        accidental = None
        is_scale_tone = True
    else:
        nearest_index, nearest_interval = min(
            enumerate(MAJOR_SCALE_INTERVALS, start=1),
            key=lambda item: (abs(_signed_interval(diff, item[1])), item[0]),
        )
        degree_no = int(nearest_index)
        signed_delta = _signed_interval(diff, nearest_interval)
        accidental = "#" if signed_delta > 0 else "b"
        is_scale_tone = False

    degree_label = f"{accidental or ''}{degree_no}"
    return {
        "degree_no": degree_no,
        "degree_label": degree_label,
        "degree_display": degree_label,
        "accidental": accidental,
        "is_scale_tone": is_scale_tone,
    }


def _octave_marks_relative_to_flute(pitch: str, flute_type: str) -> dict[str, int]:
    midi = note_to_midi(pitch)
    if midi is None:
        return {"above": 0, "below": 0}
    tonic_midi = int(_resolve_flute_profile(flute_type)["tonic_midi"])
    delta = int(midi - tonic_midi)
    if delta >= 0:
        return {"above": delta // 12, "below": 0}
    return {"above": 0, "below": (abs(delta) + 11) // 12}


def _register_label(pitch: str, flute_type: str) -> str:
    midi = note_to_midi(pitch)
    if midi is None:
        return REGISTER_LABELS["middle"]
    tonic_midi = int(_resolve_flute_profile(flute_type)["tonic_midi"])
    if midi < tonic_midi:
        return REGISTER_LABELS["low"]
    if midi >= tonic_midi + 12:
        return REGISTER_LABELS["high"]
    return REGISTER_LABELS["middle"]


def _resolve_fingering(
    pitch: str,
    degree_payload: dict[str, Any],
    *,
    flute_type: str,
) -> dict[str, Any]:
    midi = note_to_midi(pitch)
    profile = _resolve_flute_profile(flute_type)
    octave_marks = _octave_marks_relative_to_flute(pitch, flute_type)
    degree_no = int(degree_payload.get("degree_no") or 1)
    accidental = degree_payload.get("accidental")
    half_hole_candidate = bool(accidental)
    special_fingering_candidate = bool(accidental) and (
        degree_no in {4, 7} or int(octave_marks.get("above") or 0) > 0 or int(octave_marks.get("below") or 0) > 0
    )
    out_of_range = midi is None or midi < int(profile["lowest_midi"]) or midi > int(profile["highest_midi"])
    if out_of_range:
        fingering_hint = "超出当前笛型建议音域"
    elif special_fingering_candidate:
        fingering_hint = "特殊指法候选"
    elif half_hole_candidate:
        fingering_hint = "半孔候选"
    else:
        fingering_hint = "常规指法"
    return {
        "hole_pattern": FINGERING_PATTERNS.get(degree_no, "●●● ●●●"),
        "fingering_label": fingering_hint,
        "fingering_hint": fingering_hint,
        "half_hole_candidate": half_hole_candidate,
        "special_fingering_candidate": special_fingering_candidate,
        "out_of_range": out_of_range,
        "register_label": _register_label(pitch, flute_type),
        "range_text": profile["range_text"],
    }


def _blow_hint(index: int) -> str:
    return BLOW_HINT_SEQUENCE[index % len(BLOW_HINT_SEQUENCE)]


def _measure_cadence(measure: dict[str, Any]) -> str:
    notes = list(measure.get("notes") or [])
    if not notes:
        return "open"
    last_note = notes[-1]
    degree_no = int(last_note.get("degree_no") or 0)
    if degree_no == 1:
        return "resolved"
    if degree_no in {5, 7}:
        return "half"
    return "open"


def _section_label(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index <= len(alphabet):
        return alphabet[index - 1]
    quotient, remainder = divmod(index - 1, len(alphabet))
    return f"{alphabet[quotient - 1]}{alphabet[remainder]}"


def _target_measures_per_phrase(time_signature: str, total_measures: int) -> int:
    numerator, denominator = parse_time_signature(time_signature)
    if total_measures <= 4:
        return total_measures or 1
    if denominator == 8 and numerator >= 6 and numerator % 3 == 0:
        return 4 if total_measures <= 8 else 6
    if time_signature == "3/4":
        return 4
    return 4 if total_measures <= 12 else 6


def _technique_tags(
    current_note: dict[str, Any],
    next_note: dict[str, Any] | None,
    *,
    gap_beats: float,
) -> list[str]:
    tags: list[str] = []
    beats = float(current_note.get("beats") or 0.0)
    if beats >= 2.0:
        tags.append("颤音/长音保持候选")
    if gap_beats >= 1.0 or next_note is None:
        tags.append("换气点")

    current_midi = note_to_midi(str(current_note.get("pitch") or ""))
    next_midi = note_to_midi(str(next_note.get("pitch") or "")) if next_note else None
    if current_midi is not None and next_midi is not None:
        interval = int(next_midi - current_midi)
        if 0 < abs(interval) <= 2:
            tags.append("滑音候选")
        if beats <= 0.5 and float(next_note.get("beats") or 0.0) >= 1.0 and 0 < abs(interval) <= 2:
            tags.append("倚音候选")
    return tags


def _materialize_measures_from_melody(
    melody: list[dict[str, Any]],
    *,
    tempo: int,
    time_signature: str,
) -> list[dict[str, Any]]:
    total_beats = beats_per_measure(time_signature)
    measures: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"measure_no": 1, "beats": total_beats, "notes": []}
    )

    for index, item in enumerate(melody, start=1):
        pitch = str(item.get("pitch") or item.get("note") or "").strip()
        if not pitch or pitch == "Rest":
            continue
        beats = float(item.get("beats") or 0.0) or 1.0
        measure_no = max(int(item.get("measure_no") or 1), 1)
        start_beat = max(float(item.get("start_beat") or 1.0), 1.0)
        measure = measures[measure_no]
        measure["measure_no"] = measure_no
        measure["beats"] = total_beats
        measure["notes"].append(
            {
                "note_id": f"dz_{measure_no}_{index}",
                "pitch": pitch,
                "beats": beats,
                "start_beat": start_beat,
                "time": round(
                    ((measure_no - 1) * total_beats + (start_beat - 1.0)) * 60.0 / max(int(tempo), 1),
                    3,
                ),
            }
        )

    if not measures:
        return [{"measure_no": 1, "beats": total_beats, "notes": []}]
    return [measures[index] for index in sorted(measures)]


def _range_summary(notes: list[dict[str, Any]]) -> dict[str, Any]:
    non_rest = [note for note in notes if str(note.get("pitch") or "") != "Rest"]
    if not non_rest:
        return {"lowest": None, "highest": None}
    sorted_notes = sorted(non_rest, key=lambda item: note_to_midi(str(item.get("pitch") or "")) or 0)
    return {
        "lowest": sorted_notes[0].get("pitch"),
        "highest": sorted_notes[-1].get("pitch"),
    }


def _summarize_phrase_fingerings(measures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    summary: list[dict[str, Any]] = []
    for measure in measures:
        for note in list(measure.get("notes") or []):
            signature = (
                str(note.get("degree_display") or ""),
                str(note.get("hole_pattern") or ""),
                str(note.get("register_label") or ""),
            )
            if signature in seen:
                continue
            seen.add(signature)
            summary.append(
                {
                    "note_id": note.get("note_id"),
                    "measure_no": note.get("measure_no"),
                    "pitch": note.get("pitch"),
                    "degree_display": note.get("degree_display"),
                    "hole_pattern": note.get("hole_pattern"),
                    "register_label": note.get("register_label"),
                    "half_hole_candidate": note.get("half_hole_candidate"),
                    "special_fingering_candidate": note.get("special_fingering_candidate"),
                    "out_of_range": note.get("out_of_range"),
                    "fingering_hint": note.get("fingering_hint"),
                }
            )
    return summary[:8]


def _phrase_technique_counts(measures: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for measure in measures:
        for note in list(measure.get("notes") or []):
            counter.update(list(note.get("technique_tags") or []))
    return dict(counter)


def _build_phrase_lines(measures: list[dict[str, Any]], *, time_signature: str) -> list[dict[str, Any]]:
    if not measures:
        return []

    target_size = _target_measures_per_phrase(time_signature, len(measures))
    phrases: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    phrase_no = 1

    for index, measure in enumerate(measures):
        current.append(measure)
        cadence = _measure_cadence(measure)
        at_last = index == len(measures) - 1
        reached_target = len(current) >= target_size
        cadence_break = len(current) >= max(target_size - 1, 1) and cadence in {"resolved", "half"}
        overflow_break = len(current) >= max(target_size + 2, 6)
        if not (at_last or reached_target or cadence_break or overflow_break):
            continue

        phrase_measures = list(current)
        technique_counts = _phrase_technique_counts(phrase_measures)
        highlights = [label for label, count in technique_counts.items() if int(count or 0) > 0]
        phrases.append(
            {
                "phrase_no": phrase_no,
                "phrase_label": f"乐句 {phrase_no}",
                "measure_start": int(phrase_measures[0]["measure_no"]),
                "measure_end": int(phrase_measures[-1]["measure_no"]),
                "measure_count": len(phrase_measures),
                "cadence": _measure_cadence(phrase_measures[-1]),
                "measures": phrase_measures,
                "fingerings": _summarize_phrase_fingerings(phrase_measures),
                "technique_counts": technique_counts,
                "phrase_tip": (
                    "先按当前句法稳住筒音关系，再根据换气和滑音候选决定是否润色。"
                    if highlights
                    else "当前乐句以平吹主旋律为主。"
                ),
            }
        )
        current = []
        phrase_no += 1

    return phrases


def _build_sections(phrase_lines: list[dict[str, Any]], *, time_signature: str) -> list[dict[str, Any]]:
    if not phrase_lines:
        return []

    target_section_measures = 8 if _target_measures_per_phrase(time_signature, 8) >= 4 else 4
    sections: list[dict[str, Any]] = []
    current_lines: list[dict[str, Any]] = []
    section_no = 1

    for index, line in enumerate(phrase_lines):
        current_lines.append(line)
        measure_count = sum(int(item.get("measure_count") or 0) for item in current_lines)
        at_last_line = index == len(phrase_lines) - 1
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
                "phrase_start": int(current_lines[0]["phrase_no"]),
                "phrase_end": int(current_lines[-1]["phrase_no"]),
                "cadence": cadence,
                "phrase_lines": list(current_lines),
            }
        )
        current_lines = []
        section_no += 1

    return sections


def _technique_summary(notes: list[dict[str, Any]], phrase_lines: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    for note in notes:
        counter.update(list(note.get("technique_tags") or []))
    phrase_suggestions = []
    for phrase in phrase_lines:
        counts = phrase.get("technique_counts") or {}
        highlights = [label for label, count in counts.items() if int(count or 0) > 0]
        phrase_suggestions.append(
            {
                "phrase_no": phrase.get("phrase_no"),
                "phrase_label": phrase.get("phrase_label"),
                "measure_start": phrase.get("measure_start"),
                "measure_end": phrase.get("measure_end"),
                "highlights": highlights,
                "suggestion": phrase.get("phrase_tip"),
            }
        )
    return {
        "counts": dict(counter),
        "total_tagged_notes": sum(counter.values()),
        "phrase_suggestions": phrase_suggestions,
    }


def _playability_summary(notes: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(notes)
    out_of_range_notes = sum(1 for note in notes if bool(note.get("out_of_range")))
    half_hole_candidates = sum(1 for note in notes if bool(note.get("half_hole_candidate")))
    special_fingering_candidates = sum(1 for note in notes if bool(note.get("special_fingering_candidate")))
    return {
        "total_notes": total,
        "playable_notes": max(total - out_of_range_notes, 0),
        "out_of_range_notes": out_of_range_notes,
        "half_hole_candidates": half_hole_candidates,
        "special_fingering_candidates": special_fingering_candidates,
        "playable_ratio": round((total - out_of_range_notes) / total, 4) if total else 0.0,
    }


def _decorate_measures_with_dizi(
    measures: list[dict[str, Any]],
    *,
    flute_type: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    flattened_notes: list[dict[str, Any]] = []
    decorated_measures: list[dict[str, Any]] = []

    for measure in measures:
        for note in list(measure.get("notes") or []):
            note_copy = dict(note)
            note_copy["measure_no"] = int(measure.get("measure_no") or 1)
            flattened_notes.append(note_copy)

    decorated_notes: list[dict[str, Any]] = []
    fingerings: list[dict[str, Any]] = []
    for index, note in enumerate(flattened_notes):
        next_note = flattened_notes[index + 1] if index + 1 < len(flattened_notes) else None
        current_end = float(note.get("start_beat") or 1.0) + float(note.get("beats") or 0.0)
        next_start = float(next_note.get("start_beat") or 1.0) if next_note else current_end
        next_measure = int(next_note.get("measure_no") or note.get("measure_no") or 1) if next_note else int(note.get("measure_no") or 1)
        measure_jump = max(next_measure - int(note.get("measure_no") or 1), 0)
        gap_beats = max((measure_jump * float(measures[0].get("beats") or 4.0)) + next_start - current_end, 0.0) if next_note else 1.0
        degree_payload = _resolve_degree_payload(str(note.get("pitch") or "Rest"), flute_type)
        fingering_payload = _resolve_fingering(str(note.get("pitch") or "Rest"), degree_payload, flute_type=flute_type)
        octave = _octave_marks_relative_to_flute(str(note.get("pitch") or "Rest"), flute_type)
        technique_tags = _technique_tags(note, next_note, gap_beats=gap_beats)
        decorated = {
            **note,
            **degree_payload,
            **fingering_payload,
            "octave_marks": octave,
            "blow_hint": _blow_hint(index),
            "technique_tags": technique_tags,
        }
        decorated_notes.append(decorated)
        fingerings.append(
            {
                "note_id": decorated.get("note_id"),
                "measure_no": decorated.get("measure_no"),
                "start_beat": decorated.get("start_beat"),
                "pitch": decorated.get("pitch"),
                "degree_display": decorated.get("degree_display"),
                "hole_pattern": decorated.get("hole_pattern"),
                "register_label": decorated.get("register_label"),
                "half_hole_candidate": decorated.get("half_hole_candidate"),
                "special_fingering_candidate": decorated.get("special_fingering_candidate"),
                "out_of_range": decorated.get("out_of_range"),
                "fingering_hint": decorated.get("fingering_hint"),
            }
        )

    notes_by_measure: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for note in decorated_notes:
        notes_by_measure[int(note.get("measure_no") or 1)].append(note)

    for measure in measures:
        measure_no = int(measure.get("measure_no") or 1)
        decorated_measures.append(
            {
                "measure_no": measure_no,
                "beats": float(measure.get("beats") or measure.get("total_beats") or 4.0),
                "notes": sorted(
                    list(notes_by_measure.get(measure_no) or []),
                    key=lambda item: (float(item.get("start_beat") or 1.0), str(item.get("note_id") or "")),
                ),
            }
        )

    return decorated_measures, decorated_notes, fingerings


def _build_dizi_jianpu_ir(
    *,
    title: str,
    key: str,
    tempo: int,
    time_signature: str,
    flute_type: str,
    measures: list[dict[str, Any]],
    instrument_profile: dict[str, Any],
    playability_summary: dict[str, Any],
) -> dict[str, Any]:
    ir_measures: list[dict[str, Any]] = []
    for measure in measures:
        ir_notes = [
            build_jianpu_note_ir(
                note,
                annotation_text=(
                    "超"
                    if note.get("out_of_range")
                    else "特"
                    if note.get("special_fingering_candidate")
                    else "半"
                    if note.get("half_hole_candidate")
                    else ""
                ),
                annotation_hint=str(note.get("fingering_hint") or ""),
                fingering_text=str(note.get("hole_pattern") or ""),
                fingering_hint=str(note.get("register_label") or note.get("fingering_hint") or ""),
            )
            for note in list(measure.get("notes") or [])
        ]
        ir_measures.append(
            {
                "measure_no": int(measure.get("measure_no") or 1),
                "beats": float(measure.get("beats") or 4.0),
                "notes": ir_notes,
            }
        )

    return build_jianpu_ir(
        title=title,
        key=key,
        tempo=tempo,
        time_signature=time_signature,
        instrument_type="dizi",
        instrument_name="笛子",
        instrument_subtitle=f"笛子简谱 · 按 {flute_type} 调笛筒音关系显示",
        instrument_range=str(instrument_profile.get("range") or "--"),
        instrument_badge=f"{flute_type} 调笛",
        measures=ir_measures,
        statistics={
            "playable_notes": int(playability_summary.get("playable_notes") or 0),
            "out_of_range_notes": int(playability_summary.get("out_of_range_notes") or 0),
            "half_hole_candidates": int(playability_summary.get("half_hole_candidates") or 0),
            "special_fingering_candidates": int(playability_summary.get("special_fingering_candidates") or 0),
        },
        extra_meta={
            "flute_type": flute_type,
            "family": instrument_profile.get("family", "wind"),
            "tube_tonic": instrument_profile.get("tube_tonic"),
        },
    )


def generate_dizi_score(
    *,
    key: str,
    tempo: int,
    time_signature: str,
    melody: list[dict[str, Any]],
    flute_type: str = "G",
    title: str | None = None,
    style: str = "traditional",
) -> dict[str, Any]:
    normalized_key = normalize_key_signature_text(key, default="C")
    normalized_style = str(style or "traditional").strip() or "traditional"
    normalized_flute_type = normalize_flute_type(flute_type)
    base_measures = _materialize_measures_from_melody(melody, tempo=tempo, time_signature=time_signature)
    measures, flat_notes, fingerings = _decorate_measures_with_dizi(
        base_measures,
        flute_type=normalized_flute_type,
    )
    phrase_lines = _build_phrase_lines(measures, time_signature=time_signature)
    sections = _build_sections(phrase_lines, time_signature=time_signature)
    technique_summary = _technique_summary(flat_notes, phrase_lines)
    playability_summary = _playability_summary(flat_notes)
    preset = dict(get_traditional_instruments().get("dizi") or {})
    flute_profile = _resolve_flute_profile(normalized_flute_type)
    instrument_profile = {
        "name": "笛子",
        "family": preset.get("family", "wind"),
        "range": flute_profile["range_text"],
        "flute_type": normalized_flute_type,
        "tube_tonic": flute_profile["tonic_pitch"],
    }
    jianpu_ir = _build_dizi_jianpu_ir(
        title=title or "Untitled Dizi Chart",
        key=normalized_key,
        tempo=int(tempo),
        time_signature=time_signature,
        flute_type=normalized_flute_type,
        measures=measures,
        instrument_profile=instrument_profile,
        playability_summary=playability_summary,
    )

    return {
        "lead_sheet_type": "dizi_jianpu_chart",
        "render_source": "jianpu_ir",
        "layout_mode": "preview",
        "annotation_layers": ["basic", "fingering", "technique", "debug"],
        "title": title or "Untitled Dizi Chart",
        "key": normalized_key,
        "tempo": int(tempo),
        "time_signature": time_signature,
        "style": normalized_style,
        "flute_type": normalized_flute_type,
        "melody_size": len(flat_notes),
        "instrument_profile": instrument_profile,
        "measures": measures,
        "phrase_lines": phrase_lines,
        "sections": sections,
        "fingerings": fingerings,
        "technique_summary": technique_summary,
        "playability_summary": playability_summary,
        "pitch_range": _range_summary(flat_notes),
        "jianpu_ir": jianpu_ir,
    }


def generate_dizi_score_from_pitch_sequence(
    *,
    pitch_sequence: list[dict[str, Any]],
    tempo: int,
    time_signature: str,
    flute_type: str = "G",
    key: str | None = None,
    title: str | None = None,
    style: str = "traditional",
) -> dict[str, Any]:
    materialized = materialize_melody_from_pitch_sequence(
        pitch_sequence,
        tempo=tempo,
        time_signature=time_signature,
        key_signature=key,
        auto_detect_key=not bool(str(key or "").strip()),
    )
    return generate_dizi_score(
        key=str(materialized["key_signature"]),
        tempo=tempo,
        time_signature=time_signature,
        flute_type=flute_type,
        style=style,
        melody=list(materialized["melody"]),
        title=title,
    )


def generate_dizi_score_from_musicxml(
    *,
    musicxml: str,
    key: str,
    tempo: int,
    flute_type: str = "G",
    time_signature: str = "4/4",
    title: str | None = None,
    style: str = "traditional",
) -> dict[str, Any]:
    melody = extract_melody_from_musicxml(musicxml)
    return generate_dizi_score(
        key=key,
        tempo=tempo,
        time_signature=time_signature,
        flute_type=flute_type,
        style=style,
        melody=melody,
        title=title,
    )
