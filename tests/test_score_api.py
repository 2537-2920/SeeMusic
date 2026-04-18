from __future__ import annotations

import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

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
