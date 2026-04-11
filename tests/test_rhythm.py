from backend.core.rhythm.beat_detection import detect_beats
from backend.core.rhythm.rhythm_analysis import score_rhythm


def test_beat_detection_returns_beats():
    result = detect_beats("demo.wav")
    assert "beat_times" in result
    assert result["bpm"] == 120.0


def test_rhythm_score_returns_score():
    result = score_rhythm([0.5, 1.0], [0.52, 1.02])
    assert "score" in result
    assert result["score"] >= 90


def test_beat_detection_respects_hint_and_sensitivity():
    result = detect_beats("demo.wav", bpm_hint=96, sensitivity=0.8)
    assert result["bpm"] == 96.0
    assert result["sensitivity"] == 0.8


def test_rhythm_score_marks_large_deviations_as_errors():
    result = score_rhythm([0.5, 1.0], [0.7, 0.9])
    assert len(result["errors"]) == 2
    assert all(error["level"] == "major" for error in result["errors"])
