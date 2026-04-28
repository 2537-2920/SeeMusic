from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.reference_track_service import (
    build_reference_audio_url,
    search_reference_tracks,
    upsert_reference_track,
)


def test_reference_track_search_matches_artist_keyword(user_database) -> None:
    upsert_reference_track(
        song_name="Keyword Song",
        artist_name="Keyword Artist",
        audio_url=build_reference_audio_url("keyword-song.wav"),
    )

    matches = search_reference_tracks("Artist")

    assert len(matches) == 1
    assert matches[0]["song_name"] == "Keyword Song"


def test_singing_evaluate_uses_reference_ref_id_from_mysql(user_database, monkeypatch, tmp_path: Path) -> None:
    from backend.config.settings import settings

    storage_dir = tmp_path / "storage"
    reference_file = storage_dir / "reference_audio" / "keyword-song.mp3"
    reference_file.parent.mkdir(parents=True, exist_ok=True)
    reference_file.write_bytes(b"reference-from-db")
    object.__setattr__(settings, "storage_dir", storage_dir)

    reference_track = upsert_reference_track(
        song_name="Keyword Song",
        artist_name="Keyword Artist",
        audio_url=build_reference_audio_url(reference_file.name),
    )
    captured: dict[str, object] = {}

    def fake_evaluate_singing(**kwargs):
        captured.update(kwargs)
        return {
            "analysis_id": "an_singing_ref",
            "overall_score": 91,
            "score": 90,
            "scoring_model": "balanced",
            "user_audio_mode": kwargs["user_audio_mode"],
            "resolved_ref_id": kwargs.get("reference_ref_id"),
            "reference_track": kwargs.get("reference_track"),
            "rhythm": {"score": 90},
            "pitch_comparison": {"summary": {"accuracy": 92}},
        }

    monkeypatch.setattr("backend.api.api_routes.evaluate_singing", fake_evaluate_singing)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/singing/evaluate",
            data={"reference_ref_id": reference_track["ref_id"], "user_audio_mode": "a_cappella"},
            files={"user_audio": ("user.wav", b"user-audio", "audio/wav")},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["reference_track"]["song_name"] == "Keyword Song"
    assert captured["reference_file_name"] == reference_file.name
    assert captured["reference_audio_bytes"] == b"reference-from-db"
    assert captured["reference_ref_id"] == reference_track["ref_id"]


def test_singing_evaluate_returns_404_when_reference_file_missing(user_database, tmp_path: Path) -> None:
    from backend.config.settings import settings

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    object.__setattr__(settings, "storage_dir", storage_dir)

    reference_track = upsert_reference_track(
        song_name="Missing Song",
        artist_name="Missing Artist",
        audio_url=build_reference_audio_url("missing.wav"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/singing/evaluate",
            data={"reference_ref_id": reference_track["ref_id"]},
            files={"user_audio": ("user.wav", b"user-audio", "audio/wav")},
        )

    assert response.status_code == 404


def test_singing_evaluate_keeps_legacy_reference_upload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_evaluate_singing(**kwargs):
        captured.update(kwargs)
        return {
            "analysis_id": "an_singing_upload",
            "overall_score": 88,
            "score": 88,
            "scoring_model": "balanced",
            "user_audio_mode": kwargs["user_audio_mode"],
            "resolved_ref_id": kwargs.get("reference_ref_id"),
            "reference_track": kwargs.get("reference_track"),
            "rhythm": {"score": 88},
            "pitch_comparison": {"summary": {"accuracy": 88}},
        }

    monkeypatch.setattr("backend.api.api_routes.evaluate_singing", fake_evaluate_singing)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/singing/evaluate",
            data={"user_audio_mode": "with_accompaniment"},
            files={
                "reference_audio": ("standard.wav", b"reference-upload", "audio/wav"),
                "user_audio": ("user.wav", b"user-audio", "audio/wav"),
            },
        )

    assert response.status_code == 200
    assert captured["reference_file_name"] == "standard.wav"
    assert captured["reference_audio_bytes"] == b"reference-upload"
    assert captured["reference_ref_id"] is None
    assert captured["reference_track"] is None


def test_singing_evaluate_rejects_ambiguous_reference_source(user_database, tmp_path: Path) -> None:
    from backend.config.settings import settings

    storage_dir = tmp_path / "storage"
    reference_file = storage_dir / "reference_audio" / "song.wav"
    reference_file.parent.mkdir(parents=True, exist_ok=True)
    reference_file.write_bytes(b"reference")
    object.__setattr__(settings, "storage_dir", storage_dir)

    reference_track = upsert_reference_track(
        song_name="Ambiguous Song",
        artist_name="Ambiguous Artist",
        audio_url=build_reference_audio_url(reference_file.name),
    )

    with TestClient(app) as client:
        both_response = client.post(
            "/api/v1/singing/evaluate",
            data={"reference_ref_id": reference_track["ref_id"]},
            files={
                "reference_audio": ("standard.wav", b"reference-upload", "audio/wav"),
                "user_audio": ("user.wav", b"user-audio", "audio/wav"),
            },
        )
        missing_response = client.post(
            "/api/v1/singing/evaluate",
            files={"user_audio": ("user.wav", b"user-audio", "audio/wav")},
        )

    assert both_response.status_code == 400
    assert missing_response.status_code == 400
