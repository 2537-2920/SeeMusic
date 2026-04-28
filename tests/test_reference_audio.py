from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.reference_track_service import (
    build_reference_audio_url,
    resolve_storage_url_path,
    search_reference_tracks,
    upsert_reference_track,
)
from scripts.upload_reference_audio import parse_track_filename


def test_parse_track_filename_supports_all_planned_formats(tmp_path: Path) -> None:
    numbered_dot_artist_title = parse_track_filename(tmp_path / "0444.F4-流星雨.wav")
    numbered_dash = parse_track_filename(tmp_path / "0001-周杰伦-稻香.wav")
    artist_dash = parse_track_filename(tmp_path / "周杰伦-稻香.wav")
    numbered_dot = parse_track_filename(tmp_path / "0001.稻香.周杰伦.wav")
    title_only = parse_track_filename(tmp_path / "稻香.wav")

    assert (numbered_dot_artist_title.artist_name, numbered_dot_artist_title.song_name) == ("F4", "流星雨")
    assert (numbered_dash.artist_name, numbered_dash.song_name) == ("周杰伦", "稻香")
    assert (artist_dash.artist_name, artist_dash.song_name) == ("周杰伦", "稻香")
    assert (numbered_dot.artist_name, numbered_dot.song_name) == ("周杰伦", "稻香")
    assert (title_only.artist_name, title_only.song_name) == ("未知歌手", "稻香")


def test_reference_track_upsert_updates_audio_url_and_searches(user_database) -> None:
    first = upsert_reference_track(
        song_name="稻香",
        artist_name="周杰伦",
        audio_url=build_reference_audio_url("0001-周杰伦-稻香.wav"),
    )
    second = upsert_reference_track(
        song_name="稻香",
        artist_name="周杰伦",
        audio_url=build_reference_audio_url("0002-周杰伦-稻香.wav"),
    )
    matches = search_reference_tracks("稻香")

    assert first["ref_id"] == second["ref_id"]
    assert second["audio_url"].endswith("0002-\u5468\u6770\u4f26-\u7a3b\u9999.wav")
    assert len(matches) == 1
    assert matches[0]["artist_name"] == "周杰伦"


def test_resolve_storage_url_path_stays_within_storage(tmp_path, monkeypatch) -> None:
    storage_dir = tmp_path / "storage"
    audio_file = storage_dir / "reference_audio" / "song.wav"
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"demo")
    from backend.config.settings import settings

    object.__setattr__(settings, "storage_dir", storage_dir)

    resolved = resolve_storage_url_path("/storage/reference_audio/song.wav")

    assert resolved == audio_file.resolve()


def test_analyze_rhythm_uses_reference_track_audio_from_mysql(user_database, monkeypatch, tmp_path) -> None:
    from backend.config.settings import settings

    storage_dir = tmp_path / "storage"
    reference_file = storage_dir / "reference_audio" / "0001-\u5468\u6770\u4f26-\u7a3b\u9999.wav"
    reference_file.parent.mkdir(parents=True, exist_ok=True)
    reference_file.write_bytes(b"reference")
    object.__setattr__(settings, "storage_dir", storage_dir)

    reference_track = upsert_reference_track(
        song_name="稻香",
        artist_name="周杰伦",
        audio_url=build_reference_audio_url(reference_file.name),
    )

    captured: dict[str, str] = {}

    async def fake_process_rhythm_scoring(user_path: str, ref_path: str, **kwargs):
        captured["user_path"] = user_path
        captured["ref_path"] = ref_path
        return {
            "score": 90,
            "timing_accuracy": 0.9,
            "feedback": ["ok"],
            "detailed_assessment": "ok",
            "tempo_analysis": {},
            "error_classification": {},
            "user_duration": 1.0,
            "user_bpm": 120,
        }

    monkeypatch.setattr("backend.api.api_routes.process_rhythm_scoring", fake_process_rhythm_scoring)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze/rhythm",
            data={"ref_id": reference_track["ref_id"], "language": "zh", "scoring_model": "balanced", "threshold_ms": "50"},
            files={"user_audio": ("user.wav", b"user-audio", "audio/wav")},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["reference_track"]["song_name"] == "稻香"
    assert captured["ref_path"] == str(reference_file.resolve())


def test_analyze_rhythm_returns_404_when_reference_file_missing(user_database, monkeypatch, tmp_path) -> None:
    from backend.config.settings import settings

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    object.__setattr__(settings, "storage_dir", storage_dir)

    reference_track = upsert_reference_track(
        song_name="晴天",
        artist_name="周杰伦",
        audio_url=build_reference_audio_url("missing.wav"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze/rhythm",
            data={"ref_id": reference_track["ref_id"]},
            files={"user_audio": ("user.wav", b"user-audio", "audio/wav")},
        )

    assert response.status_code == 404
    assert "参考音频文件不存在" in response.json()["detail"]
