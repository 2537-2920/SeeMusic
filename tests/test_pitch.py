import math
import struct

from backend.core.pitch.audio_utils import estimate_duration_from_bytes, infer_audio_metadata, preprocess_audio_features
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.realtime_tuning import analyze_audio_frame
from backend.main import app
from fastapi.testclient import TestClient


def _sine_pcm_bytes(frequency: float, sample_rate: int = 16000, seconds: float = 0.25, amplitude: float = 0.35) -> bytes:
    total = int(sample_rate * seconds)
    samples = []
    for index in range(total):
        value = amplitude * math.sin(2 * math.pi * frequency * index / sample_rate)
        samples.append(struct.pack("<h", int(value * 32767)))
    return b"".join(samples)


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


def test_preprocess_audio_features_supports_named_multitrack_input():
    sample_rate = 16000
    vocal = [0.2 * math.sin(2 * math.pi * 440 * index / sample_rate) for index in range(1600)]
    accompaniment = [0.05 * math.sin(2 * math.pi * 220 * index / sample_rate) for index in range(800)]

    result = preprocess_audio_features(
        {"sample_rate": sample_rate, "vocal": vocal, "accompaniment": {"samples": accompaniment, "sample_rate": 8000}},
        sample_rate=sample_rate,
    )

    assert result["sample_rate"] == sample_rate
    assert result["track_count"] == 2
    assert len(result["samples"]) >= len(vocal)
    assert result["features"]["rms"] > 0
    assert {track["name"] for track in result["tracks"]} == {"vocal", "accompaniment"}


def test_detect_pitch_sequence_accepts_multitrack_payload():
    sample_rate = 16000
    vocal = [0.35 * math.sin(2 * math.pi * 440 * index / sample_rate) for index in range(3200)]
    backing = [0.08 * math.sin(2 * math.pi * 330 * index / sample_rate) for index in range(3200)]

    result = detect_pitch_sequence(
        "multitrack",
        sample_rate=sample_rate,
        audio_bytes={"tracks": [{"name": "vocal", "samples": vocal}, {"name": "backing", "samples": backing}]},
    )

    assert result
    assert any(point["voiced"] for point in result)
    assert any(point["frequency"] > 0 for point in result)


def test_pitch_detect_api_accepts_single_file_upload():
    client = TestClient(app)
    response = client.post(
        "/api/v1/pitch/detect",
        files={"file": ("vocal.raw", _sine_pcm_bytes(440.0), "application/octet-stream")},
        data={"sample_rate": "16000", "frame_ms": "20", "hop_ms": "10", "algorithm": "yin"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["track_count"] == 1
    assert data["sample_rate"] == 16000
    assert data["algorithm"] == "yin"
    assert data["pitch_sequence"]


def test_pitch_detect_multitrack_api_accepts_multiple_files():
    files = [
        ("files", ("vocal.raw", _sine_pcm_bytes(440.0), "application/octet-stream")),
        ("files", ("backing.raw", _sine_pcm_bytes(330.0, amplitude=0.08), "application/octet-stream")),
    ]
    client = TestClient(app)
    response = client.post(
        "/api/v1/pitch/detect-multitrack",
        files=files,
        data={"sample_rate": "16000", "frame_ms": "20", "hop_ms": "10", "algorithm": "yin"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["track_count"] == 2
    assert {track["name"] for track in data["tracks"]} == {"vocal.raw", "backing.raw"}
    assert data["pitch_sequence"]
    assert any(point["frequency"] > 0 for point in data["pitch_sequence"])


def test_realtime_tuning_uses_reference_frequency_when_provided():
    result = analyze_audio_frame(b"\x00" * 320, sample_rate=16000, reference_frequency=445.0)
    assert result["frequency"] == 445.0
    assert result["note"] == "A4"
    assert result["cents_offset"] == 0.0
