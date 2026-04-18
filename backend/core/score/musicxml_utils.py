"""MusicXML builder, validation, and summary helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from statistics import median
from typing import Any
from uuid import uuid4
import xml.etree.ElementTree as ET

import verovio

from backend.core.score.note_mapping import (
    beats_per_measure,
    note_to_midi,
    parse_time_signature,
    quantize_beats,
)


XML_NS = "http://www.w3.org/XML/1998/namespace"
DIVISIONS_PER_QUARTER = 8
DEFAULT_TITLE = "Untitled Score"
DEFAULT_PAGE_OPTIONS = {
    "breaks": "auto",
    "pageWidth": 2100,
    "pageHeight": 2970,
    "scale": 100,
    "adjustPageHeight": False,
    "adjustPageWidth": False,
    "svgViewBox": True,
}


def _configure_verovio_toolkit(toolkit: verovio.toolkit) -> verovio.toolkit:
    package_dir = Path(verovio.__file__).resolve().parent
    resource_dir = package_dir / "data"
    if resource_dir.exists():
        toolkit.setResourcePath(str(resource_dir))
    return toolkit

MAJOR_KEY_TO_FIFTHS = {
    "CB": -7,
    "GB": -6,
    "DB": -5,
    "AB": -4,
    "EB": -3,
    "BB": -2,
    "F": -1,
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "C#": 7,
}
MINOR_KEY_TO_FIFTHS = {
    "ABM": -7,
    "EBM": -6,
    "BBM": -5,
    "FM": -4,
    "CM": -3,
    "GM": -2,
    "DM": -1,
    "AM": 0,
    "EM": 1,
    "BM": 2,
    "F#M": 3,
    "C#M": 4,
    "G#M": 5,
    "D#M": 6,
    "A#M": 7,
}
FIFTHS_TO_MAJOR_KEY = {value: key for key, value in MAJOR_KEY_TO_FIFTHS.items()}
FIFTHS_TO_MINOR_KEY = {value: key[:-1] + "m" for key, value in MINOR_KEY_TO_FIFTHS.items()}
BEATS_TO_TYPE = {
    0.25: ("16th", 0),
    0.5: ("eighth", 0),
    0.75: ("eighth", 1),
    1.0: ("quarter", 0),
    1.5: ("quarter", 1),
    2.0: ("half", 0),
    3.0: ("half", 1),
    4.0: ("whole", 0),
}
ALTER_TO_ACCIDENTAL = {-2: "flat-flat", -1: "flat", 1: "sharp", 2: "double-sharp"}

ET.register_namespace("xml", XML_NS)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _find_first(element: ET.Element, name: str) -> ET.Element | None:
    for child in element.iter():
        if _local_name(child.tag) == name:
            return child
    return None


def _find_all(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element.iter() if _local_name(child.tag) == name]


def _first_text(element: ET.Element | None, default: str | None = None) -> str | None:
    if element is None or element.text is None:
        return default
    text = element.text.strip()
    return text or default


def _score_root_from_xml(musicxml: str) -> ET.Element:
    try:
        root = ET.fromstring(musicxml.strip().encode("utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"invalid XML: {exc}") from exc

    root_name = _local_name(root.tag)
    if root_name not in {"score-partwise", "score-timewise"}:
        raise ValueError("unsupported MusicXML document: expected score-partwise or score-timewise root")
    return root


def _normalized_key_signature(value: str | None) -> tuple[int, str]:
    if not value:
        return 0, "major"
    compact = str(value).strip().replace(" ", "")
    if not compact:
        return 0, "major"
    upper = compact.upper()
    if upper.endswith("M") and len(compact) > 1 and compact[-1].islower():
        fifths = MINOR_KEY_TO_FIFTHS.get(upper)
        if fifths is not None:
            return fifths, "minor"
    fifths = MAJOR_KEY_TO_FIFTHS.get(upper)
    if fifths is not None:
        return fifths, "major"
    return 0, "major"


def key_signature_from_fifths(fifths: int, mode: str | None = "major") -> str:
    normalized_mode = (mode or "major").strip().lower()
    if normalized_mode == "minor":
        return FIFTHS_TO_MINOR_KEY.get(int(fifths), "Am")
    return FIFTHS_TO_MAJOR_KEY.get(int(fifths), "C")


def _duration_components(beats: float, *, allow_measure_rest: bool = False) -> tuple[int, str, int]:
    quantized = quantize_beats(beats)
    if allow_measure_rest and quantized not in BEATS_TO_TYPE:
        if quantized <= 1.0:
            return _duration_components(1.0)
        if quantized <= 2.0:
            return _duration_components(2.0)
        if quantized <= 3.0:
            return _duration_components(3.0)
        return _duration_components(4.0)
    if quantized not in BEATS_TO_TYPE:
        raise ValueError(f"unsupported beat duration for MusicXML export: {beats}")
    note_type, dots = BEATS_TO_TYPE[quantized]
    duration = int(round(quantized * DIVISIONS_PER_QUARTER))
    return duration, note_type, dots


def _parse_pitch_components(pitch: str) -> tuple[str, int, int]:
    token = str(pitch or "").strip()
    if token == "Rest":
        raise ValueError("rest pitch cannot be converted to pitch components")
    step = token[0].upper()
    remainder = token[1:]
    accidental = ""
    if remainder and remainder[0] in {"#", "b"}:
        accidental = remainder[0]
        remainder = remainder[1:]
    try:
        octave = int(remainder)
    except ValueError as exc:
        raise ValueError(f"unsupported pitch value: {pitch}") from exc
    alter = 1 if accidental == "#" else -1 if accidental == "b" else 0
    return step, alter, octave


def _choose_clef(measures: list[dict[str, Any]]) -> tuple[str, str]:
    midi_values: list[int] = []
    for measure in measures:
        for note in measure.get("notes", []):
            pitch = str(note.get("pitch") or "")
            if note.get("is_rest") or pitch == "Rest":
                continue
            try:
                midi = note_to_midi(pitch)
            except ValueError:
                midi = None
            if midi is not None:
                midi_values.append(int(midi))
    if midi_values and median(midi_values) < 60:
        return "F", "4"
    return "G", "2"


def _title_from_root(root: ET.Element) -> str | None:
    work = next((child for child in root if _local_name(child.tag) == "work"), None)
    work_title = _first_text(_find_first(work, "work-title")) if work is not None else None
    if work_title:
        return work_title
    return _first_text(_find_first(root, "movement-title"))


def _set_title(root: ET.Element, title: str) -> None:
    movement_title = next((child for child in root if _local_name(child.tag) == "movement-title"), None)
    if movement_title is None:
        movement_title = ET.SubElement(root, "movement-title")
    movement_title.text = title

    work = next((child for child in root if _local_name(child.tag) == "work"), None)
    if work is None:
        insert_at = 0
        work = ET.Element("work")
        root.insert(insert_at, work)
    work_title = next((child for child in work if _local_name(child.tag) == "work-title"), None)
    if work_title is None:
        work_title = ET.SubElement(work, "work-title")
    work_title.text = title


def _ensure_xml_ids(root: ET.Element) -> None:
    measure_index = 0
    note_index = 0
    for measure in _find_all(root, "measure"):
        measure_index += 1
        measure.set(f"{{{XML_NS}}}id", measure.get(f"{{{XML_NS}}}id") or f"measure-{measure_index}")
        for note in measure:
            if _local_name(note.tag) != "note":
                continue
            note_index += 1
            note.set(f"{{{XML_NS}}}id", note.get(f"{{{XML_NS}}}id") or f"note-{note_index}")


def _indent_xml(root: ET.Element) -> None:
    try:
        ET.indent(root, space="  ")
    except AttributeError:  # pragma: no cover - older Python fallback
        pass


def _serialize_xml(root: ET.Element) -> str:
    _indent_xml(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def normalize_musicxml(musicxml: str, *, fallback_title: str | None = None) -> str:
    if not isinstance(musicxml, str) or not musicxml.strip():
        raise ValueError("musicxml must be a non-empty string")

    root = _score_root_from_xml(musicxml)
    _ensure_xml_ids(root)
    if fallback_title and not _title_from_root(root):
        _set_title(root, fallback_title)

    normalized = _serialize_xml(root)
    _validate_with_verovio(normalized)
    return normalized


def _validate_with_verovio(musicxml: str) -> None:
    toolkit = _configure_verovio_toolkit(verovio.toolkit())
    toolkit.setOptions(deepcopy(DEFAULT_PAGE_OPTIONS))
    try:
        loaded = toolkit.loadData(musicxml)
    except Exception as exc:
        raise ValueError(f"MusicXML failed Verovio validation: {exc}") from exc
    if not loaded:
        raise ValueError("MusicXML could not be loaded by Verovio")


def musicxml_page_count(musicxml: str) -> int:
    toolkit = _configure_verovio_toolkit(verovio.toolkit())
    toolkit.setOptions(deepcopy(DEFAULT_PAGE_OPTIONS))
    if not toolkit.loadData(musicxml):
        raise ValueError("MusicXML could not be loaded by Verovio")
    return max(int(toolkit.getPageCount() or 0), 1)


def build_score_summary(musicxml: str) -> dict[str, Any]:
    root = _score_root_from_xml(musicxml)
    measures = _find_all(root, "measure")
    title = _title_from_root(root) or DEFAULT_TITLE

    first_attributes = _find_first(root, "attributes")
    time_signature = "4/4"
    key_signature = "C"
    if first_attributes is not None:
        time_el = next((child for child in first_attributes if _local_name(child.tag) == "time"), None)
        if time_el is not None:
            beats = _first_text(_find_first(time_el, "beats"), "4")
            beat_type = _first_text(_find_first(time_el, "beat-type"), "4")
            time_signature = f"{beats}/{beat_type}"
        key_el = next((child for child in first_attributes if _local_name(child.tag) == "key"), None)
        if key_el is not None:
            fifths = int(_first_text(_find_first(key_el, "fifths"), "0") or 0)
            mode = _first_text(_find_first(key_el, "mode"), "major")
            key_signature = key_signature_from_fifths(fifths, mode)

    tempo = 120
    for sound in _find_all(root, "sound"):
        tempo_value = sound.attrib.get("tempo")
        if tempo_value:
            try:
                tempo = int(round(float(tempo_value)))
                break
            except ValueError:
                continue
    if tempo == 120:
        per_minute = _find_first(root, "per-minute")
        if per_minute is not None:
            try:
                tempo = int(round(float(_first_text(per_minute, "120") or 120)))
            except ValueError:
                tempo = 120

    return {
        "title": title,
        "tempo": tempo,
        "time_signature": time_signature,
        "key_signature": key_signature,
        "summary": {
            "measure_count": max(len(measures), 1),
            "page_hint": musicxml_page_count(musicxml),
        },
    }


def build_canonical_score_from_musicxml(
    musicxml: str,
    *,
    score_id: str | None = None,
    title: str | None = None,
    version: int = 1,
    project_id: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_musicxml(musicxml, fallback_title=title)
    summary_payload = build_score_summary(normalized)
    score = {
        "score_id": score_id or f"score_{uuid4().hex[:8]}",
        "version": int(version),
        "title": summary_payload["title"],
        "tempo": int(summary_payload["tempo"]),
        "time_signature": str(summary_payload["time_signature"]),
        "key_signature": str(summary_payload["key_signature"]),
        "musicxml": normalized,
        "summary": deepcopy(summary_payload["summary"]),
    }
    if project_id is not None:
        score["project_id"] = int(project_id)
    return score


def build_score_metadata_snapshot(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "score_id": str(score.get("score_id") or ""),
        "title": str(score.get("title") or DEFAULT_TITLE),
        "tempo": int(score.get("tempo", 120)),
        "time_signature": str(score.get("time_signature") or "4/4"),
        "key_signature": str(score.get("key_signature") or "C"),
        "version": int(score.get("version", 1)),
        "summary": deepcopy(score.get("summary") or {}),
        "canonical_format": "musicxml",
    }


def build_musicxml_from_measures(
    measures: list[dict[str, Any]],
    *,
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str = "C",
    title: str | None = None,
) -> str:
    normalized_title = title or DEFAULT_TITLE
    normalized_measures = list(measures or [])
    total_beats = beats_per_measure(time_signature)
    if not normalized_measures:
        normalized_measures = [
            {
                "measure_no": 1,
                "notes": [
                    {
                        "note_id": "note-1",
                        "pitch": "Rest",
                        "beats": total_beats,
                        "start_beat": 1.0,
                        "is_rest": True,
                    }
                ],
            }
        ]

    root = ET.Element("score-partwise", {"version": "4.0"})
    _set_title(root, normalized_title)

    identification = ET.SubElement(root, "identification")
    encoding = ET.SubElement(identification, "encoding")
    ET.SubElement(encoding, "software").text = "SeeMusic Verovio Migration"

    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", {"id": "P1"})
    ET.SubElement(score_part, "part-name").text = "Melody"
    part = ET.SubElement(root, "part", {"id": "P1"})

    clef_sign, clef_line = _choose_clef(normalized_measures)
    numerator, denominator = parse_time_signature(time_signature)
    fifths, mode = _normalized_key_signature(key_signature)

    note_counter = 0
    for measure_index, measure in enumerate(normalized_measures, start=1):
        measure_el = ET.SubElement(
            part,
            "measure",
            {
                "number": str(measure.get("measure_no") or measure_index),
                f"{{{XML_NS}}}id": f"measure-{measure_index}",
            },
        )
        attributes = ET.SubElement(measure_el, "attributes")
        ET.SubElement(attributes, "divisions").text = str(DIVISIONS_PER_QUARTER)
        key_el = ET.SubElement(attributes, "key")
        ET.SubElement(key_el, "fifths").text = str(fifths)
        ET.SubElement(key_el, "mode").text = mode
        time_el = ET.SubElement(attributes, "time")
        ET.SubElement(time_el, "beats").text = str(numerator)
        ET.SubElement(time_el, "beat-type").text = str(denominator)
        clef_el = ET.SubElement(attributes, "clef")
        ET.SubElement(clef_el, "sign").text = clef_sign
        ET.SubElement(clef_el, "line").text = clef_line

        if measure_index == 1:
            direction = ET.SubElement(measure_el, "direction", {"placement": "above"})
            direction_type = ET.SubElement(direction, "direction-type")
            metronome = ET.SubElement(direction_type, "metronome")
            ET.SubElement(metronome, "beat-unit").text = "quarter"
            ET.SubElement(metronome, "per-minute").text = str(int(tempo))
            ET.SubElement(direction, "sound", {"tempo": str(int(tempo))})

        notes = list(sorted(measure.get("notes") or [], key=lambda item: (float(item.get("start_beat", 1.0)), str(item.get("note_id") or ""))))
        if not notes:
            notes = [
                {
                    "note_id": f"note-{measure_index}-rest",
                    "pitch": "Rest",
                    "beats": total_beats,
                    "start_beat": 1.0,
                    "is_rest": True,
                }
            ]

        for note in notes:
            note_counter += 1
            note_el = ET.SubElement(
                measure_el,
                "note",
                {f"{{{XML_NS}}}id": str(note.get("note_id") or f"note-{note_counter}")},
            )

            is_rest = bool(note.get("is_rest")) or str(note.get("pitch")) == "Rest"
            if is_rest:
                ET.SubElement(note_el, "rest")
            else:
                pitch_el = ET.SubElement(note_el, "pitch")
                step, alter, octave = _parse_pitch_components(str(note.get("pitch") or "C4"))
                ET.SubElement(pitch_el, "step").text = step
                if alter:
                    ET.SubElement(pitch_el, "alter").text = str(alter)
                ET.SubElement(pitch_el, "octave").text = str(octave)

            duration, note_type, dots = _duration_components(float(note.get("beats") or 1.0), allow_measure_rest=is_rest)
            ET.SubElement(note_el, "duration").text = str(duration)
            ET.SubElement(note_el, "voice").text = "1"
            ET.SubElement(note_el, "type").text = note_type
            for _ in range(dots):
                ET.SubElement(note_el, "dot")

            if not is_rest:
                accidental = ALTER_TO_ACCIDENTAL.get(alter)
                if accidental:
                    ET.SubElement(note_el, "accidental").text = accidental
                tied_from_previous = bool(note.get("tied_from_previous"))
                tied_to_next = bool(note.get("tied_to_next"))
                if tied_from_previous:
                    ET.SubElement(note_el, "tie", {"type": "stop"})
                if tied_to_next:
                    ET.SubElement(note_el, "tie", {"type": "start"})
                if tied_from_previous or tied_to_next:
                    notations = ET.SubElement(note_el, "notations")
                    if tied_from_previous:
                        ET.SubElement(notations, "tied", {"type": "stop"})
                    if tied_to_next:
                        ET.SubElement(notations, "tied", {"type": "start"})

    normalized = _serialize_xml(root)
    _validate_with_verovio(normalized)
    return normalized


def musicxml_from_legacy_score(score: dict[str, Any], *, fallback_title: str | None = None) -> str:
    legacy = deepcopy(score or {})
    measures = legacy.get("measures") or []
    return build_musicxml_from_measures(
        measures,
        tempo=int(legacy.get("tempo", 120)),
        time_signature=str(legacy.get("time_signature", "4/4")),
        key_signature=str(legacy.get("key_signature", "C")),
        title=str(legacy.get("title") or fallback_title or DEFAULT_TITLE),
    )
