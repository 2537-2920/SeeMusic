from pathlib import Path

from backend.config.settings import settings
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.export.export_utils import build_export_files, build_score_export_payload, write_score_export
from backend.utils.audio_logger import AUDIO_LOGS, record_audio_log
from backend.utils.data_visualizer import build_pitch_curve


def test_audio_logger_records_entries_in_memory():
    entry = record_audio_log({"file_name": "demo.wav", "sample_rate": 16000, "duration": 1.0})
    assert entry["log_id"].startswith("log_")
    assert len(AUDIO_LOGS) == 1


def test_build_pitch_curve_computes_deviation_values():
    chart = build_pitch_curve(
        [{"time": 0.0, "frequency": 440.0}, {"time": 0.5, "frequency": 442.0}],
        [{"time": 0.0, "frequency": 438.0}, {"time": 0.5, "frequency": 444.0}],
    )
    assert chart["x_axis"] == [0.0, 0.5]
    assert chart["deviation_curve"] == [-2.0, 2.0]


def test_build_export_files_returns_downloadable_entries():
    files = build_export_files("resource_001", ["pdf", "png"])
    assert len(files) == 2
    assert files[0]["download_url"].endswith(".pdf")


def test_build_score_export_payload_supports_visual_and_midi_formats():
    score = build_score_from_pitch_sequence([{"time": 0.0, "frequency": 440.0, "duration": 0.5}])
    midi_payload = build_score_export_payload(score, "midi")
    pdf_payload = build_score_export_payload(score, "pdf", page_size="A4", with_annotations=True)
    assert midi_payload["manifest"]["kind"] == "midi"
    assert pdf_payload["manifest"]["kind"] == "pdf"
    assert pdf_payload["manifest"]["pages"]


def test_write_score_export_persists_real_files():
    score = build_score_from_pitch_sequence([{"time": 0.0, "frequency": 440.0, "duration": 0.5}])

    midi_payload = write_score_export(score, "midi", settings.storage_dir)
    png_payload = write_score_export(score, "png", settings.storage_dir)
    pdf_payload = write_score_export(score, "pdf", settings.storage_dir)

    for payload in (midi_payload, png_payload, pdf_payload):
        file_path = Path(payload["file_path"])
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        assert payload["download_url"].startswith("/storage/exports/")

