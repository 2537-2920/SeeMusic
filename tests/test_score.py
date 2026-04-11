from backend.core.score.sheet_extraction import build_score_from_pitch_sequence


def test_build_score_from_pitch_sequence_returns_score():
    score = build_score_from_pitch_sequence([{ "time": 0.0, "frequency": 440.0, "duration": 0.5 }])
    assert score["score_id"]
    assert score["measures"]

