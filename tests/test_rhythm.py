from backend.core.rhythm.beat_detection import detect_beats
from backend.core.rhythm.rhythm_analysis import score_rhythm


def test_beat_detection_returns_beats():
    result = detect_beats("demo.wav")
    assert "beat_times" in result


def test_rhythm_score_returns_score():
    result = score_rhythm([0.5, 1.0], [0.52, 1.02])
    assert "score" in result

