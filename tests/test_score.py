import pytest

from backend.db.models import ExportRecord, Sheet
from backend.db.session import session_scope
from backend.core.score.note_mapping import (
    beats_per_measure,
    beats_to_duration_label,
    frequency_to_note,
    note_to_frequency,
    parse_time_signature,
    quantize_beats,
)
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.services.score_service import (
    UserNotFoundError,
    create_score_from_pitch_sequence,
    edit_score,
    export_score,
    redo_score,
    undo_score,
)


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


def test_build_score_from_pitch_sequence_splits_measures_and_inserts_rest():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 1.0},
        ],
        tempo=120,
        time_signature="3/4",
    )

    first_measure = score["measures"][0]
    second_measure = score["measures"][1]

    assert score["score_id"]
    assert len(score["measures"]) == 2
    assert first_measure["notes"][1]["is_rest"] is True
    assert first_measure["notes"][1]["beats"] == 1.0
    assert second_measure["notes"][0]["pitch"] == "C5"
    assert second_measure["notes"][0]["beats"] == 2.0


def test_build_score_from_pitch_sequence_merges_adjacent_same_pitch():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
        ],
        tempo=120,
    )

    notes = score["measures"][0]["notes"]
    assert len(notes) == 1
    assert notes[0]["beats"] == 2.0
    assert notes[0]["duration"] == "half"


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
    original_note_id = score["measures"][0]["notes"][0]["note_id"]

    updated = edit_score(
        score_id,
        [
            {"type": "add_note", "measure_no": 1, "beat": 2, "note": {"pitch": "C5", "beats": 0.5}},
            {"type": "update_note", "note_id": original_note_id, "note": {"pitch": "G4"}},
            {"type": "update_tempo", "value": 96},
        ],
    )

    assert updated["tempo"] == 96
    assert updated["version"] == 2
    assert len(updated["measures"][0]["notes"]) == 2
    assert updated["measures"][0]["notes"][0]["pitch"] == "G4"

    added_note_id = next(note["note_id"] for note in updated["measures"][0]["notes"] if note["note_id"] != original_note_id)
    deleted = edit_score(score_id, [{"type": "delete_note", "note_id": added_note_id}])
    assert len(deleted["measures"][0]["notes"]) == 1

    reverted = undo_score(score_id)
    assert reverted["tempo"] == 96
    assert len(reverted["measures"][0]["notes"]) == 2

    redone = redo_score(score_id)
    assert len(redone["measures"][0]["notes"]) == 1

    with session_scope() as session:
        sheet = session.query(Sheet).filter_by(score_id=score_id).one()
        assert sheet.project_id == score["project_id"]
        assert sheet.note_data["version"] == redone["version"]
        assert sheet.bpm == redone["tempo"]
        assert sheet.key_sign == redone["key_signature"]
        assert sheet.time_sign == redone["time_signature"]


def test_score_export_builds_structured_manifests(score_database: dict[str, int | str]):
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
    assert midi_export["manifest"]["tracks"][0]["events"][0]["pitch"] == "A4"
    assert midi_export["download_url"].startswith("/storage/exports/")
    assert pdf_export["manifest"]["kind"] == "pdf"
    assert pdf_export["manifest"]["pages"]
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
