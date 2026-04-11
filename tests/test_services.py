import pytest

from backend.services.analysis_service import analyze_audio
from backend.services.report_service import export_report
from backend.services.score_service import (
    ScoreNotFoundError,
    ScoreOperationError,
    create_score_from_pitch_sequence,
    edit_score,
    export_score,
)


def test_analysis_service_returns_end_to_end_payload():
    result = analyze_audio("demo.wav", b"\x00" * 32000, sample_rate=16000)
    assert result["analysis_id"].startswith("an_")
    assert result["pitch_sequence"]
    assert result["beat_result"]["beat_times"]
    assert result["score"]["score_id"].startswith("score_")
    assert result["log"]["log_id"].startswith("log_")


def test_report_service_returns_requested_files():
    result = export_report({"analysis_id": "an_001", "formats": ["pdf", "png"], "include_charts": False})
    assert result["analysis_id"] == "an_001"
    assert len(result["files"]) == 2
    assert result["include_charts"] is False


def test_score_service_create_and_export_flow():
    score = create_score_from_pitch_sequence(
        {
            "tempo": 90,
            "time_signature": "4/4",
            "key_signature": "G",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    exported = export_score(score["score_id"], {"format": "midi"})
    assert score["key_signature"] == "G"
    assert exported["manifest"]["kind"] == "midi"


def test_score_service_raises_explicit_errors():
    with pytest.raises(ScoreNotFoundError):
        export_score("score_missing", {"format": "pdf"})

    score = create_score_from_pitch_sequence(
        {
            "tempo": 120,
            "time_signature": "4/4",
            "key_signature": "C",
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
        }
    )
    with pytest.raises(ScoreOperationError):
        edit_score(score["score_id"], [{"type": "unsupported"}])

