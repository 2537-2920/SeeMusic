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
    result = separate_tracks("demo.wav", model="demucs", stems=4)
    assert result["task_id"].startswith("sep_")
    assert len(result["tracks"]) == 4
    assert result["tracks"][0]["name"] == "vocal"
    assert result["status"] == "completed"
    assert result["model"] == "demucs"
    assert result["stems"] == 4


def test_separate_tracks_with_two_stems():
    result = separate_tracks("demo.wav", model="demucs", stems=2)
    assert len(result["tracks"]) == 2
    track_names = [t["name"] for t in result["tracks"]]
    assert "vocal" in track_names
    assert "accompaniment" in track_names


def test_separate_tracks_returns_track_metadata():
    result = separate_tracks("demo.wav", model="demucs", stems=2)
    for track in result["tracks"]:
        assert "name" in track
        assert "file_name" in track
        assert "download_url" in track
        assert "duration" in track
        assert isinstance(track["duration"], float)


def test_traditional_instruments_include_expected_presets():
    instruments = get_traditional_instruments()
    assert "guzheng" in instruments
    assert instruments["erhu"]["family"] == "bowed"

