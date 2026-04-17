from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from backend.core.score.note_mapping import (
    beats_per_measure,
    beats_to_duration_label,
    frequency_to_note,
    note_to_frequency,
    parse_time_signature,
    quantize_beats,
)
from backend.core.score.sheet_extraction import _simplify_events_for_readability, build_score_from_pitch_sequence
from backend.db.models import ExportRecord, Sheet
from backend.db.session import session_scope
from backend.services.score_service import (
    UserNotFoundError,
    create_score_from_pitch_sequence,
    edit_score,
    export_score,
    get_score,
    redo_score,
    undo_score,
)


def _xml_root(musicxml: str) -> ET.Element:
    return ET.fromstring(musicxml.encode("utf-8"))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _all_elements(root: ET.Element, tag_name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == tag_name]


def _replace_tempo(musicxml: str, tempo: int) -> str:
    root = _xml_root(musicxml)
    for element in _all_elements(root, "per-minute"):
        element.text = str(tempo)
    for element in _all_elements(root, "sound"):
        if "tempo" in element.attrib:
            element.set("tempo", str(tempo))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def test_note_mapping_round_trip_supports_core_notes_and_rest():
    assert frequency_to_note(440.0) == "A4"
    assert round(note_to_frequency("C4"), 2) == 261.63
    assert round(note_to_frequency("Bb3"), 2) == 233.08
    assert note_to_frequency("Rest") == 0.0


def test_meter_and_duration_helpers_quantize_values():
    assert parse_time_signature("3/4") == (3, 4)
    assert beats_per_measure("3/4") == 3.0
    assert quantize_beats(0.62) == 0.5
    assert beats_to_duration_label(1.49) == "dotted_quarter"


def test_build_score_from_pitch_sequence_returns_canonical_musicxml_with_summary():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 1.0},
        ],
        tempo=120,
        time_signature="3/4",
        key_signature="G",
        title="Unit Score",
    )

    root = _xml_root(score["musicxml"])
    notes = _all_elements(root, "note")
    rests = [note for note in notes if any(_local_name(child.tag) == "rest" for child in note)]

    assert score["score_id"].startswith("score_")
    assert score["title"] == "Unit Score"
    assert score["tempo"] == 120
    assert score["time_signature"] == "3/4"
    assert score["key_signature"] == "G"
    assert score["summary"]["measure_count"] == 2
    assert len(notes) >= 3
    assert rests


def test_build_score_from_pitch_sequence_adds_cross_measure_ties_in_musicxml():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 2.5},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="C",
        title="Tied Score",
    )

    root = _xml_root(score["musicxml"])
    tie_starts = [element for element in _all_elements(root, "tie") if element.attrib.get("type") == "start"]
    tie_stops = [element for element in _all_elements(root, "tie") if element.attrib.get("type") == "stop"]

    assert score["summary"]["measure_count"] == 2
    assert tie_starts
    assert tie_stops


def test_simplify_events_for_readability_merges_same_pitch_across_tiny_gap():
    simplified = _simplify_events_for_readability(
        [
            {"pitch": "A4", "frequency": 440.0, "duration_seconds": 0.5, "is_rest": False, "start_time": 0.0, "end_time": 0.5},
            {"pitch": "Rest", "frequency": 0.0, "duration_seconds": 0.125, "is_rest": True, "start_time": 0.5, "end_time": 0.625},
            {"pitch": "A4", "frequency": 440.0, "duration_seconds": 0.5, "is_rest": False, "start_time": 0.625, "end_time": 1.125},
        ],
        tempo=120,
    )

    assert len(simplified) == 1
    assert simplified[0]["pitch"] == "A4"
    assert simplified[0]["is_rest"] is False
    assert simplified[0]["duration_seconds"] == 1.125


def test_simplify_events_for_readability_absorbs_short_rest_between_notes():
    simplified = _simplify_events_for_readability(
        [
            {"pitch": "A4", "frequency": 440.0, "duration_seconds": 0.5, "is_rest": False, "start_time": 0.0, "end_time": 0.5},
            {"pitch": "Rest", "frequency": 0.0, "duration_seconds": 0.2, "is_rest": True, "start_time": 0.5, "end_time": 0.7},
            {"pitch": "B4", "frequency": 493.88, "duration_seconds": 0.5, "is_rest": False, "start_time": 0.7, "end_time": 1.2},
        ],
        tempo=120,
    )

    assert len([event for event in simplified if event["is_rest"]]) == 0
    assert sum(event["duration_seconds"] for event in simplified) == 1.2
    assert simplified[0]["duration_seconds"] == 0.7
    assert simplified[1]["pitch"] == "B4"


def test_simplify_events_for_readability_keeps_fast_distinct_notes():
    simplified = _simplify_events_for_readability(
        [
            {"pitch": "C4", "frequency": 261.63, "duration_seconds": 0.125, "is_rest": False, "start_time": 0.0, "end_time": 0.125},
            {"pitch": "D4", "frequency": 293.66, "duration_seconds": 0.125, "is_rest": False, "start_time": 0.125, "end_time": 0.25},
            {"pitch": "E4", "frequency": 329.63, "duration_seconds": 0.125, "is_rest": False, "start_time": 0.25, "end_time": 0.375},
            {"pitch": "F4", "frequency": 349.23, "duration_seconds": 0.125, "is_rest": False, "start_time": 0.375, "end_time": 0.5},
        ],
        tempo=120,
    )

    assert [event["pitch"] for event in simplified] == ["C4", "D4", "E4", "F4"]
    assert all(event["duration_seconds"] == 0.125 for event in simplified)


def test_score_editing_and_history_round_trip(score_database: dict[str, int | str]):
    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "title": "Unit Test Score",
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    score_id = score["score_id"]

    updated = edit_score(score_id, _replace_tempo(score["musicxml"], 96))
    fetched = get_score(score_id)

    assert updated["tempo"] == 96
    assert updated["version"] == 2
    assert fetched["tempo"] == 96
    assert "96" in updated["musicxml"]

    reverted = undo_score(score_id)
    assert reverted["tempo"] == 120
    assert reverted["version"] == 1

    redone = redo_score(score_id)
    assert redone["tempo"] == 96
    assert redone["version"] == 2

    with session_scope() as session:
        sheet = session.query(Sheet).filter_by(score_id=score_id).one()
        assert sheet.project_id == score["project_id"]
        assert sheet.note_data["version"] == redone["version"]
        assert sheet.musicxml == redone["musicxml"]
        assert sheet.bpm == redone["tempo"]
        assert sheet.key_sign == redone["key_signature"]
        assert sheet.time_sign == redone["time_signature"]


def test_score_export_builds_verovio_manifests(score_database: dict[str, int | str]):
    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    score_id = score["score_id"]

    midi_export = export_score(score_id, {"format": "midi"})
    pdf_export = export_score(score_id, {"format": "pdf", "page_size": "A4", "with_annotations": True})
    png_export = export_score(score_id, {"format": "png", "page_size": "A4", "with_annotations": False})

    assert midi_export["manifest"]["kind"] == "midi"
    assert midi_export["download_url"].startswith("/storage/exports/")
    assert pdf_export["manifest"]["kind"] == "pdf"
    assert pdf_export["manifest"]["page_count"] >= 1
    assert pdf_export["download_url"].startswith("/storage/exports/")
    assert png_export["manifest"]["kind"] == "png"
    assert png_export["download_url"].startswith("/storage/exports/")

    with session_scope() as session:
        records = session.query(ExportRecord).filter_by(project_id=score["project_id"]).all()
        assert len(records) == 3
        assert {record.format for record in records} == {"midi", "pdf", "png"}
        assert all(record.file_url for record in records)


def test_create_score_from_pitch_sequence_rejects_unknown_user(score_database: dict[str, int | str]):
    with pytest.raises(UserNotFoundError) as exc_info:
        create_score_from_pitch_sequence(
            {
                "user_id": int(score_database["user_id"]) + 999,
                "tempo": 120,
                "time_signature": "4/4",
                "key_signature": "C",
                "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
            }
        )

    assert "not found" in str(exc_info.value)
