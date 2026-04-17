import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from backend.db.models import AudioAnalysis, PitchSequence, Report
from backend.db.session import session_scope
from backend.services import analysis_service
from backend.services.analysis_service import analyze_audio, evaluate_singing
from backend.services.report_service import export_report
from backend.services.score_service import (
    ExportRecordNotFoundError,
    ScoreNotFoundError,
    ScoreOperationError,
    _resolve_export_path,
    create_score_from_pitch_sequence,
    delete_score_export,
    edit_score,
    export_score,
    get_score_export_file,
    get_score_export_record,
    list_score_exports,
    regenerate_score_export,
)
from backend.config.settings import settings


@pytest.fixture
def temp_audio_bytes():
    """Generate temporary audio bytes for testing."""
    sr = 16000
    duration = 2  # 2 seconds
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


def test_analysis_service_returns_end_to_end_payload(temp_audio_bytes):
    result = analyze_audio("demo.wav", temp_audio_bytes, sample_rate=16000)
    assert result["analysis_id"].startswith("an_")
    assert result["pitch_sequence"]
    assert result["beat_result"]["beat_times"]
    assert result["score"]["score_id"].startswith("score_")
    assert result["log"]["log_id"].startswith("log_")
    assert result["log"]["sample_rate"] == 16000
    assert result["log"]["duration"] == 2.0  # 2 seconds as defined in fixture
    assert result["log"]["stage"] == "analyze_audio"


def test_evaluate_singing_separates_reference_only_for_a_cappella_user(temp_audio_bytes, tmp_path, monkeypatch):
    calls = []

    def fake_separate_tracks(file_name, model="demucs", stems=2, audio_bytes=None, sample_rate=44100):
        calls.append(file_name)
        vocal_path = tmp_path / f"{Path(file_name).stem}_vocal.wav"
        vocal_path.write_bytes(temp_audio_bytes)
        return {
            "task_id": f"sep_{Path(file_name).stem}",
            "status": "completed",
            "model": model,
            "backend_used": "fake",
            "fallback_used": False,
            "warnings": [],
            "tracks": [
                {
                    "name": "vocal",
                    "file_name": vocal_path.name,
                    "download_url": f"/api/v1/audio/download/{vocal_path.name}",
                    "file_path": str(vocal_path),
                    "duration": 2.0,
                }
            ],
        }

    monkeypatch.setattr("backend.core.separation.multi_track_separation.separate_tracks", fake_separate_tracks)
    monkeypatch.setattr(
        analysis_service,
        "process_rhythm_scoring_sync",
        lambda *args, **kwargs: {
            "score": 80,
            "timing_accuracy": 0.8,
            "coverage_ratio": 0.9,
            "consistency_ratio": 0.85,
            "mean_deviation_ms": 12,
            "missing_beats": 0,
            "extra_beats": 0,
            "error_classification": {},
            "reference_duration": 2.0,
            "user_duration": 2.0,
            "reference_bpm": 120,
            "user_bpm": 118,
        },
    )
    monkeypatch.setattr(
        analysis_service,
        "detect_pitch_sequence",
        lambda **kwargs: [
            {"time": 0.0, "frequency": 440.0, "confidence": 0.9},
            {"time": 0.1, "frequency": 441.0, "confidence": 0.9},
        ],
    )

    result = evaluate_singing(
        reference_file_name="standard.wav",
        reference_audio_bytes=temp_audio_bytes,
        user_file_name="user.wav",
        user_audio_bytes=temp_audio_bytes,
        user_audio_mode="a_cappella",
    )

    assert calls == ["standard.wav"]
    assert result["analysis_id"].startswith("an_")
    assert result["user_audio_mode"] == "a_cappella"
    assert result["reference_separation"]["vocal_track"]["name"] == "vocal"
    assert result["user_separation"] is None
    assert result["rhythm"]["score"] == 80
    assert result["pitch_comparison"]["summary"]["matched_points"] > 0
    assert result["overall_score"] >= 80


def test_evaluate_singing_separates_user_when_accompanied(temp_audio_bytes, tmp_path, monkeypatch):
    calls = []

    def fake_separate_tracks(file_name, model="demucs", stems=2, audio_bytes=None, sample_rate=44100):
        calls.append(file_name)
        vocal_path = tmp_path / f"{len(calls)}_{Path(file_name).stem}_vocal.wav"
        vocal_path.write_bytes(temp_audio_bytes)
        return {
            "task_id": f"sep_{len(calls)}",
            "status": "completed",
            "model": model,
            "tracks": [
                {
                    "name": "vocal",
                    "file_name": vocal_path.name,
                    "download_url": f"/api/v1/audio/download/{vocal_path.name}",
                    "file_path": str(vocal_path),
                    "duration": 2.0,
                }
            ],
        }

    monkeypatch.setattr("backend.core.separation.multi_track_separation.separate_tracks", fake_separate_tracks)
    monkeypatch.setattr(
        analysis_service,
        "process_rhythm_scoring_sync",
        lambda *args, **kwargs: {
            "score": 90,
            "timing_accuracy": 0.9,
            "coverage_ratio": 1.0,
            "consistency_ratio": 0.95,
            "mean_deviation_ms": 8,
            "missing_beats": 0,
            "extra_beats": 0,
            "error_classification": {},
            "reference_duration": 2.0,
            "user_duration": 2.0,
            "reference_bpm": 120,
            "user_bpm": 120,
        },
    )
    monkeypatch.setattr(
        analysis_service,
        "detect_pitch_sequence",
        lambda **kwargs: [{"time": 0.0, "frequency": 440.0, "confidence": 0.9}],
    )

    different_user_audio = temp_audio_bytes + b"\x00"

    result = evaluate_singing(
        reference_file_name="standard.wav",
        reference_audio_bytes=temp_audio_bytes,
        user_file_name="user.wav",
        user_audio_bytes=different_user_audio,
        user_audio_mode="with_accompaniment",
    )

    assert calls == ["standard.wav", "user.wav"]
    assert result["user_audio_mode"] == "with_accompaniment"
    assert result["user_separation"]["vocal_track"]["name"] == "vocal"


def test_evaluate_singing_reuses_reference_vocal_when_same_audio(temp_audio_bytes, tmp_path, monkeypatch):
    calls = []

    def fake_separate_tracks(file_name, model="demucs", stems=2, audio_bytes=None, sample_rate=44100):
        calls.append(file_name)
        vocal_path = tmp_path / f"{Path(file_name).stem}_vocal.wav"
        vocal_path.write_bytes(temp_audio_bytes)
        return {
            "task_id": f"sep_{Path(file_name).stem}",
            "status": "completed",
            "model": model,
            "tracks": [
                {
                    "name": "vocal",
                    "file_name": vocal_path.name,
                    "download_url": f"/api/v1/audio/download/{vocal_path.name}",
                    "file_path": str(vocal_path),
                    "duration": 2.0,
                }
            ],
        }

    monkeypatch.setattr("backend.core.separation.multi_track_separation.separate_tracks", fake_separate_tracks)
    monkeypatch.setattr(
        analysis_service,
        "process_rhythm_scoring_sync",
        lambda *args, **kwargs: {
            "score": 88,
            "timing_accuracy": 0.88,
            "coverage_ratio": 1.0,
            "consistency_ratio": 0.92,
            "mean_deviation_ms": 9,
            "missing_beats": 0,
            "extra_beats": 0,
            "error_classification": {},
            "reference_duration": 2.0,
            "user_duration": 2.0,
            "reference_bpm": 120,
            "user_bpm": 120,
        },
    )
    monkeypatch.setattr(
        analysis_service,
        "detect_pitch_sequence",
        lambda **kwargs: [{"time": 0.0, "frequency": 440.0, "confidence": 0.9}],
    )

    result = evaluate_singing(
        reference_file_name="standard.wav",
        reference_audio_bytes=temp_audio_bytes,
        user_file_name="user.wav",
        user_audio_bytes=temp_audio_bytes,
        user_audio_mode="with_accompaniment",
    )

    assert calls == ["standard.wav"]
    assert result["user_audio_mode"] == "with_accompaniment"
    assert result["user_separation"]["reused_from_reference"] is True


def test_evaluate_singing_rejects_non_wav_upload(temp_audio_bytes):
    with pytest.raises(ValueError, match="WAV"):
        evaluate_singing(
            reference_file_name="standard.mp3",
            reference_audio_bytes=temp_audio_bytes,
            user_file_name="user.wav",
            user_audio_bytes=temp_audio_bytes,
        )



def test_report_service_returns_requested_files():
    result = export_report({"analysis_id": "an_001", "formats": ["pdf", "png"], "include_charts": False})
    assert result["analysis_id"] == "an_001"
    assert len(result["files"]) == 2
    assert result["include_charts"] is False


def test_analysis_service_persists_audio_analysis_when_db_enabled(user_database, temp_audio_bytes):
    result = analyze_audio("demo.wav", temp_audio_bytes, sample_rate=16000)

    with session_scope() as session:
        analysis = session.query(AudioAnalysis).filter_by(analysis_id=result["analysis_id"]).one()
        points = session.query(PitchSequence).filter_by(analysis_id=result["analysis_id"]).all()

    assert analysis.file_name == "demo.wav"
    assert analysis.sample_rate == 16000
    assert analysis.status == 1
    assert analysis.result_data["score_id"] == result["score"]["score_id"]
    assert len(points) == len(result["pitch_sequence"])


def test_report_service_persists_report_when_db_enabled(user_database):
    result = export_report({"analysis_id": "an_001", "formats": ["pdf", "png"], "include_charts": False})

    with session_scope() as session:
        report = session.query(Report).filter_by(report_id=result["report_id"]).one()

    assert report.analysis_id == "an_001"
    assert report.project_id is None
    assert report.metadata_["formats"] == ["pdf", "png"]
    assert report.metadata_["include_charts"] is False



def test_score_service_create_export_regenerate_and_delete_flow(score_database: dict[str, int | str]):
    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "title": "Service Export Score",
            "tempo": 90,
            "time_signature": "4/4",
            "key_signature": "G",
            "pitch_sequence": [
                {"time": 0.0, "frequency": 440.0, "duration": 0.25},
                {"time": 0.25, "frequency": 493.88, "duration": 0.25},
                {"time": 0.5, "frequency": 523.25, "duration": 0.25},
                {"time": 0.75, "frequency": 587.33, "duration": 0.25},
            ],
        }
    )
    exported = export_score(score["score_id"], {"format": "png"})
    listing = list_score_exports(score["score_id"])
    detail = get_score_export_record(score["score_id"], exported["export_record_id"])
    file_payload = get_score_export_file(score["score_id"], exported["export_record_id"])
    regenerated = regenerate_score_export(
        score["score_id"],
        exported["export_record_id"],
        {"page_size": "LETTER", "with_annotations": False},
    )
    deleted = delete_score_export(score["score_id"], exported["export_record_id"])

    assert score["key_signature"] == "G"
    assert score["title"] == "Service Export Score"
    assert exported["manifest"]["kind"] == "png"
    assert f"export_{exported['export_record_id']}" in exported["file_name"]
    assert exported["preview_url"].endswith("/preview")
    assert exported["download_api_url"].endswith("/download")
    assert listing["count"] == 1
    assert listing["items"][0]["export_record_id"] == exported["export_record_id"]
    assert detail["download_url"] == exported["download_url"]
    assert detail["regenerate_url"].endswith("/regenerate")
    assert file_payload["exists"] is True
    assert file_payload["content_type"] == "image/png"
    assert regenerated["regenerated"] is True
    assert regenerated["manifest"]["page_size"] == "LETTER"
    assert regenerated["manifest"]["with_annotations"] is False
    assert deleted["deleted"] is True
    assert deleted["file_deleted"] is True

    with pytest.raises(ExportRecordNotFoundError):
        get_score_export_record(score["score_id"], exported["export_record_id"])



def test_score_service_raises_explicit_errors(score_database: dict[str, int | str]):
    with pytest.raises(ScoreNotFoundError):
        export_score("score_missing", {"format": "pdf"})

    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    with pytest.raises(ScoreOperationError):
        edit_score(score["score_id"], [{"type": "unsupported"}])
