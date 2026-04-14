"""REST and WebSocket routes for the Music AI System."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from backend.api.schemas import (
    AudioLogRequest,
    ChordGenerationRequest,
    CommunityScorePublishRequest,
    HistoryCreateRequest,
    LoginRequest,
    PitchCompareRequest,
    PitchToScoreRequest,
    RegisterRequest,
    ReportExportRequest,
    RhythmScoreRequest,
    ScoreEditRequest,
    ScoreExportRequest,
    ScoreReExportRequest,
    VariationSuggestionRequest,
)
from backend.core.generation.chord_generation import generate_chord_sequence
from backend.core.generation.variation_suggestions import generate_variation_suggestions
from backend.core.pitch.audio_utils import estimate_duration_from_bytes, infer_audio_metadata
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.realtime_tuning import analyze_audio_frame
from backend.core.rhythm.beat_detection import detect_beats
from backend.core.rhythm.rhythm_analysis import score_rhythm
from backend.core.separation.multi_track_separation import separate_tracks
from backend.services.report_service import export_report
from backend.services.score_service import (
    ExportFileNotFoundError,
    ExportRecordNotFoundError,
    ScoreNotFoundError,
    ScoreOperationError,
    UserNotFoundError,
    create_score_from_pitch_sequence,
    delete_score_export,
    edit_score,
    export_score,
    get_score_export_file,
    get_score_export_record,
    list_score_exports,
    regenerate_score_export,
    redo_score,
    undo_score,
)
from backend.user.history_manager import delete_history, list_history, save_history
from backend.user.user_system import get_current_user, login_user, register_user
from backend.utils.audio_logger import record_audio_log
from backend.utils.data_visualizer import build_pitch_curve


router = APIRouter(prefix="/api/v1", tags=["api"])

INLINE_PREVIEW_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "text/plain",
)



def ok(data: Any, message: str = "success") -> Dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


@router.post("/pitch/detect")
async def pitch_detect(
    file: UploadFile = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
):
    content = await file.read()
    resolved_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(content, resolved_sample_rate)
    metadata = infer_audio_metadata(file.filename or "audio", resolved_sample_rate, estimated_duration or None)
    pitches = detect_pitch_sequence(
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        algorithm=algorithm,
        duration=metadata["duration"],
        audio_bytes=content,
    )
    return ok(
        {
            "analysis_id": metadata["analysis_id"],
            "duration": metadata["duration"],
            "sample_rate": metadata["sample_rate"],
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "track_count": 1,
            "tracks": [{"name": file.filename or "audio"}],
            "pitch_sequence": pitches,
        }
    )


@router.post("/pitch/detect-multitrack")
async def pitch_detect_multitrack(
    files: list[UploadFile] = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
):
    if not files:
        raise HTTPException(status_code=400, detail="at least one audio track is required")

    resolved_sample_rate = sample_rate or 16000
    tracks = []
    durations = []
    for index, upload in enumerate(files):
        content = await upload.read()
        if not content:
            continue
        track_name = upload.filename or f"track_{index + 1}"
        tracks.append({"name": track_name, "audio_bytes": content, "sample_rate": resolved_sample_rate})
        durations.append(estimate_duration_from_bytes(content, resolved_sample_rate))

    if not tracks:
        raise HTTPException(status_code=400, detail="uploaded tracks are empty")

    duration = max(durations) if durations else None
    metadata = infer_audio_metadata("multitrack", resolved_sample_rate, duration or None)
    pitches = detect_pitch_sequence(
        file_name="multitrack",
        sample_rate=metadata["sample_rate"],
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        algorithm=algorithm,
        duration=metadata["duration"],
        audio_bytes={"sample_rate": metadata["sample_rate"], "tracks": tracks},
    )
    return ok(
        {
            "analysis_id": metadata["analysis_id"],
            "duration": metadata["duration"],
            "sample_rate": metadata["sample_rate"],
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "track_count": len(tracks),
            "tracks": [{"name": track["name"]} for track in tracks],
            "pitch_sequence": pitches,
        }
    )


@router.websocket("/ws/realtime-pitch")
async def realtime_pitch(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                payload = {"type": "audio_frame", "pcm_bytes": message["bytes"], "sample_rate": 16000}
            else:
                payload = json.loads(message.get("text", "{}"))
            if payload.get("type") == "stop":
                await websocket.send_json({"type": "stopped"})
                break
            if payload.get("type") != "audio_frame":
                await websocket.send_json({"type": "error", "message": "unsupported message type"})
                continue
            frame = payload.get("pcm_bytes") or payload.get("pcm", "").encode("utf-8")
            reference_frequency = payload.get("reference_frequency")
            result = analyze_audio_frame(
                frame,
                int(payload.get("sample_rate", 16000)),
                reference_frequency=float(reference_frequency) if reference_frequency is not None else None,
                timestamp=float(payload.get("timestamp", payload.get("time", 0.0))),
                algorithm=payload.get("algorithm", "yin"),
            )
            await websocket.send_json({"type": "pitch_update", **result})
    except WebSocketDisconnect:
        return


@router.post("/pitch/compare")
def pitch_compare(payload: PitchCompareRequest):
    reference = detect_pitch_sequence(file_name=payload.reference_id, duration=10.0)
    user = detect_pitch_sequence(file_name=payload.user_recording_id, duration=10.0)
    deviation = [
        {"time": item["time"], "cents_offset": item["frequency"] - reference[index]["frequency"]}
        for index, item in enumerate(user[: len(reference)])
    ]
    summary = {
        "accuracy": 92.3,
        "average_deviation": round(sum(entry["cents_offset"] for entry in deviation) / max(len(deviation), 1), 2),
    }
    return ok({"reference": reference, "user": user, "deviation": deviation, "summary": summary})


@router.post("/score/from-pitch-sequence")
def score_from_pitch_sequence(payload: PitchToScoreRequest):
    try:
        return ok(create_score_from_pitch_sequence(payload.model_dump()))
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/scores/{score_id}")
def patch_score(score_id: str, payload: ScoreEditRequest):
    try:
        return ok(edit_score(score_id, [op.model_dump() for op in payload.operations]))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScoreOperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scores/{score_id}/undo")
def score_undo(score_id: str):
    try:
        return ok(undo_score(score_id))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scores/{score_id}/redo")
def score_redo(score_id: str):
    try:
        return ok(redo_score(score_id))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scores/{score_id}/export")
def score_export(score_id: str, payload: ScoreExportRequest):
    try:
        return ok(export_score(score_id, payload.model_dump()))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scores/{score_id}/exports")
def score_export_list(score_id: str):
    try:
        return ok(list_score_exports(score_id))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scores/{score_id}/exports/{export_record_id}")
def score_export_detail(score_id: str, export_record_id: int):
    try:
        return ok(get_score_export_record(score_id, export_record_id))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/scores/{score_id}/exports/{export_record_id}")
def score_export_delete(score_id: str, export_record_id: int):
    try:
        return ok(delete_score_export(score_id, export_record_id))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scores/{score_id}/exports/{export_record_id}/regenerate")
def score_export_regenerate(score_id: str, export_record_id: int, payload: ScoreReExportRequest):
    try:
        return ok(regenerate_score_export(score_id, export_record_id, payload.model_dump()))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scores/{score_id}/exports/{export_record_id}/download")
def score_export_download(score_id: str, export_record_id: int):
    try:
        export_data = get_score_export_file(score_id, export_record_id)
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=export_data["file_path"],
        filename=export_data["file_name"],
        media_type=export_data["content_type"],
        content_disposition_type="attachment",
    )


@router.get("/scores/{score_id}/exports/{export_record_id}/preview")
def score_export_preview(score_id: str, export_record_id: int):
    try:
        export_data = get_score_export_file(score_id, export_record_id)
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    disposition = "inline" if str(export_data["content_type"]).startswith(INLINE_PREVIEW_TYPES) else "attachment"
    return FileResponse(
        path=export_data["file_path"],
        filename=export_data["file_name"],
        media_type=export_data["content_type"],
        content_disposition_type=disposition,
    )


@router.post("/rhythm/beat-detect")
async def rhythm_beat_detect(
    file: UploadFile = File(...),
    bpm_hint: Optional[int] = Form(None),
    sensitivity: float = Form(0.5),
):
    content = await file.read()
    result = detect_beats(file.filename or "audio", bpm_hint=bpm_hint, sensitivity=sensitivity, audio_bytes=content)
    return ok(result)


@router.post("/audio/separate-tracks")
async def audio_separate_tracks(
    file: UploadFile = File(...),
    model: str = Form("demucs"),
    stems: int = Form(2),
):
    content = await file.read()
    return ok(separate_tracks(file.filename or "audio", model=model, stems=stems, audio_bytes=content))


@router.post("/rhythm/score")
def rhythm_score(payload: RhythmScoreRequest):
    return ok(score_rhythm(payload.reference_beats, payload.user_beats))


@router.get("/community/scores")
def list_community_scores(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
):
    items = [
        {
            "score_id": "score_1001",
            "title": "澶滄洸",
            "author": "user_01",
            "likes": 56,
            "favorites": 24,
            "tags": ["娴佽", "閽㈢惔"],
        }
    ]
    return ok({"total": len(items), "items": items, "page": page, "page_size": page_size, "keyword": keyword, "tag": tag})


@router.post("/community/scores")
def publish_community_score(payload: CommunityScorePublishRequest):
    return ok({"community_score_id": f"cmt_{payload.score_id}", "published_at": "2026-04-11T10:30:00+08:00"})


@router.post("/community/scores/{score_id}/like")
def like_score(score_id: str):
    return ok({"score_id": score_id, "liked": True})


@router.delete("/community/scores/{score_id}/like")
def unlike_score(score_id: str):
    return ok({"score_id": score_id, "liked": False})


@router.post("/community/scores/{score_id}/favorite")
def favorite_score(score_id: str):
    return ok({"score_id": score_id, "favorited": True})


@router.delete("/community/scores/{score_id}/favorite")
def unfavorite_score(score_id: str):
    return ok({"score_id": score_id, "favorited": False})


@router.post("/logs/audio")
def audio_log(payload: AudioLogRequest):
    return ok(record_audio_log(payload.model_dump()))


@router.get("/charts/pitch-curve")
def pitch_curve(analysis_id: str = Query(...), mode: str = Query("compare")):
    reference_curve = detect_pitch_sequence(file_name=f"{analysis_id}_reference", duration=3.0)
    user_curve = detect_pitch_sequence(file_name=f"{analysis_id}_user", duration=3.0)
    return ok({"analysis_id": analysis_id, "mode": mode, **build_pitch_curve(reference_curve, user_curve)})


@router.post("/generation/chords")
def generation_chords(payload: ChordGenerationRequest):
    return ok(generate_chord_sequence(payload.key, payload.tempo, payload.style, payload.melody))


@router.post("/generation/variation-suggestions")
def generation_variations(payload: VariationSuggestionRequest):
    return ok(generate_variation_suggestions(payload.score_id, payload.style, payload.difficulty))


@router.post("/auth/register")
def auth_register(payload: RegisterRequest):
    return ok(register_user(payload.username, payload.password, payload.email))


@router.post("/auth/login")
def auth_login(payload: LoginRequest):
    return ok(login_user(payload.username, payload.password))


@router.get("/users/me")
def me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(current_user)


@router.get("/users/me/history")
def get_history(current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(list_history(current_user["user_id"]))


@router.post("/users/me/history")
def post_history(payload: HistoryCreateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(save_history(current_user["user_id"], payload.model_dump()))


@router.delete("/users/me/history/{history_id}")
def remove_history(history_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(delete_history(current_user["user_id"], history_id))


@router.post("/reports/export")
def reports_export(payload: ReportExportRequest):
    return ok(export_report(payload.model_dump()))
