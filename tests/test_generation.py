from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

import backend.core.dizi.audio_pipeline as dizi_audio_pipeline
import backend.core.guzheng.audio_pipeline as guzheng_audio_pipeline
import backend.core.guitar.audio_pipeline as guitar_audio_pipeline
from backend.core.dizi.audio_pipeline import generate_dizi_score_from_audio
from backend.core.dizi.notation import (
    generate_dizi_score,
    generate_dizi_score_from_pitch_sequence,
)
from backend.core.guzheng.audio_pipeline import generate_guzheng_score_from_audio
from backend.core.guzheng.notation import (
    generate_guzheng_score,
    generate_guzheng_score_from_pitch_sequence,
)
from backend.core.guitar.audio_pipeline import generate_guitar_lead_sheet_from_audio
from backend.core.guitar.lead_sheet import generate_guitar_lead_sheet, generate_guitar_lead_sheet_from_musicxml
from backend.core.generation.chord_generation import generate_chord_sequence
from backend.core.generation.transpose_suggestions import generate_transpose_suggestions
from backend.core.generation.variation_suggestions import generate_variation_suggestions
from backend.core.score.note_mapping import note_to_frequency
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.core.separation.multi_track_separation import separate_tracks
from backend.core.traditional.traditional_instruments import get_traditional_instruments


@pytest.fixture
def temp_audio_bytes():
    """Generate temporary audio bytes for testing."""
    import tempfile
    from pathlib import Path
    
    sr = 44100
    duration = 3  # 3 seconds
    t = np.linspace(0, duration, sr * duration)
    # Generate a simple sine wave
    y = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    # Write to temporary file and read back as bytes
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = f.name
    
    try:
        sf.write(temp_path, y, sr)
        with open(temp_path, 'rb') as f:
            audio_bytes = f.read()
        return audio_bytes
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_generate_chord_sequence_returns_context_and_chords():
    result = generate_chord_sequence("C", 120, "pop", [{"time": 0.0, "note": "C4"}])
    assert result["key"] == "C"
    assert result["style"] == "pop"
    assert result["melody_size"] == 1
    assert result["lead_sheet_type"] == "guitar_chord_chart"
    assert result["chords"]


def test_generate_guitar_lead_sheet_returns_measure_layout_shapes_and_capo():
    result = generate_guitar_lead_sheet(
        key="C",
        tempo=120,
        time_signature="4/4",
        style="folk",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 1.0, "pitch": "C4"},
            {"measure_no": 1, "start_beat": 2.0, "beats": 1.0, "pitch": "E4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 1.0, "pitch": "G4"},
            {"measure_no": 1, "start_beat": 4.0, "beats": 1.0, "pitch": "B4"},
        ],
    )

    assert result["measures"]
    assert result["chords"]
    assert result["guitar_shapes"]
    assert result["strumming_pattern"]["pattern"]
    assert "capo" in result["capo_suggestion"]
    assert all("shape" in chord for chord in result["chords"])
    assert result["sections"]
    assert result["display_lines"]
    assert result["display_sections"]
    assert result["chord_diagrams"]
    assert "lyric_lines" not in result
    assert all("lyric_text" not in line for line in result["display_lines"])


def test_generate_guitar_lead_sheet_returns_structured_strumming_guidance():
    melody = [
        {
            "measure_no": measure_no,
            "start_beat": 1.0,
            "beats": 2.0,
            "pitch": ["C4", "E4", "G4", "A4"][(measure_no - 1) % 4],
        }
        for measure_no in range(1, 17)
    ]

    result = generate_guitar_lead_sheet(
        key="C",
        tempo=112,
        time_signature="4/4",
        style="folk",
        melody=melody,
    )

    strumming = result["strumming_pattern"]
    section_patterns = strumming["section_patterns"]

    assert strumming["pattern"] == "D DU UDU"
    assert "↓" in strumming["display_pattern"]
    assert strumming["counting"] == "1 & 2 & 3 & 4 &"
    assert len(strumming["stroke_grid"]) == 8
    assert len(section_patterns) >= 2
    assert section_patterns[0]["section_role"] == "verse"
    assert section_patterns[1]["section_role"] == "chorus"
    assert section_patterns[0]["display_pattern"]
    assert section_patterns[1]["display_pattern"]


def test_generate_guitar_lead_sheet_from_musicxml_uses_melody_staff_without_lyrics_metadata():
    source_score = build_score_from_pitch_sequence(
        [
            {"time": 0.0, "frequency": 261.63, "duration": 0.5, "note": "C4"},
            {"time": 0.5, "frequency": 293.66, "duration": 0.5, "note": "D4"},
        ],
        tempo=120,
        time_signature="4/4",
        key_signature="C",
        title="童年",
        arrangement_mode="piano_solo",
    )

    result = generate_guitar_lead_sheet_from_musicxml(
        musicxml=source_score["musicxml"],
        key="C",
        tempo=120,
        time_signature="4/4",
        style="folk",
        title="童年",
    )

    assert result["melody_size"] == 2
    assert result["display_sections"][0]["display_lines"][0]["tokens"]
    assert all(token["type"] != "lyric" for token in result["display_sections"][0]["display_lines"][0]["tokens"])


def test_generate_guitar_lead_sheet_resolves_secondary_dominant_before_target():
    result = generate_guitar_lead_sheet(
        key="C",
        tempo=120,
        time_signature="4/4",
        style="pop",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "C#4"},
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "E4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 2.0, "pitch": "D4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 2.0, "pitch": "F4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 2.0, "pitch": "A4"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 2, "start_beat": 3.0, "beats": 2.0, "pitch": "C4"},
        ],
    )

    symbols = [chord["symbol"] for chord in result["chords"]]
    assert "A7" in symbols
    secondary_index = symbols.index("A7")
    assert result["chords"][secondary_index]["source"] == "secondary_dominant"
    assert secondary_index + 1 < len(result["chords"])
    assert result["chords"][secondary_index + 1]["symbol"] == "Dm"


def test_generate_guitar_lead_sheet_can_use_borrowed_chords_in_major_key():
    result = generate_guitar_lead_sheet(
        key="C",
        tempo=120,
        time_signature="4/4",
        style="folk",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "C4"},
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "E4"},
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 2.0, "pitch": "F4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 2.0, "pitch": "Ab4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 2.0, "pitch": "C5"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 2.0, "pitch": "B4"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 2.0, "pitch": "D5"},
            {"measure_no": 2, "start_beat": 3.0, "beats": 2.0, "pitch": "C4"},
            {"measure_no": 2, "start_beat": 3.0, "beats": 2.0, "pitch": "E4"},
            {"measure_no": 2, "start_beat": 3.0, "beats": 2.0, "pitch": "G4"},
        ],
    )

    assert any(chord["source"] == "borrowed" for chord in result["chords"])
    assert any(chord["symbol"] == "Fm" for chord in result["chords"])


def test_generate_guzheng_score_returns_jianpu_positions_and_techniques():
    result = generate_guzheng_score(
        key="G",
        tempo=96,
        time_signature="4/4",
        style="traditional",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 1.0, "pitch": "B4"},
            {"measure_no": 1, "start_beat": 4.0, "beats": 1.0, "pitch": "C5"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 1.0, "pitch": "D5"},
        ],
        title="古筝测试谱",
    )

    assert result["lead_sheet_type"] == "guzheng_jianpu_chart"
    assert result["render_source"] == "jianpu_ir"
    assert result["layout_mode"] == "preview"
    assert "fingering" in result["annotation_layers"]
    assert result["jianpu_ir"]["meta"]["instrument_type"] == "guzheng"
    assert result["jianpu_ir"]["lines"]
    assert result["jianpu_ir"]["pages"]
    assert result["instrument_profile"]["tuning"] == "21弦 D调定弦"
    assert result["measures"]
    assert result["phrase_lines"]
    assert result["sections"]
    first_note = result["measures"][0]["notes"][0]
    assert first_note["degree_display"] == "1"
    assert first_note["string_label"].endswith("弦")
    assert "摇指候选" in first_note["technique_tags"]
    assert result["technique_summary"]["counts"]["摇指候选"] >= 1
    assert result["pentatonic_summary"]["press_note_candidates"] >= 1


def test_generate_guzheng_score_from_pitch_sequence_marks_press_note_candidates():
    result = generate_guzheng_score_from_pitch_sequence(
        pitch_sequence=[
            {"time": 0.0, "frequency": 392.0, "duration": 1.0, "note": "G4"},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5, "note": "B4"},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5, "note": "C5"},
        ],
        tempo=96,
        time_signature="4/4",
        key="G",
    )

    assert result["lead_sheet_type"] == "guzheng_jianpu_chart"
    assert result["jianpu_ir"]["statistics"]["press_note_candidates"] >= 1
    assert any(note["press_note_candidate"] for measure in result["measures"] for note in measure["notes"])
    assert result["string_positions"]


def test_generate_guzheng_score_supports_minor_open_string_mapping():
    result = generate_guzheng_score(
        key="Am",
        tempo=88,
        time_signature="4/4",
        style="traditional",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 1.0, "pitch": "A4"},
            {"measure_no": 1, "start_beat": 2.0, "beats": 1.0, "pitch": "C5"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 1.0, "pitch": "D5"},
            {"measure_no": 1, "start_beat": 4.0, "beats": 1.0, "pitch": "E5"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 2.0, "pitch": "G5"},
        ],
        title="小调古筝测试谱",
    )

    notes_by_degree = {
        int(note["degree_no"]): note
        for measure in result["measures"]
        for note in measure["notes"]
    }

    assert result["lead_sheet_type"] == "guzheng_jianpu_chart"
    assert result["key"] == "Am"
    assert notes_by_degree[4]["is_pentatonic"] is True
    assert notes_by_degree[4]["press_note_candidate"] is False
    assert notes_by_degree[4]["string_label"].endswith("弦")
    assert notes_by_degree[7]["is_pentatonic"] is True
    assert notes_by_degree[7]["press_note_candidate"] is False
    assert result["string_positions"]


def test_generate_dizi_score_returns_fingerings_and_techniques():
    result = generate_dizi_score(
        key="G",
        tempo=92,
        time_signature="4/4",
        flute_type="G",
        style="traditional",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 0.5, "pitch": "G#4"},
            {"measure_no": 1, "start_beat": 3.5, "beats": 1.5, "pitch": "A4"},
            {"measure_no": 2, "start_beat": 1.0, "beats": 2.0, "pitch": "D5"},
        ],
        title="笛子测试谱",
    )

    assert result["lead_sheet_type"] == "dizi_jianpu_chart"
    assert result["render_source"] == "jianpu_ir"
    assert result["layout_mode"] == "preview"
    assert "technique" in result["annotation_layers"]
    assert result["jianpu_ir"]["meta"]["instrument_type"] == "dizi"
    assert result["jianpu_ir"]["meta"]["flute_type"] == "G"
    assert result["jianpu_ir"]["lines"]
    assert result["jianpu_ir"]["pages"]
    assert result["flute_type"] == "G"
    assert result["measures"]
    assert result["phrase_lines"]
    assert result["sections"]
    first_note = result["measures"][0]["notes"][0]
    assert first_note["degree_display"] == "1"
    assert first_note["hole_pattern"]
    assert "颤音/长音保持候选" in first_note["technique_tags"]
    assert result["playability_summary"]["half_hole_candidates"] >= 1
    assert result["fingerings"]


def test_generate_dizi_score_from_pitch_sequence_marks_half_hole_candidates():
    result = generate_dizi_score_from_pitch_sequence(
        pitch_sequence=[
            {"time": 0.0, "frequency": 392.0, "duration": 0.5, "note": "G4"},
            {"time": 0.5, "frequency": 415.3, "duration": 0.5, "note": "G#4"},
            {"time": 1.0, "frequency": 440.0, "duration": 1.0, "note": "A4"},
        ],
        tempo=96,
        time_signature="4/4",
        flute_type="G",
        key="G",
    )

    assert result["lead_sheet_type"] == "dizi_jianpu_chart"
    assert result["jianpu_ir"]["statistics"]["half_hole_candidates"] >= 1
    assert any(note["half_hole_candidate"] for measure in result["measures"] for note in measure["notes"])
    assert result["fingerings"]


def test_generate_variation_suggestions_returns_expected_shape():
    result = generate_variation_suggestions("score_001", "traditional", "medium")
    assert result["score_id"] == "score_001"
    assert result["style"] == "traditional"
    assert result["suggestions"]


def test_generate_transpose_suggestions_returns_cross_gender_baseline():
    result = generate_transpose_suggestions(
        analysis_id="an_transpose_001",
        current_key="C",
        source_gender="male",
        target_gender="female",
        pitch_sequence=[],
    )

    suggestions = {item["tier"]: item for item in result["suggestions"]}
    assert result["current_key"] == "C"
    assert result["used_audio_adjustment"] is False
    assert suggestions["recommended"]["semitones"] == 4
    assert suggestions["recommended"]["target_key"] == "E"
    assert suggestions["conservative"]["semitones"] == 3
    assert suggestions["bright"]["semitones"] == 5


def test_generate_transpose_suggestions_returns_same_gender_defaults():
    result = generate_transpose_suggestions(
        analysis_id="an_transpose_002",
        current_key="Am",
        source_gender="female",
        target_gender="female",
        pitch_sequence=[],
    )

    tiers = {item["tier"]: item for item in result["suggestions"]}
    assert tiers["recommended"]["semitones"] == 0
    assert tiers["recommended"]["target_key"] == "Am"
    assert tiers["lower"]["semitones"] == -2
    assert tiers["bright"]["semitones"] == 2


def test_generate_transpose_suggestions_uses_audio_range_to_adjust_main_recommendation():
    pitch_sequence = [
        {"time": index * 0.2, "frequency": note_to_frequency(note), "duration": 0.2, "confidence": 0.95}
        for index, note in enumerate(["B2", "C3", "C3", "D3", "C3", "B2", "C3", "D3", "C3", "B2"])
    ]

    result = generate_transpose_suggestions(
        analysis_id="an_transpose_003",
        current_key="C",
        source_gender="male",
        target_gender="female",
        pitch_sequence=pitch_sequence,
    )

    recommended = next(item for item in result["suggestions"] if item["tier"] == "recommended")
    assert result["used_audio_adjustment"] is True
    assert result["detected_range"]["median_note"] == "C3"
    assert recommended["semitones"] == 6
    assert recommended["target_key"] == "F#"


def test_generate_transpose_suggestions_falls_back_when_audio_points_are_insufficient():
    pitch_sequence = [
        {"time": 0.0, "frequency": note_to_frequency("C3"), "duration": 0.2, "confidence": 0.95},
        {"time": 0.2, "frequency": note_to_frequency("D3"), "duration": 0.2, "confidence": 0.95},
        {"time": 0.4, "frequency": note_to_frequency("E3"), "duration": 0.2, "confidence": 0.95},
    ]

    result = generate_transpose_suggestions(
        analysis_id="an_transpose_004",
        current_key="G",
        source_gender="male",
        target_gender="female",
        pitch_sequence=pitch_sequence,
    )

    recommended = next(item for item in result["suggestions"] if item["tier"] == "recommended")
    assert result["used_audio_adjustment"] is False
    assert result["detected_range"] is None
    assert recommended["semitones"] == 4


def test_separate_tracks_returns_requested_stems(temp_audio_bytes):
    result = separate_tracks("demo.wav", model="demucs", stems=4, audio_bytes=temp_audio_bytes)
    assert result["task_id"].startswith("sep_")
    assert len(result["tracks"]) == 4
    assert result["tracks"][0]["name"] == "vocal"
    assert result["status"] == "completed"
    assert result["model"] == "demucs"
    assert result["stems"] == 4


def test_separate_tracks_with_two_stems(temp_audio_bytes):
    result = separate_tracks("demo.wav", model="demucs", stems=2, audio_bytes=temp_audio_bytes)
    assert len(result["tracks"]) == 2
    track_names = [t["name"] for t in result["tracks"]]
    assert "vocal" in track_names
    assert "accompaniment" in track_names


def test_separate_tracks_returns_track_metadata(temp_audio_bytes):
    result = separate_tracks("demo.wav", model="demucs", stems=2, audio_bytes=temp_audio_bytes)
    for track in result["tracks"]:
        assert "name" in track
        assert "file_name" in track
        assert "download_url" in track
        assert "duration" in track
        assert isinstance(track["duration"], float)


def test_traditional_instruments_include_expected_presets():
    instruments = get_traditional_instruments()
    assert "guzheng" in instruments
    assert "dizi" in instruments
    assert "G" in instruments["dizi"]["supported_flute_types"]
    assert instruments["erhu"]["family"] == "bowed"


def test_generate_guitar_lead_sheet_from_audio_prefers_vocal_track(monkeypatch: pytest.MonkeyPatch, tmp_path):
    sample_rate = 16000
    duration_seconds = 1.0
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    vocal = 0.35 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    accompaniment = 0.05 * np.sin(2 * np.pi * 220 * t).astype(np.float32)

    vocal_path = tmp_path / "vocal.wav"
    accompaniment_path = tmp_path / "accompaniment.wav"
    sf.write(vocal_path, vocal, sample_rate)
    sf.write(accompaniment_path, accompaniment, sample_rate)

    def fake_separate_tracks(file_name: str, model: str, stems: int, audio_bytes: bytes | None = None, sample_rate: int = 44100):
        return {
            "task_id": "sep_test",
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

    monkeypatch.setattr(guitar_audio_pipeline, "separate_tracks", fake_separate_tracks)

    result = generate_guitar_lead_sheet_from_audio(
        file_name="song.wav",
        audio_bytes=b"placeholder",
        analysis_id="an_test_guitar_audio",
        key="",
        tempo=120,
        time_signature="4/4",
        style="pop",
        sample_rate=sample_rate,
    )

    assert result["melody_track"]["name"] == "vocal"
    assert result["melody_track"]["source"] == "separated_track"
    assert result["pitch_sequence"]
    assert result["detected_key_signature"]
    assert result["chords"]


def test_generate_guzheng_score_from_audio_prefers_vocal_track_and_returns_debug_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    sample_rate = 16000
    duration_seconds = 1.0
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    vocal = 0.35 * np.sin(2 * np.pi * 392 * t).astype(np.float32)
    accompaniment = 0.05 * np.sin(2 * np.pi * 220 * t).astype(np.float32)

    vocal_path = tmp_path / "vocal.wav"
    accompaniment_path = tmp_path / "accompaniment.wav"
    sf.write(vocal_path, vocal, sample_rate)
    sf.write(accompaniment_path, accompaniment, sample_rate)

    def fake_separate_tracks(file_name: str, model: str, stems: int, audio_bytes: bytes | None = None, sample_rate: int = 44100):
        return {
            "task_id": "sep_test_guzheng",
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
            "beat_quality": {"confidence": 0.7},
            "num_beats": 4,
        }

    monkeypatch.setattr(guzheng_audio_pipeline, "separate_tracks", fake_separate_tracks)
    monkeypatch.setattr(guzheng_audio_pipeline, "detect_beats", fake_detect_beats)

    result = generate_guzheng_score_from_audio(
        file_name="song.wav",
        audio_bytes=b"placeholder",
        analysis_id="an_test_guzheng_audio",
        key="",
        tempo=120,
        time_signature="4/4",
        style="traditional",
        sample_rate=sample_rate,
    )

    assert result["melody_track"]["name"] == "vocal"
    assert result["melody_track"]["source"] == "separated_track"
    assert result["tempo"] == 96
    assert result["tempo_detection"]["used_detected_tempo"] is True
    assert result["pitch_sequence"]
    assert result["string_positions"]


def test_generate_dizi_score_from_audio_prefers_vocal_track_and_returns_debug_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    sample_rate = 16000
    duration_seconds = 1.0
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    vocal = 0.35 * np.sin(2 * np.pi * 392 * t).astype(np.float32)
    accompaniment = 0.05 * np.sin(2 * np.pi * 220 * t).astype(np.float32)

    vocal_path = tmp_path / "vocal.wav"
    accompaniment_path = tmp_path / "accompaniment.wav"
    sf.write(vocal_path, vocal, sample_rate)
    sf.write(accompaniment_path, accompaniment, sample_rate)

    def fake_separate_tracks(file_name: str, model: str, stems: int, audio_bytes: bytes | None = None, sample_rate: int = 44100):
        return {
            "task_id": "sep_test_dizi",
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
            "beat_quality": {"confidence": 0.7},
            "num_beats": 4,
        }

    monkeypatch.setattr(dizi_audio_pipeline, "separate_tracks", fake_separate_tracks)
    monkeypatch.setattr(dizi_audio_pipeline, "detect_beats", fake_detect_beats)

    result = generate_dizi_score_from_audio(
        file_name="song.wav",
        audio_bytes=b"placeholder",
        analysis_id="an_test_dizi_audio",
        key="",
        tempo=120,
        time_signature="4/4",
        flute_type="G",
        style="traditional",
        sample_rate=sample_rate,
    )

    assert result["melody_track"]["name"] == "vocal"
    assert result["melody_track"]["source"] == "separated_track"
    assert result["tempo"] == 96
    assert result["tempo_detection"]["used_detected_tempo"] is True
    assert result["pitch_sequence"]
    assert result["fingerings"]
