"""Generate guzheng-oriented jianpu charts from melody material."""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
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
DIRECT_OPEN_DEGREES_MAJOR = {1, 2, 3, 5, 6}
DIRECT_OPEN_DEGREES_MINOR = {1, 3, 4, 5, 7}
PLUCK_SEQUENCE = ("托", "勾", "抹")
ZONE_LABELS = {
    "high": "高音区",
    "middle": "中音区",
    "low": "低音区",
}


def _key_mode(key_signature: str) -> str:
    return "minor" if key_signature.endswith("m") else "major"


def _key_root_name(key_signature: str) -> str:
    return key_signature[:-1] if key_signature.endswith("m") else key_signature


def _pitch_class(note: str) -> int | None:
    midi = note_to_midi(note)
    if midi is None:
        return None
    return int(midi % 12)


def _scale_intervals(key_signature: str) -> list[int]:
    return [0, 2, 3, 5, 7, 8, 10] if _key_mode(key_signature) == "minor" else [0, 2, 4, 5, 7, 9, 11]


def _direct_open_degrees(key_signature: str) -> set[int]:
    return DIRECT_OPEN_DEGREES_MINOR if _key_mode(key_signature) == "minor" else DIRECT_OPEN_DEGREES_MAJOR


def _tonic_pitch_class(key_signature: str) -> int:
    tonic = _key_root_name(key_signature)
    return NOTE_NAME_TO_PITCH_CLASS.get(tonic, 0)


def _signed_interval(diff: int, target: int) -> int:
    delta = diff - target
    if delta > 6:
        delta -= 12
    if delta < -6:
        delta += 12
    return delta


def _resolve_degree_payload(pitch: str, key_signature: str) -> dict[str, Any]:
    midi = note_to_midi(pitch)
    if midi is None:
        return {
            "degree_no": 1,
            "degree_label": "1",
            "degree_display": "1",
            "accidental": None,
            "is_scale_tone": False,
            "is_pentatonic": False,
            "press_note_candidate": False,
        }

    tonic_pc = _tonic_pitch_class(key_signature)
    diff = int((midi - tonic_pc) % 12)
    intervals = _scale_intervals(key_signature)
    direct_open = _direct_open_degrees(key_signature)
    if diff in intervals:
        degree_no = intervals.index(diff) + 1
        accidental = None
        is_scale_tone = True
    else:
        nearest_index, nearest_interval = min(
            enumerate(intervals, start=1),
            key=lambda item: (abs(_signed_interval(diff, item[1])), item[0]),
        )
        degree_no = int(nearest_index)
        signed_delta = _signed_interval(diff, nearest_interval)
        accidental = "#" if signed_delta > 0 else "b"
        is_scale_tone = False

    degree_label = f"{accidental or ''}{degree_no}"
    is_pentatonic = is_scale_tone and degree_no in direct_open
    return {
        "degree_no": degree_no,
        "degree_label": degree_label,
        "degree_display": degree_label,
        "accidental": accidental,
        "is_scale_tone": is_scale_tone,
        "is_pentatonic": is_pentatonic,
        "press_note_candidate": not is_pentatonic,
    }


def _octave_marks(pitch: str) -> dict[str, int]:
    midi = note_to_midi(pitch)
    if midi is None:
        return {"above": 0, "below": 0}
    octave = midi // 12 - 1
    if octave >= 4:
        return {"above": max(octave - 4, 0), "below": 0}
    return {"above": 0, "below": max(4 - octave, 0)}


def _register_group_from_pitch(pitch: str) -> int:
    midi = note_to_midi(pitch)
    if midi is None:
        return 2
    octave = midi // 12 - 1
    return max(0, min(octave - 2, 4))


def _build_string_layout(cycle: tuple[int, ...]) -> list[dict[str, Any]]:
    layout: list[dict[str, Any]] = []
    for low_rank in range(21):
        string_no = 21 - low_rank
        degree = cycle[low_rank % len(cycle)]
        octave_group = low_rank // len(cycle)
        if string_no <= 7:
            zone = "high"
        elif string_no <= 14:
            zone = "middle"
        else:
            zone = "low"
        layout.append(
            {
                "string_no": string_no,
                "degree": degree,
                "octave_group": octave_group,
                "zone": zone,
                "zone_label": ZONE_LABELS[zone],
            }
        )
    return layout


@lru_cache(maxsize=4)
def _string_layout_for_key(key_signature: str) -> tuple[dict[str, Any], ...]:
    cycle = tuple(sorted(_direct_open_degrees(key_signature)))
    return tuple(_build_string_layout(cycle))


def _fallback_open_degree(degree_no: int, key_signature: str) -> int:
    direct_open = sorted(_direct_open_degrees(key_signature))
    lower = [item for item in direct_open if item <= degree_no]
    if lower:
        return lower[-1]
    return direct_open[0]


def _resolve_string_position(pitch: str, degree_payload: dict[str, Any], key_signature: str) -> dict[str, Any]:
    target_group = _register_group_from_pitch(pitch)
    direct_degree = (
        int(degree_payload["degree_no"])
        if degree_payload.get("is_pentatonic")
        else _fallback_open_degree(int(degree_payload["degree_no"]), key_signature)
    )
    string_layout = list(_string_layout_for_key(key_signature))
    candidates = [item for item in string_layout if int(item["degree"]) == direct_degree]
    if not candidates:
        candidates = string_layout
    chosen = min(
        candidates,
        key=lambda item: (abs(int(item["octave_group"]) - target_group), int(item["string_no"])),
    )
    return {
        "string_no": int(chosen["string_no"]),
        "string_label": f'{chosen["string_no"]}弦',
        "zone": chosen["zone"],
        "zone_label": chosen["zone_label"],
        "open_degree": direct_degree,
        "position_hint": f'{chosen["zone_label"]} · {chosen["string_no"]}弦',
        "requires_press": bool(degree_payload.get("press_note_candidate")),
    }


def _pluck_hint(index: int) -> str:
    return PLUCK_SEQUENCE[index % len(PLUCK_SEQUENCE)]


def _technique_tags(
    current_note: dict[str, Any],
    next_note: dict[str, Any] | None,
    *,
    degree_payload: dict[str, Any],
) -> list[str]:
    tags: list[str] = []
    if float(current_note.get("beats") or 0.0) >= 2.0:
        tags.append("摇指候选")
    if degree_payload.get("press_note_candidate"):
        tags.append("按音候选")
    current_midi = note_to_midi(str(current_note.get("pitch") or ""))
    next_midi = note_to_midi(str(next_note.get("pitch") or "")) if next_note else None
    if current_midi is not None and next_midi is not None:
        interval = int(next_midi - current_midi)
        if 0 < interval <= 2:
            tags.append("上滑音候选")
        elif -2 <= interval < 0:
            tags.append("下滑音候选")
    return tags


def _measure_cadence(measure: dict[str, Any]) -> str:
    notes = list(measure.get("notes") or [])
    if not notes:
        return "open"
    last_note = notes[-1]
    degree_no = int(last_note.get("degree_no") or 0)
    if degree_no == 1:
        return "resolved"
    if degree_no == 5:
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


def _summarize_phrase_positions(measures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, str]] = set()
    summary: list[dict[str, Any]] = []
    for measure in measures:
        for note in list(measure.get("notes") or []):
            signature = (int(note.get("string_no") or 0), str(note.get("degree_display") or ""))
            if signature in seen:
                continue
            seen.add(signature)
            summary.append(
                {
                    "note_id": note.get("note_id"),
                    "measure_no": note.get("measure_no"),
                    "string_no": note.get("string_no"),
                    "string_label": note.get("string_label"),
                    "zone_label": note.get("zone_label"),
                    "degree_display": note.get("degree_display"),
                    "position_hint": note.get("position_hint"),
                    "requires_press": note.get("press_note_candidate"),
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
        phrases.append(
            {
                "phrase_no": phrase_no,
                "phrase_label": f"乐句 {phrase_no}",
                "measure_start": int(phrase_measures[0]["measure_no"]),
                "measure_end": int(phrase_measures[-1]["measure_no"]),
                "measure_count": len(phrase_measures),
                "cadence": _measure_cadence(phrase_measures[-1]),
                "measures": phrase_measures,
                "string_positions": _summarize_phrase_positions(phrase_measures),
                "technique_counts": technique_counts,
                "phrase_tip": "按当前句法先稳住主音，再根据按音/滑音提示决定润饰。" if technique_counts else "当前乐句以主旋律直弹为主。",
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
                "note_id": f"gz_{measure_no}_{index}",
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


def _pentatonic_summary(notes: list[dict[str, Any]]) -> dict[str, Any]:
    direct_open_notes = sum(1 for note in notes if bool(note.get("is_pentatonic")))
    press_note_candidates = sum(1 for note in notes if bool(note.get("press_note_candidate")))
    scale_tone_notes = sum(1 for note in notes if bool(note.get("is_scale_tone")))
    total = len(notes)
    return {
        "direct_open_notes": direct_open_notes,
        "press_note_candidates": press_note_candidates,
        "scale_tone_notes": scale_tone_notes,
        "non_scale_tone_notes": max(total - scale_tone_notes, 0),
        "direct_ratio": round(direct_open_notes / total, 4) if total else 0.0,
    }


def _decorate_measures_with_guzheng(
    measures: list[dict[str, Any]],
    *,
    key_signature: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    flattened_notes: list[dict[str, Any]] = []
    decorated_measures: list[dict[str, Any]] = []

    for measure in measures:
        for note in list(measure.get("notes") or []):
            note_copy = dict(note)
            note_copy["measure_no"] = int(measure.get("measure_no") or 1)
            flattened_notes.append(note_copy)

    decorated_notes: list[dict[str, Any]] = []
    string_positions: list[dict[str, Any]] = []
    for index, note in enumerate(flattened_notes):
        degree_payload = _resolve_degree_payload(str(note.get("pitch") or "Rest"), key_signature)
        string_position = _resolve_string_position(str(note.get("pitch") or "Rest"), degree_payload, key_signature)
        technique_tags = _technique_tags(
            note,
            flattened_notes[index + 1] if index + 1 < len(flattened_notes) else None,
            degree_payload=degree_payload,
        )
        octave = _octave_marks(str(note.get("pitch") or "Rest"))
        decorated = {
            **note,
            **degree_payload,
            **string_position,
            "octave_marks": octave,
            "pluck_hint": _pluck_hint(index),
            "technique_tags": technique_tags,
        }
        decorated_notes.append(decorated)
        string_positions.append(
            {
                "note_id": decorated.get("note_id"),
                "measure_no": decorated.get("measure_no"),
                "start_beat": decorated.get("start_beat"),
                "pitch": decorated.get("pitch"),
                "degree_display": decorated.get("degree_display"),
                "string_no": decorated.get("string_no"),
                "string_label": decorated.get("string_label"),
                "zone_label": decorated.get("zone_label"),
                "position_hint": decorated.get("position_hint"),
                "requires_press": decorated.get("requires_press"),
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

    return decorated_measures, decorated_notes, string_positions


def _build_guzheng_jianpu_ir(
    *,
    title: str,
    key: str,
    tempo: int,
    time_signature: str,
    measures: list[dict[str, Any]],
    instrument_profile: dict[str, Any],
    pentatonic_summary: dict[str, Any],
) -> dict[str, Any]:
    ir_measures: list[dict[str, Any]] = []
    for measure in measures:
        ir_notes = [
            build_jianpu_note_ir(
                note,
                annotation_text=str(note.get("open_degree") or "") if note.get("press_note_candidate") else "",
                annotation_hint=str(note.get("position_hint") or ""),
                fingering_text=str(note.get("string_label") or ""),
                fingering_hint=str(note.get("position_hint") or note.get("zone_label") or ""),
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
        instrument_type="guzheng",
        instrument_name="古筝",
        instrument_subtitle=f"古筝简谱 · {'小调' if str(key).endswith('m') else '大调'} · {instrument_profile.get('tuning', '21弦 D调定弦')}",
        instrument_range=str(instrument_profile.get("range") or "D2-D6"),
        instrument_badge=str(instrument_profile.get("tuning") or "21弦 D调定弦"),
        measures=ir_measures,
        statistics={
            "press_note_candidates": int(pentatonic_summary.get("press_note_candidates") or 0),
            "direct_open_notes": int(pentatonic_summary.get("direct_open_notes") or 0),
        },
        extra_meta={
            "tuning": instrument_profile.get("tuning", "21弦 D调定弦"),
            "family": instrument_profile.get("family", "plucked"),
        },
    )


def generate_guzheng_score(
    *,
    key: str,
    tempo: int,
    time_signature: str,
    melody: list[dict[str, Any]],
    title: str | None = None,
    style: str = "traditional",
) -> dict[str, Any]:
    normalized_key = normalize_key_signature_text(key, default="C")
    normalized_style = str(style or "traditional").strip() or "traditional"
    base_measures = _materialize_measures_from_melody(melody, tempo=tempo, time_signature=time_signature)
    measures, flat_notes, string_positions = _decorate_measures_with_guzheng(
        base_measures,
        key_signature=normalized_key,
    )
    phrase_lines = _build_phrase_lines(measures, time_signature=time_signature)
    sections = _build_sections(phrase_lines, time_signature=time_signature)
    technique_summary = _technique_summary(flat_notes, phrase_lines)
    pentatonic_summary = _pentatonic_summary(flat_notes)
    instrument_profile = dict(get_traditional_instruments().get("guzheng") or {})
    jianpu_ir = _build_guzheng_jianpu_ir(
        title=title or "Untitled Guzheng Chart",
        key=normalized_key,
        tempo=int(tempo),
        time_signature=time_signature,
        measures=measures,
        instrument_profile={
            "family": instrument_profile.get("family", "plucked"),
            "range": instrument_profile.get("range", "D2-D6"),
            "tuning": instrument_profile.get("tuning", "21弦 D调定弦"),
        },
        pentatonic_summary=pentatonic_summary,
    )

    return {
        "lead_sheet_type": "guzheng_jianpu_chart",
        "render_source": "jianpu_ir",
        "layout_mode": "preview",
        "annotation_layers": ["basic", "fingering", "technique", "debug"],
        "title": title or "Untitled Guzheng Chart",
        "key": normalized_key,
        "tempo": int(tempo),
        "time_signature": time_signature,
        "style": normalized_style,
        "melody_size": len(flat_notes),
        "instrument_profile": {
            "name": "古筝",
            "family": instrument_profile.get("family", "plucked"),
            "range": instrument_profile.get("range", "D2-D6"),
            "tuning": instrument_profile.get("tuning", "21弦 D调定弦"),
        },
        "measures": measures,
        "phrase_lines": phrase_lines,
        "sections": sections,
        "string_positions": string_positions,
        "technique_summary": technique_summary,
        "pentatonic_summary": pentatonic_summary,
        "pitch_range": _range_summary(flat_notes),
        "jianpu_ir": jianpu_ir,
    }


def generate_guzheng_score_from_pitch_sequence(
    *,
    pitch_sequence: list[dict[str, Any]],
    tempo: int,
    time_signature: str,
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
    return generate_guzheng_score(
        key=str(materialized["key_signature"]),
        tempo=tempo,
        time_signature=time_signature,
        style=style,
        melody=list(materialized["melody"]),
        title=title,
    )


def generate_guzheng_score_from_musicxml(
    *,
    musicxml: str,
    key: str,
    tempo: int,
    time_signature: str = "4/4",
    title: str | None = None,
    style: str = "traditional",
) -> dict[str, Any]:
    melody = extract_melody_from_musicxml(musicxml)
    return generate_guzheng_score(
        key=key,
        tempo=tempo,
        time_signature=time_signature,
        style=style,
        melody=melody,
        title=title,
    )
