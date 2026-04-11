from backend.core.pitch.pitch_detection import detect_pitch_sequence


def test_detect_pitch_sequence_returns_data():
    result = detect_pitch_sequence("demo.wav")
    assert result
    assert "frequency" in result[0]

