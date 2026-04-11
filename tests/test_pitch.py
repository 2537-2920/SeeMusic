from backend.core.pitch.audio_utils import estimate_duration_from_bytes, infer_audio_metadata
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.realtime_tuning import analyze_audio_frame


def test_detect_pitch_sequence_returns_data():
    result = detect_pitch_sequence("demo.wav")
    assert result
    assert "frequency" in result[0]
    assert "note" in result[0]
    assert result[0]["algorithm"] == "yin"


def test_infer_audio_metadata_uses_defaults():
    metadata = infer_audio_metadata("demo.wav")
    assert metadata["file_name"] == "demo.wav"
    assert metadata["sample_rate"] == 16000
    assert metadata["duration"] == 60.0
    assert metadata["analysis_id"].startswith("an_")


def test_estimate_duration_from_bytes_matches_sample_rate():
    assert estimate_duration_from_bytes(bytes(32000), sample_rate=16000) == 1.0
    assert estimate_duration_from_bytes(b"", sample_rate=16000) == 0.0


def test_realtime_tuning_uses_reference_frequency_when_provided():
    result = analyze_audio_frame(b"\x00" * 320, sample_rate=16000, reference_frequency=445.0)
    assert result["frequency"] == 445.0
    assert result["note"] == "A4"
    assert result["cents_offset"] == 0.0
