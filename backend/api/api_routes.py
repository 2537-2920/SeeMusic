"""REST and WebSocket routes for the Music AI System."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect

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
    VariationSuggestionRequest,
)
from backend.core.generation.chord_generation import generate_chord_sequence
from backend.core.generation.variation_suggestions import generate_variation_suggestions
from backend.core.pitch.audio_utils import infer_audio_metadata
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.realtime_tuning import analyze_audio_frame
from backend.core.rhythm.beat_detection import detect_beats
from backend.core.rhythm.rhythm_analysis import score_rhythm
from backend.core.separation.multi_track_separation import separate_tracks
from backend.services.report_service import export_report
from backend.services.score_service import (
    ScoreNotFoundError,
    ScoreOperationError,
    create_score_from_pitch_sequence,
    edit_score,
    export_score,
    redo_score,
    undo_score,
)
from backend.user.history_manager import delete_history, list_history, save_history
from backend.user.user_system import get_current_user, login_user, register_user
from backend.utils.audio_logger import record_audio_log
from backend.utils.data_visualizer import build_pitch_curve


router = APIRouter(prefix="/api/v1", tags=["api"])

<<<<<<< Updated upstream
=======
INLINE_PREVIEW_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "text/plain",
)

COMMUNITY_SCORE_MAX_BYTES = 20 * 1024 * 1024
COMMUNITY_COVER_MAX_BYTES = 5 * 1024 * 1024
COMMUNITY_COVER_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
COMMUNITY_COVER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


>>>>>>> Stashed changes

def ok(data: Any, message: str = "success") -> Dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


<<<<<<< Updated upstream
=======
def optional_user_from_authorization(authorization: str = "") -> Dict[str, Any] | None:
    if not isinstance(authorization, str):
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None
    try:
        return get_user_by_token(token)
    except HTTPException:
        return None


def optional_query_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default


def _resolve_cover_suffix(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower().strip()
    if content_type in COMMUNITY_COVER_TYPES:
        return COMMUNITY_COVER_TYPES[content_type]
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in COMMUNITY_COVER_EXTENSIONS:
        return suffix
    raise HTTPException(status_code=400, detail="cover image must be PNG, JPG, WEBP, or GIF")


def resolve_pitch_sequence_source(
    *,
    pitch_path: str | None = None,
    pitch_sequence: list[dict[str, Any]] | None = None,
    fallback_id: str | None = None,
    duration: float = 10.0,
) -> list[dict[str, Any]]:
    # Ensure pitch_path is a string or None (not a Query object)
    if pitch_path is not None and not isinstance(pitch_path, str):
        pitch_path = None
    
    if pitch_sequence:
        return pitch_sequence
    if pitch_path:
        try:
            return load_pitch_sequence_json(pitch_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if fallback_id:
        saved_sequence = get_saved_pitch_sequence(fallback_id)
        if saved_sequence:
            return saved_sequence
        if fallback_id.endswith("_reference"):
            saved_sequence = get_saved_pitch_sequence(fallback_id[: -len("_reference")])
            if saved_sequence:
                return saved_sequence
        if fallback_id.endswith("_user"):
            saved_sequence = get_saved_pitch_sequence(fallback_id[: -len("_user")])
            if saved_sequence:
                return saved_sequence
        return detect_pitch_sequence(file_name=fallback_id, duration=duration)
    raise HTTPException(status_code=400, detail="missing pitch source")


>>>>>>> Stashed changes
@router.post("/pitch/detect")
async def pitch_detect(
    file: UploadFile = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
):
    content = await file.read()
    metadata = infer_audio_metadata(file.filename or "audio", sample_rate, None)
    pitches = detect_pitch_sequence(
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        algorithm=algorithm,
        duration=metadata["duration"],
        audio_bytes=content,
    )
    return ok({"analysis_id": metadata["analysis_id"], "duration": metadata["duration"], "pitch_sequence": pitches})


@router.websocket("/ws/realtime-pitch")
async def realtime_pitch(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)
            if payload.get("type") == "stop":
                await websocket.send_json({"type": "stopped"})
                break
            if payload.get("type") != "audio_frame":
                await websocket.send_json({"type": "error", "message": "unsupported message type"})
                continue
            frame = payload.get("pcm", "").encode("utf-8")
            result = analyze_audio_frame(frame, int(payload.get("sample_rate", 16000)))
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
    return ok(create_score_from_pitch_sequence(payload.model_dump()))


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
            "title": "夜曲",
            "author": "user_01",
            "likes": 56,
            "favorites": 24,
            "tags": ["流行", "钢琴"],
        }
    ]
    return ok({"total": len(items), "items": items, "page": page, "page_size": page_size, "keyword": keyword, "tag": tag})


@router.post("/community/scores")
<<<<<<< Updated upstream
def publish_community_score(payload: CommunityScorePublishRequest):
    return ok({"community_score_id": f"cmt_{payload.score_id}", "published_at": "2026-04-11T10:30:00+08:00"})
=======
def publish_community_score(payload: CommunityScorePublishRequest, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    return ok(publish_community_score_data(payload.model_dump(), current_user=current_user))


@router.post("/community/scores/upload")
async def upload_community_score(
    file: UploadFile = File(...),
    cover_file: UploadFile | None = File(default=None),
    title: str = Form(...),
    style: str = Form("精选"),
    instrument: str = Form("乐谱"),
    price: float = Form(0.0),
    description: str = Form(""),
    tags: str = Form(""),
    authorization: str = Header(default=""),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty upload file")
    if len(content) > COMMUNITY_SCORE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="file exceeds 20MB limit")

    cover_url = None
    if cover_file is not None:
        cover_content = await cover_file.read()
        if not cover_content:
            raise HTTPException(status_code=400, detail="empty cover file")
        if len(cover_content) > COMMUNITY_COVER_MAX_BYTES:
            raise HTTPException(status_code=400, detail="cover image exceeds 5MB limit")
        _resolve_cover_suffix(cover_file)

    current_user = optional_user_from_authorization(authorization)
    payload = {
        "title": title,
        "description": description,
        "style": style,
        "instrument": instrument,
        "price": price,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
        "source_file_name": file.filename or "community-upload.bin",
        "cover_url": cover_url,
        "cover_image": cover_content if cover_file is not None else None,
        "cover_content_type": (cover_file.content_type or "image/png") if cover_file is not None else None,
        "is_public": True,
    }
    published = publish_community_score_data(payload, current_user=current_user)
    published["upload"] = {
        "file_name": file.filename or "community-upload.bin",
        "size_bytes": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "cover_file_name": cover_file.filename if cover_file is not None else None,
        "cover_url": published["item"].get("cover_url"),
    }
    return ok(published)


@router.get("/community/scores/{score_id}/comments")
def list_community_score_comments(
    score_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        return ok(
            list_community_comments_data(
                score_id,
                page=optional_query_int(page, 1),
                page_size=optional_query_int(page_size, 20),
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/community/scores/{score_id}/comments")
def post_community_score_comment(
    score_id: str,
    payload: CommunityCommentCreateRequest,
    authorization: str = Header(default=""),
):
    current_user = optional_user_from_authorization(authorization)
    try:
        return ok(add_community_comment(score_id, payload.model_dump(), current_user=current_user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/community/scores/{score_id}/download")
def download_community_score(score_id: str):
    try:
        return ok(register_score_download(score_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
>>>>>>> Stashed changes


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
