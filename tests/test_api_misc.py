import json

from backend.api.api_routes import (
    audio_log,
    auth_login,
    auth_register,
    favorite_score,
    generation_chords,
    generation_variations,
    get_history,
    get_user_preferences,
    like_score,
    list_community_scores,
    me,
    pitch_compare,
    pitch_curve,
    post_history,
    publish_community_score,
    remove_history,
    reports_export,
    unfavorite_score,
    unlike_score,
    update_user_preferences,
)
from backend.api.schemas import (
    AudioLogRequest,
    ChordGenerationRequest,
    CommunityScorePublishRequest,
    HistoryCreateRequest,
    LoginRequest,
    PitchCompareRequest,
    PreferencesUpdateRequest,
    RegisterRequest,
    ReportExportRequest,
    VariationSuggestionRequest,
)
from backend.user.user_system import get_current_user


def test_misc_api_routes_cover_compare_community_generation_and_chart():
    compare_result = pitch_compare(PitchCompareRequest(reference_id="ref_001", user_recording_id="user_001"))
    community_result = list_community_scores(page=1, page_size=20, keyword="夜曲", tag="钢琴")
    publish_result = publish_community_score(
        CommunityScorePublishRequest(score_id="score_001", title="夜曲", description="demo", tags=["流行"], is_public=True)
    )
    chart_result = pitch_curve("an_001", "compare")
    chord_result = generation_chords(ChordGenerationRequest(key="C", tempo=120, style="pop", melody=[]))
    variation_result = generation_variations(
        VariationSuggestionRequest(score_id="score_001", style="traditional", difficulty="medium")
    )

    assert compare_result["data"]["summary"]["accuracy"] == 100.0
    assert compare_result["data"]["chart"]["chart_type"] == "pitch_comparison"
    assert community_result["data"]["total"] == 1
    assert publish_result["data"]["community_score_id"] == "cmt_score_001"
    assert like_score("score_001")["data"]["liked"] is True
    assert unlike_score("score_001")["data"]["liked"] is False
    assert favorite_score("score_001")["data"]["favorited"] is True
    assert unfavorite_score("score_001")["data"]["favorited"] is False
    assert chart_result["data"]["analysis_id"] == "an_001"
    assert chart_result["data"]["report_payload"]["chart_type"] == "pitch_comparison"
    assert chord_result["data"]["chords"]
    assert variation_result["data"]["suggestions"]


def test_pitch_compare_accepts_json_paths(tmp_path):
    reference_path = tmp_path / "reference_pitch.json"
    user_path = tmp_path / "user_pitch.json"
    reference_path.write_text(
        json.dumps(
            [
                {"time": 0.0, "frequency": 440.0, "confidence": 0.9},
                {"time": 0.5, "frequency": 442.0, "confidence": 0.9},
            ]
        ),
        encoding="utf-8",
    )
    user_path.write_text(
        json.dumps(
            {"pitch_sequence": [{"time": 0.0, "frequency": 441.0}, {"time": 0.5, "frequency": 444.0}]}
        ),
        encoding="utf-8",
    )

    result = pitch_compare(
        PitchCompareRequest(
            reference_pitch_path=str(reference_path),
            user_pitch_path=str(user_path),
        )
    )

    assert result["data"]["reference_curve"] == [440.0, 442.0]
    assert result["data"]["user_curve"] == [441.0, 444.0]
    assert result["data"]["chart"]["series"][2]["id"] == "deviation_cents"
    assert result["data"]["summary"]["matched_points"] == 2


def test_auth_history_log_and_report_routes_work_together():
    register_result = auth_register(RegisterRequest(username="alice", password="password123", email="alice@example.com"))
    login_result = auth_login(LoginRequest(username="alice", password="password123"))
    token = login_result["data"]["token"]
    current_user = get_current_user(f"Bearer {token}")

    me_result = me(current_user=current_user)
    history_result = post_history(
        HistoryCreateRequest(type="score", resource_id="score_001", title="练习乐谱", metadata={"source": "api"}),
        current_user=current_user,
    )
    list_result = get_history(current_user=current_user)
    delete_result = remove_history(history_result["data"]["history_id"], current_user=current_user)
    log_result = audio_log(AudioLogRequest(file_name="demo.wav", sample_rate=16000, duration=1.0, params={"mode": "test"}))
    report_result = reports_export(ReportExportRequest(analysis_id="an_001", formats=["pdf", "png"], include_charts=True))

    assert register_result["data"]["user_id"].startswith("u_")
    assert me_result["data"]["username"] == "alice"
    assert len(list_result["data"]["items"]) == 1
    assert delete_result["data"]["deleted"] is True
    assert log_result["data"]["log_id"].startswith("log_")
    assert log_result["data"]["sample_rate"] == 16000
    assert log_result["data"]["duration"] == 1.0
    assert log_result["data"]["source"] == "api"
    assert log_result["data"]["stage"] == "manual"
    assert len(report_result["data"]["files"]) == 2


def test_preferences_api_get_and_update():
    auth_register(RegisterRequest(username="prefs_user", password="password123"))
    login_result = auth_login(LoginRequest(username="prefs_user", password="password123"))
    token = login_result["data"]["token"]
    current_user = get_current_user(f"Bearer {token}")

    defaults = get_user_preferences(current_user=current_user)
    assert defaults["data"]["audio_engine"] == "default"
    assert "MIDI" in defaults["data"]["export_formats"]

    updated = update_user_preferences(
        PreferencesUpdateRequest(audio_engine="asio", export_formats=["PNG"]),
        current_user=current_user,
    )
    assert updated["data"]["audio_engine"] == "asio"
    assert updated["data"]["export_formats"] == ["PNG"]

    reloaded = get_user_preferences(current_user=current_user)
    assert reloaded["data"]["audio_engine"] == "asio"
