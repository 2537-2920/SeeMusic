from __future__ import annotations

import xml.etree.ElementTree as ET

import backend.api.api_routes as api_routes_module
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.core.pitch.audio_utils import AudioDependencyError
from backend.services.analysis_service import save_analysis_result
import backend.services.score_service as score_service
from backend.db.models import Project, Sheet
from backend.db.session import session_scope
from backend.main import app


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



def test_score_creation_route_persists_project_and_sheet(score_database: dict[str, int | str]) -> None:
    payload = {
        "user_id": score_database["user_id"],
        "title": "API Created Score",
        "analysis_id": "an_demo_001",
        "tempo": 108,
        "time_signature": "3/4",
        "key_signature": "G",
        "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/score/from-pitch-sequence", json=payload)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["project_id"] > 0
    assert body["score_id"]
    assert body["tempo"] == 108
    assert body["title"] == "API Created Score"
    assert body["musicxml"].startswith("<?xml")
    assert body["summary"]["measure_count"] >= 1

    with session_scope() as session:
        project = session.get(Project, body["project_id"])
        sheet = session.query(Sheet).filter_by(score_id=body["score_id"]).one()

        assert project is not None
        assert project.user_id == score_database["user_id"]
        assert project.title == "API Created Score"
        assert project.analysis_id == "an_demo_001"
        assert project.status == 1
        assert sheet.project_id == body["project_id"]
        assert sheet.bpm == 108
        assert sheet.key_sign == "G"
        assert sheet.time_sign == "3/4"
        assert sheet.note_data["score_id"] == body["score_id"]
        assert sheet.note_data["title"] == "API Created Score"
        assert sheet.musicxml == body["musicxml"]


def test_score_creation_route_can_auto_detect_key_signature(score_database: dict[str, int | str]) -> None:
    payload = {
        "user_id": score_database["user_id"],
        "title": "Auto Key Score",
        "tempo": 120,
        "time_signature": "4/4",
        "key_signature": None,
        "auto_detect_key": True,
        "pitch_sequence": [
            {"time": 0.0, "frequency": 392.0, "duration": 0.5},
            {"time": 0.5, "frequency": 440.0, "duration": 0.5},
            {"time": 1.0, "frequency": 493.88, "duration": 0.5},
            {"time": 1.5, "frequency": 523.25, "duration": 0.5},
            {"time": 2.0, "frequency": 587.33, "duration": 0.5},
            {"time": 2.5, "frequency": 659.25, "duration": 0.5},
            {"time": 3.0, "frequency": 739.99, "duration": 0.5},
            {"time": 3.5, "frequency": 783.99, "duration": 1.0},
        ],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/score/from-pitch-sequence", json=payload)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["key_signature"] == "G"


def test_score_creation_from_audio_route_returns_piano_melody_score(
    score_database: dict[str, int | str],
    monkeypatch,
) -> None:
    def fake_piano_pipeline(**kwargs):
        assert kwargs["analysis_id"].startswith("an_")
        assert kwargs["fallback_tempo"] == 120
        return {
            "analysis_id": kwargs["analysis_id"],
            "tempo": 92,
            "time_signature": kwargs["time_signature"],
            "pitch_sequence": [{"time": 0.0, "frequency": 392.0, "duration": 0.5, "note": "G4"}],
            "detected_key_signature": "G",
            "key_detection": {"key_signature": "G", "confidence": 0.88, "mode": "major", "fifths": 1},
            "beat_result": {
                "bpm": 92.0,
                "beat_times": [0.0, 0.652, 1.304],
                "beat_quality": {"confidence": 0.62},
                "num_beats": 3,
            },
            "tempo_detection": {
                "detected_tempo": 92,
                "resolved_tempo": 92,
                "used_detected_tempo": True,
                "confidence": 0.62,
                "beat_count": 3,
                "fallback_reason": None,
            },
            "melody_track": {"name": "vocal", "source": "separated_track", "average_confidence": 0.91, "voiced_ratio": 0.9},
            "melody_track_candidates": [],
            "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
            "warnings": [],
            "pipeline": {"separation_enabled": True, "beat_detection_enabled": True},
        }

    monkeypatch.setattr(api_routes_module, "prepare_piano_score_from_audio", fake_piano_pipeline)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/score/from-audio",
            files={"file": ("tongnian.wav", b"demo-audio", "audio/wav")},
            data={
                "user_id": str(score_database["user_id"]),
                "title": "钢琴主旋律谱",
                "tempo": "120",
                "time_signature": "4/4",
                "frame_ms": "20",
                "hop_ms": "10",
                "algorithm": "yin",
                "separation_model": "demucs",
                "separation_stems": "2",
            },
        )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["score_mode"] == "piano_two_hand_arrangement"
    assert body["tempo"] == 92
    assert body["key_signature"] == "G"
    assert body["melody_track"]["name"] == "vocal"
    assert body["beat_result"]["bpm"] == 92.0
    assert body["arrangement_mode"] == "piano_solo"
    assert body["piano_arrangement"]["arrangement_type"] == "piano_solo"
    assert body["piano_arrangement"]["chords"]
    assert body["score_id"]


def test_score_creation_from_audio_route_can_return_precise_piano_melody_mode(
    score_database: dict[str, int | str],
    monkeypatch,
) -> None:
    def fake_piano_pipeline(**kwargs):
        return {
            "analysis_id": kwargs["analysis_id"],
            "tempo": 84,
            "time_signature": kwargs["time_signature"],
            "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5, "note": "A4"}],
            "detected_key_signature": "D",
            "key_detection": {"key_signature": "D", "confidence": 0.77, "mode": "major", "fifths": 2},
            "beat_result": {
                "bpm": 84.0,
                "beat_times": [0.0, 0.714, 1.428],
                "beat_quality": {"confidence": 0.52},
                "num_beats": 3,
            },
            "tempo_detection": {
                "detected_tempo": 84,
                "resolved_tempo": 84,
                "used_detected_tempo": True,
                "confidence": 0.52,
                "beat_count": 3,
                "fallback_reason": None,
            },
            "melody_track": {"name": "vocal", "source": "separated_track", "average_confidence": 0.88, "voiced_ratio": 0.86},
            "melody_track_candidates": [],
            "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
            "warnings": [],
            "pipeline": {"separation_enabled": True, "beat_detection_enabled": True},
        }

    monkeypatch.setattr(api_routes_module, "prepare_piano_score_from_audio", fake_piano_pipeline)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/score/from-audio",
            files={"file": ("melody.wav", b"demo-audio", "audio/wav")},
            data={
                "user_id": str(score_database["user_id"]),
                "title": "精准钢琴谱",
                "tempo": "120",
                "time_signature": "4/4",
                "frame_ms": "20",
                "hop_ms": "10",
                "algorithm": "yin",
                "separation_model": "demucs",
                "separation_stems": "2",
                "arrangement_mode": "melody",
            },
        )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["score_mode"] == "piano_two_hand_arrangement"
    assert body["arrangement_mode"] == "piano_solo"
    assert body["tempo"] == 84
    assert body["key_signature"] == "D"
    assert body["melody_track"]["name"] == "vocal"
    assert body["beat_result"]["bpm"] == 84.0
    assert body["piano_arrangement"] is not None
    assert body["score_id"]


def test_score_creation_from_audio_route_accepts_mp3_and_optional_lrc(
    score_database: dict[str, int | str],
    monkeypatch,
) -> None:
    def fake_piano_pipeline(**kwargs):
        assert kwargs["file_name"] == "tongnian.mp3"
        return {
            "analysis_id": kwargs["analysis_id"],
            "tempo": 92,
            "time_signature": kwargs["time_signature"],
            "pitch_sequence": [
                {"time": 0.0, "frequency": 392.0, "duration": 0.5, "note": "G4"},
                {"time": 0.5, "frequency": 440.0, "duration": 0.5, "note": "A4"},
            ],
            "detected_key_signature": "G",
            "key_detection": {"key_signature": "G", "confidence": 0.88, "mode": "major", "fifths": 1},
            "beat_result": {
                "bpm": 92.0,
                "beat_times": [0.0, 0.652, 1.304],
                "beat_quality": {"confidence": 0.62},
                "num_beats": 3,
            },
            "tempo_detection": {
                "detected_tempo": 92,
                "resolved_tempo": 92,
                "used_detected_tempo": True,
                "confidence": 0.62,
                "beat_count": 3,
                "fallback_reason": None,
            },
            "melody_track": {"name": "vocal", "source": "separated_track", "average_confidence": 0.91, "voiced_ratio": 0.9},
            "melody_track_candidates": [],
            "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
            "warnings": [],
            "pipeline": {"separation_enabled": True, "beat_detection_enabled": True},
        }

    monkeypatch.setattr(api_routes_module, "prepare_piano_score_from_audio", fake_piano_pipeline)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/score/from-audio",
            files=[
                ("file", ("tongnian.mp3", b"demo-audio", "audio/mpeg")),
                ("lyrics_file", ("tongnian.lrc", "[00:00.00]你好 世界".encode("utf-8"), "text/plain")),
            ],
            data={
                "user_id": str(score_database["user_id"]),
                "title": "带歌词钢琴谱",
                "tempo": "120",
                "time_signature": "4/4",
                "frame_ms": "20",
                "hop_ms": "10",
                "algorithm": "yin",
                "separation_model": "demucs",
                "separation_stems": "2",
            },
        )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["lyrics_import"]["source"] == "lrc"
    assert body["lyrics_import"]["alignment_mode"] == "timestamped_lines"
    assert body["lyrics_import"]["note_count_with_lyrics"] == 2
    assert body["summary"]["has_lyrics"] is True
    assert body["summary"]["lyric_note_count"] == 2
    assert "<lyric>" in body["musicxml"]


def test_score_creation_from_audio_route_accepts_async_whisperx_mode(
    score_database: dict[str, int | str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(api_routes_module, "validate_whisperx_runtime", lambda: None)

    def fake_async_task(**kwargs):
        score = score_service.create_score_from_pitch_sequence(
            {
                "user_id": score_database["user_id"],
                "title": "WhisperX Async Score",
                "analysis_id": kwargs["analysis_id"],
                "tempo": 96,
                "time_signature": "4/4",
                "key_signature": "C",
                "arrangement_mode": "piano_solo",
                "pitch_sequence": [
                    {"time": 0.0, "frequency": 261.63, "duration": 0.5, "note": "C4"},
                    {"time": 0.5, "frequency": 293.66, "duration": 0.5, "note": "D4"},
                ],
                "lyrics_payload": {
                    "status": "imported",
                    "source": "whisperx_asr",
                    "has_timestamps": True,
                    "timing_kind": "token",
                    "lines": [
                        {
                            "time": 0.0,
                            "text": "你好",
                            "tokens": [
                                {"text": "你", "time": 0.0},
                                {"text": "好", "time": 0.5},
                            ],
                        }
                    ],
                    "line_count": 1,
                    "warnings": [],
                    "language": "zh",
                },
            }
        )
        save_analysis_result(
            analysis_id=kwargs["analysis_id"],
            file_name=kwargs["file_name"],
            sample_rate=kwargs["sample_rate"],
            duration=kwargs["duration"],
            bpm=96,
            status=1,
            params={"lyrics_mode": "asr_whisperx"},
            result_data={
                "task_status": "completed",
                "task_stage": "completed",
                "lyrics_mode": "asr_whisperx",
                "score_id": score["score_id"],
                "arrangement_mode": "piano_solo",
                "score_mode": score.get("score_mode"),
                "detected_key_signature": "C",
                "beat_result": {"bpm": 96.0, "beat_times": [0.0, 0.625]},
                "tempo_detection": {"resolved_tempo": 96, "used_detected_tempo": True},
                "key_detection": {"key_signature": "C", "confidence": 0.8},
                "separation": {"status": "completed", "tracks": [{"name": "vocal"}]},
                "melody_track": {"name": "vocal", "source": "separated_track"},
                "melody_track_candidates": [],
                "pipeline": {"separation_enabled": True, "beat_detection_enabled": True},
                "piano_arrangement": score.get("piano_arrangement"),
                "lyrics_import": score.get("lyrics_import"),
                "warnings": [],
            },
            pitch_sequence=[
                {"time": 0.0, "frequency": 261.63, "duration": 0.5, "note": "C4"},
                {"time": 0.5, "frequency": 293.66, "duration": 0.5, "note": "D4"},
            ],
            user_id=score_database["user_id"],
        )

    monkeypatch.setattr(api_routes_module, "_run_async_piano_score_from_audio_task", fake_async_task)

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/score/from-audio",
            files={"file": ("async.mp3", b"demo-audio", "audio/mpeg")},
            data={
                "user_id": str(score_database["user_id"]),
                "title": "WhisperX Async Score",
                "tempo": "120",
                "time_signature": "4/4",
                "lyrics_mode": "asr_whisperx",
            },
        )
        assert accepted.status_code == 200
        accepted_body = accepted.json()["data"]
        assert accepted_body["accepted"] is True
        assert accepted_body["task_status"] == "pending"
        assert accepted_body["task_stage"] == "queued"

        detail = client.get(f"/api/v1/analysis/{accepted_body['analysis_id']}")

    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["task_status"] == "completed"
    assert body["lyrics_import"]["source"] == "whisperx_asr"
    assert body["lyrics_import"]["language"] == "zh"
    assert body["summary"]["has_lyrics"] is True
    assert "<lyric>" in body["musicxml"]


def test_score_creation_from_audio_route_rejects_whisperx_when_runtime_missing(
    score_database: dict[str, int | str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api_routes_module,
        "validate_whisperx_runtime",
        lambda: (_ for _ in ()).throw(AudioDependencyError("当前环境缺少 ffmpeg，无法运行 WhisperX 自动歌词识别。")),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/score/from-audio",
            files={"file": ("async.mp3", b"demo-audio", "audio/mpeg")},
            data={
                "user_id": str(score_database["user_id"]),
                "title": "WhisperX Missing Runtime",
                "tempo": "120",
                "time_signature": "4/4",
                "lyrics_mode": "asr_whisperx",
            },
        )

    assert response.status_code == 503
    assert "ffmpeg" in response.json()["detail"]


def test_analysis_detail_route_returns_pending_task_payload():
    save_analysis_result(
        analysis_id="an_async_pending",
        file_name="demo.mp3",
        sample_rate=16000,
        duration=30.0,
        bpm=None,
        status=0,
        params={"lyrics_mode": "asr_whisperx"},
        result_data={
            "task_status": "running",
            "task_stage": "asr_transcription",
            "lyrics_mode": "asr_whisperx",
            "warnings": [],
        },
        pitch_sequence=[],
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/analysis/an_async_pending")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["task_status"] == "running"
    assert body["task_stage"] == "asr_transcription"
    assert body["score_id"] is None


def test_score_creation_route_rejects_unknown_user(score_database: dict[str, int | str]) -> None:
    payload = {
        "user_id": int(score_database["user_id"]) + 999,
        "tempo": 120,
        "time_signature": "4/4",
        "key_signature": "C",
        "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/score/from-pitch-sequence", json=payload)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_score_creation_route_falls_back_to_authenticated_user_when_payload_user_is_stale(
    user_database: dict[str, int | str],
) -> None:
    register_payload = {
        "username": "score_api_auth_user",
        "password": "secret123",
        "email": "score_api_auth_user@example.com",
    }
    create_payload = {
        "user_id": 1,
        "title": "Authenticated Fallback Score",
        "tempo": 120,
        "time_signature": "4/4",
        "key_signature": "C",
        "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
    }

    with TestClient(app) as client:
        register_response = client.post("/api/v1/auth/register", json=register_payload)
        assert register_response.status_code == 200

        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": register_payload["username"], "password": register_payload["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json()["data"]["token"]
        auth_user_id = int(login_response.json()["data"]["user"]["user_id"])

        response = client.post(
            "/api/v1/score/from-pitch-sequence",
            json=create_payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["title"] == "Authenticated Fallback Score"

    with session_scope() as session:
        project = session.get(Project, body["project_id"])
        assert project is not None
        assert int(project.user_id) == auth_user_id


def test_score_creation_route_falls_back_to_in_memory_when_db_is_unavailable(
    score_database: dict[str, int | str],
    monkeypatch,
) -> None:
    def raise_db_timeout(*args, **kwargs):
        raise SQLAlchemyError("db unavailable")

    monkeypatch.setattr(score_service, "get_user_by_id", raise_db_timeout)
    monkeypatch.setattr(score_service, "get_sheet_by_score_id", lambda *args, **kwargs: None)

    payload = {
        "user_id": score_database["user_id"],
        "title": "Route In-Memory Score",
        "tempo": 112,
        "time_signature": "4/4",
        "key_signature": "C",
        "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/score/from-pitch-sequence", json=payload)
        assert response.status_code == 200
        body = response.json()["data"]
        exports_response = client.get(f"/api/v1/scores/{body['score_id']}/exports")

    assert body["project_id"] >= score_service.IN_MEMORY_PROJECT_ID_BASE
    assert body["title"] == "Route In-Memory Score"
    assert exports_response.status_code == 200
    assert exports_response.json()["data"]["count"] == 0



def test_export_routes_support_detail_preview_download_regenerate_and_delete(score_database: dict[str, int | str]) -> None:
    create_payload = {
        "user_id": score_database["user_id"],
        "title": "Previewable Score",
        "tempo": 96,
        "time_signature": "4/4",
        "key_signature": "D",
        "pitch_sequence": [
            {"time": 0.0, "frequency": 440.0, "duration": 0.25},
            {"time": 0.25, "frequency": 493.88, "duration": 0.25},
            {"time": 0.5, "frequency": 523.25, "duration": 0.25},
            {"time": 0.75, "frequency": 587.33, "duration": 0.25},
            {"time": 1.0, "frequency": 659.25, "duration": 0.5},
            {"time": 1.5, "frequency": 587.33, "duration": 0.5},
        ],
    }

    with TestClient(app) as client:
        create_response = client.post("/api/v1/score/from-pitch-sequence", json=create_payload)
        assert create_response.status_code == 200
        score_id = create_response.json()["data"]["score_id"]

        pdf_export = client.post(
            f"/api/v1/scores/{score_id}/export",
            json={"format": "pdf", "page_size": "A4", "with_annotations": True},
        )
        png_export = client.post(
            f"/api/v1/scores/{score_id}/export",
            json={"format": "png", "page_size": "A4", "with_annotations": True},
        )

        assert pdf_export.status_code == 200
        assert png_export.status_code == 200

        pdf_data = pdf_export.json()["data"]
        png_data = png_export.json()["data"]

        list_response = client.get(f"/api/v1/scores/{score_id}/exports")
        detail_response = client.get(f"/api/v1/scores/{score_id}/exports/{pdf_data['export_record_id']}")
        pdf_preview = client.get(f"/api/v1/scores/{score_id}/exports/{pdf_data['export_record_id']}/preview")
        pdf_download = client.get(f"/api/v1/scores/{score_id}/exports/{pdf_data['export_record_id']}/download")
        regenerate_response = client.post(
            f"/api/v1/scores/{score_id}/exports/{pdf_data['export_record_id']}/regenerate",
            json={"page_size": "LETTER", "with_annotations": False},
        )
        delete_response = client.delete(f"/api/v1/scores/{score_id}/exports/{png_data['export_record_id']}")
        deleted_detail = client.get(f"/api/v1/scores/{score_id}/exports/{png_data['export_record_id']}")

    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["download_api_url"].endswith("/download")
    assert items[0]["preview_url"].endswith("/preview")
    assert items[0]["regenerate_url"].endswith("/regenerate")
    assert items[0]["delete_url"].endswith(str(items[0]["export_record_id"]))
    assert items[0]["exists"] is True

    detail = detail_response.json()["data"]
    assert detail["export_record_id"] == pdf_data["export_record_id"]
    assert detail["download_url"].startswith("/storage/exports/")
    assert detail["content_type"] == "application/pdf"
    assert f"export_{pdf_data['export_record_id']}" in detail["file_name"]

    assert pdf_data["preview_url"].endswith("/preview")
    assert pdf_data["download_api_url"].endswith("/download")
    assert pdf_preview.status_code == 200
    assert pdf_preview.headers["content-type"].startswith("application/pdf")
    assert "inline" in pdf_preview.headers["content-disposition"]

    assert pdf_download.status_code == 200
    assert pdf_download.headers["content-type"].startswith("application/pdf")
    assert "attachment" in pdf_download.headers["content-disposition"]

    assert regenerate_response.status_code == 200
    regenerated = regenerate_response.json()["data"]
    assert regenerated["regenerated"] is True
    assert regenerated["export_record_id"] == pdf_data["export_record_id"]
    assert regenerated["manifest"]["page_size"] == "LETTER"
    assert regenerated["manifest"]["with_annotations"] is False

    assert delete_response.status_code == 200
    deleted = delete_response.json()["data"]
    assert deleted["deleted"] is True
    assert deleted["export_record_id"] == png_data["export_record_id"]
    assert deleted_detail.status_code == 404


def test_score_routes_support_get_and_full_musicxml_patch(score_database: dict[str, int | str]) -> None:
    create_payload = {
        "user_id": score_database["user_id"],
        "title": "Editable API Score",
        "tempo": 100,
        "time_signature": "4/4",
        "key_signature": "C",
        "pitch_sequence": [{"time": 0.0, "frequency": 440.0, "duration": 0.5}],
    }

    with TestClient(app) as client:
        created = client.post("/api/v1/score/from-pitch-sequence", json=create_payload)
        assert created.status_code == 200
        score_body = created.json()["data"]

        get_response = client.get(f"/api/v1/scores/{score_body['score_id']}")
        patch_response = client.patch(
            f"/api/v1/scores/{score_body['score_id']}",
            json={"musicxml": _replace_tempo(score_body["musicxml"], 72)},
        )

    assert get_response.status_code == 200
    assert get_response.json()["data"]["score_id"] == score_body["score_id"]
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["tempo"] == 72
    assert patch_response.json()["data"]["version"] == 2



def test_missing_score_routes_return_404(score_database: dict[str, int | str]) -> None:
    with TestClient(app) as client:
        edit_response = client.patch("/api/v1/scores/missing_score", json={"musicxml": "<score-partwise />"})
        get_response = client.get("/api/v1/scores/missing_score")
        export_response = client.post(
            "/api/v1/scores/missing_score/export",
            json={"format": "pdf", "page_size": "A4", "with_annotations": True},
        )
        exports_response = client.get("/api/v1/scores/missing_score/exports")
        regenerate_response = client.post(
            "/api/v1/scores/missing_score/exports/1/regenerate",
            json={"page_size": "A4", "with_annotations": True},
        )

    assert edit_response.status_code == 404
    assert get_response.status_code == 404
    assert export_response.status_code == 404
    assert exports_response.status_code == 404
    assert regenerate_response.status_code == 404
