import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import soundfile as sf
from sqlalchemy.exc import SQLAlchemyError

import backend.services.score_service as score_service
from backend.db.models import AudioAnalysis, PitchSequence, Report
from backend.db.session import session_scope
from backend.services.analysis_service import analyze_audio, get_saved_pitch_sequence
from backend.services.report_service import export_report
from backend.services.score_service import (
    ExportRecordNotFoundError,
    ScoreNotFoundError,
    ScoreOperationError,
    create_score_from_pitch_sequence,
    delete_score_export,
    edit_score,
    export_score,
    get_score_export_file,
    get_score_export_record,
    list_score_exports,
    regenerate_score_export,
)


def _replace_tempo(musicxml: str, tempo: int) -> str:
    root = ET.fromstring(musicxml.encode("utf-8"))
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "per-minute":
            element.text = str(tempo)
        if tag == "sound" and "tempo" in element.attrib:
            element.set("tempo", str(tempo))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


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
    assert analysis.result_data["pitch_sequence_format"] == "note_events"
    assert analysis.result_data["pitch_sequence"]
    assert analysis.result_data["pitch_meta"]["original_point_count"] == len(result["pitch_sequence"])
    assert points == []
    rebuilt = get_saved_pitch_sequence(result["analysis_id"], populate_cache=False)
    assert rebuilt
    assert rebuilt[0]["note"] == result["pitch_sequence"][0]["note"]


def test_analysis_service_populates_pitch_sequence_cache_on_demand(user_database, temp_audio_bytes):
    result = analyze_audio("demo.wav", temp_audio_bytes, sample_rate=16000)

    first = get_saved_pitch_sequence(result["analysis_id"], populate_cache=True)
    second = get_saved_pitch_sequence(result["analysis_id"], populate_cache=False)

    with session_scope() as session:
        points = session.query(PitchSequence).filter_by(analysis_id=result["analysis_id"]).all()

    assert first
    assert second
    assert len(points) == len(first)


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


def test_score_service_uses_in_memory_export_cache_when_db_reads_fail(
    score_database: dict[str, int | str],
    monkeypatch: pytest.MonkeyPatch,
):
    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "title": "Cached Export Score",
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    exported = export_score(score["score_id"], {"format": "png"})

    def raise_db_timeout(*args, **kwargs):
        raise SQLAlchemyError("db read timeout")

    monkeypatch.setattr(score_service, "get_sheet_by_score_id", raise_db_timeout)
    monkeypatch.setattr(score_service, "list_export_records_by_project", raise_db_timeout)
    monkeypatch.setattr(score_service, "get_export_record_by_id", raise_db_timeout)

    listing = list_score_exports(score["score_id"])
    detail = get_score_export_record(score["score_id"], exported["export_record_id"])

    assert listing["count"] == 1
    assert listing["items"][0]["export_record_id"] == exported["export_record_id"]
    assert detail["download_url"] == exported["download_url"]
    assert detail["content_type"] == "image/png"


def test_score_service_exports_with_in_memory_fallback_when_db_write_fails(
    score_database: dict[str, int | str],
    monkeypatch: pytest.MonkeyPatch,
):
    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "title": "Fallback Export Score",
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )

    def raise_db_timeout(*args, **kwargs):
        raise SQLAlchemyError("db write timeout")

    monkeypatch.setattr(score_service, "create_export_record", raise_db_timeout)

    exported = export_score(score["score_id"], {"format": "pdf"})

    monkeypatch.setattr(score_service, "list_export_records_by_project", raise_db_timeout)
    monkeypatch.setattr(score_service, "get_export_record_by_id", raise_db_timeout)

    listing = list_score_exports(score["score_id"])
    detail = get_score_export_record(score["score_id"], exported["export_record_id"])

    assert exported["export_record_id"] >= score_service.IN_MEMORY_EXPORT_RECORD_ID_BASE
    assert exported["download_api_url"].endswith("/download")
    assert exported["content_type"] == "application/pdf"
    assert listing["count"] == 1
    assert listing["items"][0]["export_record_id"] == exported["export_record_id"]
    assert detail["file_name"] == exported["file_name"]
    assert detail["download_api_url"].endswith("/download")


def test_score_service_creates_score_in_memory_when_db_is_unavailable(
    score_database: dict[str, int | str],
    monkeypatch: pytest.MonkeyPatch,
):
    def raise_db_timeout(*args, **kwargs):
        raise SQLAlchemyError("db create timeout")

    monkeypatch.setattr(score_service, "get_user_by_id", raise_db_timeout)
    monkeypatch.setattr(score_service, "get_sheet_by_score_id", lambda *args, **kwargs: None)

    score = create_score_from_pitch_sequence(
        {
            "user_id": score_database["user_id"],
            "title": "In-Memory Score",
            "tempo": 84,
            "time_signature": "4/4",
            "key_signature": "F",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    listing = list_score_exports(score["score_id"])
    updated = edit_score(score["score_id"], _replace_tempo(score["musicxml"], 72))

    assert score["project_id"] >= score_service.IN_MEMORY_PROJECT_ID_BASE
    assert score["title"] == "In-Memory Score"
    assert listing["count"] == 0
    assert listing["project_id"] == score["project_id"]
    assert updated["tempo"] == 72
    assert updated["project_id"] == score["project_id"]


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
        edit_score(score["score_id"], "<score-partwise>")
