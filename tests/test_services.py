import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from backend.services.analysis_service import analyze_audio
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



def test_report_service_returns_requested_files():
    result = export_report({"analysis_id": "an_001", "formats": ["pdf", "png"], "include_charts": False})
    assert result["analysis_id"] == "an_001"
    assert len(result["files"]) == 2
    assert result["include_charts"] is False


def test_score_service_resolves_storage_urls_inside_configured_storage():
    resolved = _resolve_export_path("/storage/exports/example.pdf")

    assert resolved == (settings.storage_dir / "exports" / "example.pdf").resolve()



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
