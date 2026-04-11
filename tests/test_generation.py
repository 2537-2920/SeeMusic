from backend.core.generation.chord_generation import generate_chord_sequence
from backend.core.generation.variation_suggestions import generate_variation_suggestions
from backend.core.separation.multi_track_separation import separate_tracks
from backend.core.traditional.traditional_instruments import get_traditional_instruments


def test_generate_chord_sequence_returns_context_and_chords():
    result = generate_chord_sequence("C", 120, "pop", [{"time": 0.0, "note": "C4"}])
    assert result["key"] == "C"
    assert result["style"] == "pop"
    assert result["melody_size"] == 1
    assert len(result["chords"]) == 3


def test_generate_variation_suggestions_returns_expected_shape():
    result = generate_variation_suggestions("score_001", "traditional", "medium")
    assert result["score_id"] == "score_001"
    assert result["style"] == "traditional"
    assert result["suggestions"]


def test_separate_tracks_returns_requested_stems():
    result = separate_tracks("demo.wav", model="demucs", stems=3)
    assert result["task_id"] == "sep_demo.wav"
    assert len(result["tracks"]) == 3
    assert result["tracks"][0]["name"] == "vocal"


def test_traditional_instruments_include_expected_presets():
    instruments = get_traditional_instruments()
    assert "guzheng" in instruments
    assert instruments["erhu"]["family"] == "bowed"

