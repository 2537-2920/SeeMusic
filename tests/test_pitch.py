import builtins
from contextlib import contextmanager
import importlib
import io
import math
import struct
import sys
import wave

import pytest
from sqlalchemy.exc import OperationalError

import backend.api.api_routes as api_routes_module
import backend.core.pitch.audio_utils as audio_utils
from backend.services import analysis_service
from backend.core.pitch.audio_utils import AudioDecodeError, audio_bytes_to_samples, estimate_duration_from_bytes, infer_audio_metadata, preprocess_audio_features
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


def _sine_wav_bytes(frequency: float, sample_rate: int = 16000, seconds: float = 0.25, amplitude: float = 0.35) -> bytes:
    pcm = _sine_pcm_bytes(frequency, sample_rate=sample_rate, seconds=seconds, amplitude=amplitude)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


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


def test_audio_bytes_to_samples_decodes_wav_upload():
    samples, sample_rate = audio_bytes_to_samples(_sine_wav_bytes(440.0), file_name="vocal.wav")

    assert sample_rate == 16000
    assert samples
    assert max(abs(sample) for sample in samples) > 0.1


@pytest.mark.parametrize("file_name", ["demo.ogg", "demo.mp3", "demo.m4a"])
def test_audio_bytes_to_samples_uses_compressed_decoder(monkeypatch: pytest.MonkeyPatch, file_name: str):
    def fake_decode_with_librosa(audio_bytes: bytes, incoming_name: str | None, sample_rate: int):
        assert audio_bytes == b"compressed-audio"
        assert incoming_name == file_name
        assert sample_rate == 16000
        return [0.1, -0.1, 0.2], 22050

    monkeypatch.setattr(audio_utils, "_decode_with_librosa", fake_decode_with_librosa)

    samples, sample_rate = audio_bytes_to_samples(b"compressed-audio", sample_rate=16000, file_name=file_name)

    assert sample_rate == 22050
    assert samples == [0.1, -0.1, 0.2]


def test_audio_bytes_to_samples_rejects_invalid_compressed_upload(monkeypatch: pytest.MonkeyPatch):
    def raise_decode_error(_: bytes, __: str | None, ___: int):
        raise AudioDecodeError("无法解码该音频格式。")

    monkeypatch.setattr(audio_utils, "_decode_with_librosa", raise_decode_error)

    with pytest.raises(AudioDecodeError, match="无法解码"):
        audio_bytes_to_samples(b"broken", sample_rate=16000, file_name="broken.mp3")


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
    assert data["detected_key_signature"]
    assert data["key_detection"]["key_signature"] == data["detected_key_signature"]
    assert data["pitch_sequence"]


def test_pitch_detect_api_accepts_wav_upload():
    client = TestClient(app)
    response = client.post(
        "/api/v1/pitch/detect",
        files={"file": ("vocal.wav", _sine_wav_bytes(440.0), "audio/wav")},
        data={"frame_ms": "20", "hop_ms": "10", "algorithm": "yin"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pitch_sequence"]
    assert any(point["frequency"] > 0 for point in data["pitch_sequence"])


def test_pitch_detect_api_returns_result_when_db_persistence_times_out(monkeypatch: pytest.MonkeyPatch):
    @contextmanager
    def failing_session_scope():
        raise OperationalError(
            "DELETE FROM pitch_sequence WHERE analysis_id = %(analysis_id_1)s",
            {"analysis_id_1": "an_test"},
            Exception("Lock wait timeout exceeded; try restarting transaction"),
        )
        yield

    monkeypatch.setattr(analysis_service, "_session_scope", failing_session_scope)
    monkeypatch.setattr(analysis_service, "USE_DB", True)

    client = TestClient(app)
    response = client.post(
        "/api/v1/pitch/detect",
        files={"file": ("vocal.wav", _sine_wav_bytes(440.0), "audio/wav")},
        data={"frame_ms": "20", "hop_ms": "10", "algorithm": "yin"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pitch_sequence"]
    assert analysis_service.get_saved_pitch_sequence(data["analysis_id"]) == data["pitch_sequence"]


def test_pitch_detect_api_rejects_invalid_compressed_upload(monkeypatch: pytest.MonkeyPatch):
    def raise_decode_error(_: bytes, __: str | None, ___: int):
        raise AudioDecodeError("无法解码该音频格式。")

    monkeypatch.setattr(audio_utils, "_decode_with_librosa", raise_decode_error)
    client = TestClient(app)
    response = client.post(
        "/api/v1/pitch/detect",
        files={"file": ("broken.mp3", b"broken", "audio/mpeg")},
        data={"frame_ms": "20", "hop_ms": "10", "algorithm": "yin"},
    )

    assert response.status_code == 400
    assert "无法解码" in response.json()["detail"]


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


def test_guitar_audio_pipeline_api_accepts_audio_upload(monkeypatch: pytest.MonkeyPatch):
    def fake_guitar_pipeline(**kwargs):
        assert kwargs["analysis_id"].startswith("an_")
        assert kwargs["tempo"] == 92
        assert kwargs["time_signature"] == "4/4"
        return {
            "analysis_id": kwargs["analysis_id"],
            "lead_sheet_type": "guitar_chord_chart",
            "title": "童年",
            "key": "G",
            "tempo": kwargs["tempo"],
            "time_signature": kwargs["time_signature"],
            "style": kwargs["style"],
            "melody_size": 4,
            "pitch_sequence": [{"time": 0.0, "frequency": 392.0, "duration": 0.5, "confidence": 0.92}],
            "detected_key_signature": "G",
            "key_detection": {"key_signature": "G", "confidence": 0.88},
            "melody_track": {"name": "vocal", "source": "separated_track", "average_confidence": 0.92, "voiced_ratio": 0.9},
            "melody_track_candidates": [],
            "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
            "warnings": [],
            "pipeline": {"separation_enabled": True},
            "chords": [{"measure_no": 1, "beat_in_measure": 1.0, "symbol": "G", "source": "diatonic"}],
            "measures": [{"measure_no": 1, "chords": [{"symbol": "G"}]}],
            "guitar_shapes": {"G": {"symbol": "G", "fingering": "320003"}},
            "capo_suggestion": {"capo": 0, "transposed_key": "G"},
            "strumming_pattern": {"pattern": "D DU UDU", "description": "demo"},
        }

    monkeypatch.setattr(api_routes_module, "generate_guitar_lead_sheet_from_audio", fake_guitar_pipeline)

    client = TestClient(app)
    response = client.post(
        "/api/v1/generation/guitar-lead-sheet-from-audio",
        files={"file": ("tongnian.wav", _sine_wav_bytes(392.0), "audio/wav")},
        data={
            "tempo": "92",
            "time_signature": "4/4",
            "style": "folk",
            "title": "童年",
            "frame_ms": "20",
            "hop_ms": "10",
            "algorithm": "yin",
            "separation_model": "demucs",
            "separation_stems": "2",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lead_sheet_type"] == "guitar_chord_chart"
    assert data["melody_track"]["name"] == "vocal"
    assert data["detected_key_signature"] == "G"
    assert data["audio_log"]["log_id"].startswith("log_")


def test_guzheng_audio_pipeline_api_accepts_audio_upload(monkeypatch: pytest.MonkeyPatch):
    def fake_guzheng_pipeline(**kwargs):
        assert kwargs["analysis_id"].startswith("an_")
        assert kwargs["tempo"] == 96
        assert kwargs["time_signature"] == "4/4"
        return {
            "analysis_id": kwargs["analysis_id"],
            "lead_sheet_type": "guzheng_jianpu_chart",
            "title": "渔舟唱晚",
            "key": "G",
            "tempo": 88,
            "time_signature": kwargs["time_signature"],
            "style": kwargs["style"],
            "melody_size": 4,
            "pitch_sequence": [{"time": 0.0, "frequency": 392.0, "duration": 0.5, "confidence": 0.92}],
            "detected_key_signature": "G",
            "key_detection": {"key_signature": "G", "confidence": 0.88, "mode": "major", "fifths": 1},
            "beat_result": {"bpm": 88.0, "beat_times": [0.0, 0.68, 1.36], "beat_quality": {"confidence": 0.6}, "num_beats": 3},
            "tempo_detection": {"detected_tempo": 88, "resolved_tempo": 88, "used_detected_tempo": True, "confidence": 0.6, "beat_count": 3, "fallback_reason": None},
            "melody_track": {"name": "vocal", "source": "separated_track", "average_confidence": 0.92, "voiced_ratio": 0.9},
            "melody_track_candidates": [],
            "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
            "warnings": [],
            "pipeline": {"separation_enabled": True, "beat_detection_enabled": True},
            "instrument_profile": {"tuning": "21弦 D调定弦", "range": "D2-D6", "family": "plucked"},
            "measures": [{"measure_no": 1, "notes": [{"degree_display": "1", "string_label": "11弦"}]}],
            "phrase_lines": [{"phrase_no": 1, "measure_start": 1, "measure_end": 1, "measures": [{"measure_no": 1, "notes": []}], "string_positions": []}],
            "sections": [{"section_no": 1, "measure_start": 1, "measure_end": 1, "phrase_lines": []}],
            "string_positions": [{"measure_no": 1, "string_label": "11弦"}],
            "technique_summary": {"counts": {"摇指候选": 1}, "total_tagged_notes": 1, "phrase_suggestions": []},
            "pentatonic_summary": {"direct_open_notes": 3, "press_note_candidates": 1, "direct_ratio": 0.75},
            "pitch_range": {"lowest": "G4", "highest": "D5"},
        }

    monkeypatch.setattr(api_routes_module, "generate_guzheng_score_from_audio", fake_guzheng_pipeline)

    client = TestClient(app)
    response = client.post(
        "/api/v1/generation/guzheng-score-from-audio",
        files={"file": ("guzheng.wav", _sine_wav_bytes(392.0), "audio/wav")},
        data={
            "tempo": "96",
            "time_signature": "4/4",
            "style": "traditional",
            "title": "渔舟唱晚",
            "frame_ms": "20",
            "hop_ms": "10",
            "algorithm": "yin",
            "separation_model": "demucs",
            "separation_stems": "2",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lead_sheet_type"] == "guzheng_jianpu_chart"
    assert data["melody_track"]["name"] == "vocal"
    assert data["tempo_detection"]["resolved_tempo"] == 88
    assert data["instrument_profile"]["tuning"] == "21弦 D调定弦"
    assert data["audio_log"]["log_id"].startswith("log_")


def test_dizi_audio_pipeline_api_accepts_audio_upload(monkeypatch: pytest.MonkeyPatch):
    def fake_dizi_pipeline(**kwargs):
        assert kwargs["analysis_id"].startswith("an_")
        assert kwargs["tempo"] == 96
        assert kwargs["time_signature"] == "4/4"
        assert kwargs["flute_type"] == "G"
        return {
            "analysis_id": kwargs["analysis_id"],
            "lead_sheet_type": "dizi_jianpu_chart",
            "title": "笛子测试",
            "key": "G",
            "tempo": 88,
            "time_signature": kwargs["time_signature"],
            "style": kwargs["style"],
            "flute_type": kwargs["flute_type"],
            "melody_size": 4,
            "pitch_sequence": [{"time": 0.0, "frequency": 392.0, "duration": 0.5, "confidence": 0.92}],
            "detected_key_signature": "G",
            "key_detection": {"key_signature": "G", "confidence": 0.88, "mode": "major", "fifths": 1},
            "beat_result": {"bpm": 88.0, "beat_times": [0.0, 0.68, 1.36], "beat_quality": {"confidence": 0.6}, "num_beats": 3},
            "tempo_detection": {"detected_tempo": 88, "resolved_tempo": 88, "used_detected_tempo": True, "confidence": 0.6, "beat_count": 3, "fallback_reason": None},
            "melody_track": {"name": "vocal", "source": "separated_track", "average_confidence": 0.92, "voiced_ratio": 0.9},
            "melody_track_candidates": [],
            "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
            "warnings": [],
            "pipeline": {"separation_enabled": True, "beat_detection_enabled": True},
            "instrument_profile": {"flute_type": "G", "range": "F4-A6", "family": "wind"},
            "measures": [{"measure_no": 1, "notes": [{"degree_display": "1", "hole_pattern": "●●● ●●●"}]}],
            "phrase_lines": [{"phrase_no": 1, "measure_start": 1, "measure_end": 1, "measures": [{"measure_no": 1, "notes": []}], "fingerings": []}],
            "sections": [{"section_no": 1, "measure_start": 1, "measure_end": 1, "phrase_lines": []}],
            "fingerings": [{"measure_no": 1, "hole_pattern": "●●● ●●●"}],
            "technique_summary": {"counts": {"换气点": 1}, "total_tagged_notes": 1, "phrase_suggestions": []},
            "playability_summary": {"playable_notes": 4, "out_of_range_notes": 0, "half_hole_candidates": 1, "special_fingering_candidates": 0, "playable_ratio": 1.0},
            "pitch_range": {"lowest": "G4", "highest": "D5"},
        }

    monkeypatch.setattr(api_routes_module, "generate_dizi_score_from_audio", fake_dizi_pipeline)

    client = TestClient(app)
    response = client.post(
        "/api/v1/generation/dizi-score-from-audio",
        files={"file": ("dizi.wav", _sine_wav_bytes(392.0), "audio/wav")},
        data={
            "tempo": "96",
            "time_signature": "4/4",
            "style": "traditional",
            "flute_type": "G",
            "title": "笛子测试",
            "frame_ms": "20",
            "hop_ms": "10",
            "algorithm": "yin",
            "separation_model": "demucs",
            "separation_stems": "2",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lead_sheet_type"] == "dizi_jianpu_chart"
    assert data["melody_track"]["name"] == "vocal"
    assert data["tempo_detection"]["resolved_tempo"] == 88
    assert data["flute_type"] == "G"
    assert data["audio_log"]["log_id"].startswith("log_")


def test_realtime_tuning_uses_reference_frequency_when_provided():
    result = analyze_audio_frame(b"\x00" * 320, sample_rate=16000, reference_frequency=445.0)
    assert result["frequency"] == 445.0
    assert result["note"] == "A4"
    assert result["cents_offset"] == 0.0


def test_backend_main_import_does_not_require_soundfile(monkeypatch: pytest.MonkeyPatch):
    import backend.api.api_routes as api_routes_module
    import backend.main as main_module
    import backend.services.analysis_service as analysis_service_module
    import backend.utils.audio_logger as audio_logger_module

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "soundfile":
            raise ModuleNotFoundError("No module named 'soundfile'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "soundfile", raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    importlib.reload(audio_logger_module)
    importlib.reload(analysis_service_module)
    importlib.reload(api_routes_module)
    reloaded_main = importlib.reload(main_module)

    with TestClient(reloaded_main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
