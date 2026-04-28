from __future__ import annotations

import xml.etree.ElementTree as ET

import numpy as np
import pytest
import soundfile as sf

from backend.core.piano.arrangement import _resolve_hand_spacing
import backend.core.score.audio_pipeline as score_audio_pipeline
from backend.core.score.audio_pipeline import prepare_piano_score_from_audio
from backend.core.score.note_mapping import (
    beats_per_measure,
    beats_to_duration_label,
    frequency_to_note,
    note_to_frequency,
    note_to_midi,
    parse_time_signature,
    quantize_beats,
)
from backend.core.score.key_detection import analyze_key_signature
from backend.core.score.sheet_extraction import _normalize_pitch_items, _simplify_events_for_readability, build_score_from_pitch_sequence
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


def _child_text(element: ET.Element, tag_name: str, default: str = "") -> str:
    child = next((node for node in element if _local_name(node.tag) == tag_name), None)
    text = child.text if child is not None else None
    return (text or default).strip()


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
    assert round(note_to_frequency("Cb4"), 2) == round(note_to_frequency("B3"), 2)
    assert round(note_to_frequency("E#4"), 2) == round(note_to_frequency("F4"), 2)
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


def test_analyze_key_signature_prefers_g_major_for_g_major_melody():
    result = analyze_key_signature(
        [
            {"time": 0.0, "frequency": 392.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5},
            {"time": 2.0, "frequency": 587.33, "duration": 0.5},
            {"time": 2.5, "frequency": 659.25, "duration": 0.5},
            {"time": 3.0, "frequency": 739.99, "duration": 0.5},
            {"time": 3.5, "frequency": 783.99, "duration": 1.0},
        ]
    )

    assert result["key_signature"] == "G"


def test_build_score_from_pitch_sequence_auto_detects_key_and_uses_key_signature_accidentals():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 392.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5},
            {"time": 2.0, "frequency": 587.33, "duration": 0.5},
            {"time": 2.5, "frequency": 659.25, "duration": 0.5},
            {"time": 3.0, "frequency": 739.99, "duration": 0.5},
            {"time": 3.5, "frequency": 783.99, "duration": 1.0},
        ],
        tempo=120,
        time_signature="4/4",
        auto_detect_key=True,
        title="Detected Key Score",
    )

    root = _xml_root(score["musicxml"])
    first_fifths = next(element for element in _all_elements(root, "fifths"))

    assert score["key_signature"] == "G"
    assert first_fifths.text == "1"
    assert not _all_elements(root, "accidental")


def test_build_score_from_pitch_sequence_respells_flat_notes_for_flat_keys():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 349.23, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 466.16, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 1.0},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="F",
        title="Flat Spelling Score",
    )

    root = _xml_root(score["musicxml"])
    pitched_notes = [note for note in _all_elements(root, "note") if not any(_local_name(child.tag) == "rest" for child in note)]
    third_pitch = next(child for child in pitched_notes[2] if _local_name(child.tag) == "pitch")
    step = next(child.text for child in third_pitch if _local_name(child.tag) == "step")
    alter = next(child.text for child in third_pitch if _local_name(child.tag) == "alter")

    assert step == "B"
    assert alter == "-1"


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


def test_build_score_from_pitch_sequence_can_generate_two_hand_piano_arrangement():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 392.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5},
            {"time": 2.0, "frequency": 587.33, "duration": 0.5},
            {"time": 2.5, "frequency": 659.25, "duration": 0.5},
            {"time": 3.0, "frequency": 698.46, "duration": 0.5},
            {"time": 3.5, "frequency": 783.99, "duration": 0.5},
        ],
        tempo=96,
        time_signature="4/4",
        key_signature="G",
        title="Piano Arrangement",
        arrangement_mode="piano_solo",
    )

    root = _xml_root(score["musicxml"])
    staves = [element for element in _all_elements(root, "staves") if (element.text or "").strip() == "2"]
    backups = _all_elements(root, "backup")
    staff_numbers = {child.text for child in _all_elements(root, "staff") if child.text}

    assert score["score_mode"] == "piano_two_hand_arrangement"
    assert score["piano_arrangement"]["arrangement_type"] == "piano_solo"
    assert score["piano_arrangement"]["chords"]
    assert score["piano_arrangement"]["left_hand_pattern"]["name"]
    assert staves
    assert backups
    assert {"1", "2"} <= staff_numbers


def test_build_score_from_pitch_sequence_writes_lyrics_to_right_hand_only():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 392.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="G",
        title="Lyrics Piano Arrangement",
        arrangement_mode="piano_solo",
        lyrics_payload={
            "status": "imported",
            "source": "id3_sylt",
            "has_timestamps": True,
            "timing_kind": "token",
            "lines": [
                {
                    "time": 0.0,
                    "text": "你好世界",
                    "tokens": [
                        {"text": "你", "time": 0.0},
                        {"text": "好", "time": 0.5},
                        {"text": "世", "time": 1.0},
                        {"text": "界", "time": 1.5},
                    ],
                }
            ],
            "line_count": 1,
            "warnings": [],
        },
    )

    root = _xml_root(score["musicxml"])
    lyric_notes = [note for note in _all_elements(root, "note") if next((child for child in note if _local_name(child.tag) == "lyric"), None)]

    assert score["lyrics_import"]["source"] == "id3_sylt"
    assert score["lyrics_import"]["alignment_mode"] == "timestamped_tokens"
    assert score["summary"]["has_lyrics"] is True
    assert score["summary"]["lyric_note_count"] == 4
    assert [_child_text(next(child for child in note if _local_name(child.tag) == "lyric"), "text") for note in lyric_notes] == ["你", "好", "世", "界"]
    assert all(_child_text(note, "staff", "1") == "1" for note in lyric_notes)


def test_build_score_from_pitch_sequence_only_labels_first_segment_of_tied_note():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 2.5},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="C",
        title="Tied Lyrics Score",
        arrangement_mode="piano_solo",
        lyrics_payload={
            "status": "imported",
            "source": "id3_uslt",
            "has_timestamps": False,
            "timing_kind": "none",
            "lines": [{"time": None, "text": "长音", "tokens": []}],
            "line_count": 1,
            "warnings": [],
        },
    )

    root = _xml_root(score["musicxml"])
    lyric_notes = [note for note in _all_elements(root, "note") if next((child for child in note if _local_name(child.tag) == "lyric"), None)]

    assert len(lyric_notes) == 1
    assert score["summary"]["lyric_note_count"] == 1
    assert _child_text(next(child for child in lyric_notes[0] if _local_name(child.tag) == "lyric"), "text") == "长音"


def test_build_score_from_pitch_sequence_trims_trailing_full_rest_measures():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 0.5},
            {"time": 0.5, "frequency": 0.0, "duration": 12.0, "note": "Rest"},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="C",
        title="Trim Tail Rest Score",
        arrangement_mode="melody",
    )

    root = _xml_root(score["musicxml"])
    measures = _all_elements(root, "measure")

    assert score["summary"]["measure_count"] == 1
    assert len(measures) == 1


def test_build_score_from_pitch_sequence_writes_plain_text_tempo_marking():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 0.5},
        ],
        tempo=63,
        time_signature="4/4",
        key_signature="G",
        title="Tempo Mark Score",
        arrangement_mode="melody",
    )

    root = _xml_root(score["musicxml"])
    words = _all_elements(root, "words")
    metronomes = _all_elements(root, "metronome")
    sounds = _all_elements(root, "sound")

    assert any((element.text or "").strip() == "Quarter = 63" for element in words)
    assert not metronomes
    assert any(element.attrib.get("tempo") == "63" for element in sounds)


def test_piano_arrangement_writes_visual_attributes_only_in_initial_measure():
    score = build_score_from_pitch_sequence(
        [
            {"start": 0.0, "end": 2.0, "note": "G4", "frequency_avg": 392.0},
            {"start": 2.0, "end": 4.0, "note": "A4", "frequency_avg": 440.0},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="G",
        title="Compact Piano Attributes",
        arrangement_mode="piano_solo",
    )

    root = _xml_root(score["musicxml"])
    measures = _all_elements(root, "measure")
    later_attributes = [
        next((child for child in measure if _local_name(child.tag) == "attributes"), None)
        for measure in measures[1:]
    ]

    assert len(measures) == 2
    assert next((child for child in measures[0] if _local_name(child.tag) == "attributes"), None) is not None
    assert all(attributes is None for attributes in later_attributes)


def test_build_score_from_pitch_sequence_can_keep_precise_melody_mode_without_piano_arrangement():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 392.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5},
        ],
        tempo=96,
        time_signature="4/4",
        key_signature="G",
        title="Precise Melody",
        arrangement_mode="melody",
    )

    root = _xml_root(score["musicxml"])
    staves = [element for element in _all_elements(root, "staves") if (element.text or "").strip() == "2"]
    backups = _all_elements(root, "backup")

    assert score["arrangement_mode"] == "melody"
    assert score["score_mode"] == "melody_transcription"
    assert "piano_arrangement" not in score
    assert not staves
    assert not backups


def test_piano_arrangement_raises_low_right_hand_melody_into_c4_to_c6_range():
    score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 196.0, "duration": 0.5},
            {"time": 0.5, "frequency": 220.0, "duration": 0.5},
            {"time": 1.0, "frequency": 246.94, "duration": 0.5},
            {"time": 1.5, "frequency": 261.63, "duration": 0.5},
        ],
        tempo=88,
        time_signature="4/4",
        key_signature="G",
        title="Raised Melody",
        arrangement_mode="piano_solo",
    )

    right_hand_midis = [
        note_to_midi(note["pitch"])
        for measure in score["piano_arrangement"]["arranged_measures"]
        for note in measure.get("right_hand_notes") or []
        if not note.get("is_rest")
    ]

    assert score["piano_arrangement"]["right_hand_range_adjustment"]["global_octave_shift"] >= 1
    assert right_hand_midis
    assert min(right_hand_midis) >= 60
    assert max(right_hand_midis) <= 84


def test_resolve_hand_spacing_prefers_lowering_left_hand_when_too_close():
    right_hand_notes = [
        {"pitch": "D4", "beats": 1.0, "start_beat": 1.0, "is_rest": False},
    ]
    left_hand_notes = [
        {"pitch": "B3", "beats": 1.0, "start_beat": 1.0, "is_rest": False},
    ]

    adjusted_right, adjusted_left, right_lifts, left_drops = _resolve_hand_spacing(right_hand_notes, left_hand_notes)

    assert right_lifts == 0
    assert left_drops == 1
    assert adjusted_right[0]["pitch"] == "D4"
    assert adjusted_left[0]["pitch"] == "B2"


def test_prepare_piano_score_from_audio_prefers_vocal_track_and_detects_tempo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    sample_rate = 16000
    duration_seconds = 1.0
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    vocal = 0.35 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    accompaniment = 0.05 * np.sin(2 * np.pi * 220 * t).astype(np.float32)

    vocal_path = tmp_path / "vocal.wav"
    accompaniment_path = tmp_path / "accompaniment.wav"
    sf.write(vocal_path, vocal, sample_rate)
    sf.write(accompaniment_path, accompaniment, sample_rate)

    def fake_separate_tracks(
        file_name: str,
        model: str,
        stems: int,
        audio_bytes: bytes | None = None,
        sample_rate: int = 44100,
    ):
        return {
            "task_id": "sep_test_piano",
            "status": "completed",
            "model": model,
            "stems": stems,
            "sample_rate": sample_rate,
            "tracks": [
                {
                    "name": "vocal",
                    "file_name": vocal_path.name,
                    "file_path": str(vocal_path),
                    "duration": duration_seconds,
                },
                {
                    "name": "accompaniment",
                    "file_name": accompaniment_path.name,
                    "file_path": str(accompaniment_path),
                    "duration": duration_seconds,
                },
            ],
            "warnings": [],
        }

    def fake_detect_beats(
        audio_path: str,
        bpm_hint: float | None = None,
        sensitivity: float = 0.5,
        audio_bytes: bytes | None = None,
    ):
        return {
            "beat_times": [0.0, 0.625, 1.25, 1.875],
            "bpm": 96.0,
            "primary_bpm": 96.0,
            "bpm_candidates": [96.0, 48.0],
            "beat_strengths": [0.4, 0.42, 0.38, 0.4],
            "beat_quality": {"confidence": 0.72, "regularity": 0.7, "strength": 0.62},
            "num_beats": 4,
            "trimmed_start": 0.0,
        }

    monkeypatch.setattr(score_audio_pipeline, "separate_tracks", fake_separate_tracks)
    monkeypatch.setattr(score_audio_pipeline, "detect_beats", fake_detect_beats)

    result = prepare_piano_score_from_audio(
        file_name="song.wav",
        audio_bytes=b"placeholder",
        analysis_id="an_test_piano_audio",
        fallback_tempo=120,
        time_signature="4/4",
        sample_rate=sample_rate,
    )

    assert result["tempo"] == 96
    assert result["tempo_detection"]["used_detected_tempo"] is True
    assert result["melody_track"]["name"] == "vocal"
    assert result["melody_track"]["source"] == "separated_track"
    assert result["pitch_sequence"]
    assert result["detected_key_signature"]


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


def test_normalize_pitch_items_trims_overlapping_notes():
    normalized = _normalize_pitch_items(
        [
            {"time": 0.0, "frequency": 261.63, "duration": 0.6},
            {"time": 0.4, "frequency": 293.66, "duration": 0.4},
        ],
        tempo=120,
    )

    assert len(normalized) == 2
    assert normalized[0]["end_time"] <= normalized[1]["start_time"]
    assert normalized[1]["duration_seconds"] == 0.2


def test_simplify_events_for_readability_absorbs_short_ornament_into_next_note():
    simplified = _simplify_events_for_readability(
        [
            {"pitch": "C4", "frequency": 261.63, "duration_seconds": 0.05, "is_rest": False, "start_time": 0.0, "end_time": 0.05},
            {"pitch": "D4", "frequency": 293.66, "duration_seconds": 0.5, "is_rest": False, "start_time": 0.05, "end_time": 0.55},
        ],
        tempo=120,
    )

    assert len(simplified) == 1
    assert simplified[0]["pitch"] == "D4"
    assert simplified[0]["duration_seconds"] == 0.55


def test_simplify_events_for_readability_median_filters_spiky_pitch_outlier():
    simplified = _simplify_events_for_readability(
        [
            {"pitch": "C4", "frequency": 261.63, "duration_seconds": 0.2, "is_rest": False, "start_time": 0.0, "end_time": 0.2},
            {"pitch": "A5", "frequency": 880.0, "duration_seconds": 0.2, "is_rest": False, "start_time": 0.2, "end_time": 0.4},
            {"pitch": "D4", "frequency": 293.66, "duration_seconds": 0.2, "is_rest": False, "start_time": 0.4, "end_time": 0.6},
        ],
        tempo=120,
    )

    assert [event["pitch"] for event in simplified] == ["C4", "D4"]
    assert simplified[1]["duration_seconds"] == 0.4


def test_score_editing_and_history_round_trip(score_database: dict[str, int | str]):
    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "title": "Unit Test Score",
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
            "lyrics_payload": {
                "status": "imported",
                "source": "id3_uslt",
                "has_timestamps": False,
                "timing_kind": "none",
                "lines": [{"time": None, "text": "测试歌词", "tokens": []}],
                "line_count": 1,
                "warnings": [],
            },
        }
    )
    score_id = score["score_id"]

    updated = edit_score(score_id, _replace_tempo(score["musicxml"], 96))
    fetched = get_score(score_id)

    assert updated["tempo"] == 96
    assert updated["version"] == 2
    assert fetched["tempo"] == 96
    assert "96" in updated["musicxml"]
    assert "测试歌词" in updated["musicxml"]
    assert updated["summary"]["has_lyrics"] is True
    assert updated["summary"]["lyric_note_count"] == 1

    reverted = undo_score(score_id)
    assert reverted["tempo"] == 120
    assert reverted["version"] == 1
    assert "测试歌词" in reverted["musicxml"]

    redone = redo_score(score_id)
    assert redone["tempo"] == 96
    assert redone["version"] == 2
    assert "测试歌词" in redone["musicxml"]

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
