"""REST and WebSocket routes for the Music AI System."""

from __future__ import annotations

import json
import os
import uuid
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from backend.api.schemas import (
    AnalyzeRhythmRequest,
    AudioLogRequest,
    ChordGenerationRequest,
    CommunityCommentCreateRequest,
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
from backend.core.pitch.pitch_comparison import build_pitch_comparison_payload, load_pitch_sequence_json
from backend.core.pitch.audio_utils import infer_audio_metadata
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.realtime_tuning import analyze_audio_frame
from backend.core.separation.multi_track_separation import separate_tracks
from backend.services.report_service import export_report
from backend.services.community_service import (
    add_community_comment,
    get_community_score_detail as get_community_score_detail_data,
    list_community_comments as list_community_comments_data,
    list_community_scores as list_community_scores_data,
    list_community_tags as list_community_tags_data,
    publish_community_score as publish_community_score_data,
    register_score_download,
    set_score_favorite,
    set_score_like,
)
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
from backend.user.user_system import get_current_user, get_user_by_token, login_user, register_user
from backend.utils.audio_logger import record_audio_log, record_audio_processing_log

# 引入节奏处理服务与项目配置项
from backend.services.analysis_service import process_rhythm_scoring
from backend.config.settings import settings


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
        return detect_pitch_sequence(file_name=fallback_id, duration=duration)
    raise HTTPException(status_code=400, detail="missing pitch source")


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
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="pitch_detect",
        params={"frame_ms": frame_ms, "hop_ms": hop_ms, "algorithm": algorithm},
    )
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
            "pitch_sequence": pitches,
            "audio_log": log_entry,
        }
    )


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
    reference = resolve_pitch_sequence_source(
        pitch_path=payload.reference_pitch_path,
        pitch_sequence=[item.model_dump() for item in payload.reference_pitch_sequence]
        if payload.reference_pitch_sequence
        else None,
        fallback_id=payload.reference_id,
    )
    user = resolve_pitch_sequence_source(
        pitch_path=payload.user_pitch_path,
        pitch_sequence=[item.model_dump() for item in payload.user_pitch_sequence]
        if payload.user_pitch_sequence
        else None,
        fallback_id=payload.user_recording_id,
    )
    comparison = build_pitch_comparison_payload(
        reference,
        user,
        time_range=payload.range.model_dump() if payload.range else None,
        mode="compare",
    )
    return ok(
        {
            "reference": comparison["reference_points"],
            "user": comparison["user_points"],
            "deviation": comparison["deviation"],
            "summary": comparison["summary"],
            "alignment": comparison["alignment"],
            "chart": comparison["report_payload"],
            "x_axis": comparison["x_axis"],
            "reference_curve": comparison["reference_curve"],
            "user_curve": comparison["user_curve"],
            "deviation_curve": comparison["deviation_curve"],
            "deviation_cents_curve": comparison["deviation_cents_curve"],
        }
    )


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
    from backend.core.rhythm.beat_detection import detect_beats

    content = await file.read()
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        source="api",
        stage="rhythm_beat_detect",
        params={"bpm_hint": bpm_hint, "sensitivity": sensitivity},
    )
    result = detect_beats(file.filename or "audio", bpm_hint=bpm_hint, sensitivity=sensitivity, audio_bytes=content)
    return ok({**result, "audio_log": log_entry})


@router.post("/audio/separate-tracks")
async def audio_separate_tracks(
    file: UploadFile = File(...),
    model: str = Form("demucs"),
    stems: int = Form(2),
):
    content = await file.read()
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        source="api",
        stage="audio_separate_tracks",
        params={"model": model, "stems": stems},
    )
    result = separate_tracks(file.filename or "audio", model=model, stems=stems, audio_bytes=content)
    return ok({**result, "audio_log": log_entry})


@router.post("/rhythm/score")
def rhythm_score(payload: RhythmScoreRequest):
    """Score user's rhythm performance against reference beats.
    
    Supports multilingual feedback and configurable scoring models.
    
    Request body:
    - reference_beats: List of reference beat timestamps (seconds)
    - user_beats: List of user beat timestamps (seconds)
    - language: Language for feedback ('en' or 'zh'). Default: 'en'
    - scoring_model: 'strict', 'balanced' (default), or 'lenient'
    - threshold_ms: Time window for on-time classification. Default: 50ms
    
    Response includes:
    - score: Overall score (0-100)
    - timing_accuracy: Timing accuracy percentage
    - feedback: Multilingual feedback messages
    - detailed_assessment: Detailed evaluation in user's language
    """
    from backend.core.rhythm.rhythm_analysis import score_rhythm

    try:
        result = score_rhythm(
            payload.user_beats,
            payload.reference_beats,
            scoring_model=payload.scoring_model,
            language=payload.language,
            threshold_ms=payload.threshold_ms,
        )
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rhythm scoring failed: {str(e)}") from e


# ==========================================
# 新增：端到端的节奏音频分析接口
# ==========================================
@router.post("/analyze/rhythm")
async def analyze_rhythm_api(
    user_audio: UploadFile = File(...),
    ref_id: str = Form("default_ref"),
    language: str = Form("en"),
    scoring_model: str = Form("balanced"),
    threshold_ms: float = Form(50.0),
):
    """
    End-to-end rhythm analysis: compare user audio against reference track.
    
    Performs beat detection on both audios and provides comprehensive rhythm scoring
    with multilingual feedback.
    
    Parameters:
    - user_audio: User's audio file (WAV/MP3)
    - ref_id: Reference audio ID (stored in assets/references/{ref_id}.wav)
    - language: Feedback language ('en' for English, 'zh' for Chinese). Default: 'en'
    - scoring_model: Scoring model ('strict', 'balanced', 'lenient'). Default: 'balanced'
    
    Returns:
    - score: Overall rhythm score (0-100)
    - timing_accuracy: Accuracy percentage
    - feedback: Multilingual feedback with specific improvement suggestions
    - detailed_assessment: Detailed evaluation in user's language
    - tempo_analysis: Tempo stability metrics
    - error_classification: Categorization of timing errors
    """
    # Ensure storage directory exists
    storage_dir = getattr(settings, "storage_dir", "temp")
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)

    # Generate unique temporary filename to prevent concurrent conflicts
    file_ext = os.path.splitext(user_audio.filename)[1] if user_audio.filename else ".wav"
    temp_filename = f"rhythm_{uuid.uuid4().hex}{file_ext}"
    temp_user_path = os.path.join(storage_dir, temp_filename)

    try:
        # Save uploaded file
        content = await user_audio.read()
        with open(temp_user_path, "wb") as f:
            f.write(content)
        log_entry = record_audio_processing_log(
            file_name=user_audio.filename or "audio",
            audio_bytes=content,
            source="api",
            stage="analyze_rhythm_upload",
            params={"ref_id": ref_id, "language": language, "scoring_model": scoring_model, "threshold_ms": threshold_ms},
        )
        
        # Construct reference audio path
        ref_audio_path = os.path.join("assets", "references", f"{ref_id}.wav")
        
        # Check if reference audio exists
        if not os.path.exists(ref_audio_path):
            logging.error(f"Reference audio file not found: {ref_audio_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Reference audio with ID '{ref_id}' not found. Please check assets/references/ directory.",
            )
        
        # Call service layer core logic with language and scoring model support
        report = await process_rhythm_scoring(
            temp_user_path,
            ref_audio_path,
            language=language,
            scoring_model=scoring_model,
            threshold_ms=threshold_ms,
        )
        
        return ok({**report, "audio_log": log_entry})

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logging.error(f"File not found during rhythm analysis: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail=f"Audio file error: {str(e)}",
        ) from e
    except Exception as e:
        logging.error(f"Rhythm analysis error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Rhythm analysis failed: {str(e)}. Please ensure both audio files are valid WAV/MP3 format.",
        ) from e
    
    finally:
        # Cleanup temporary file
        if os.path.exists(temp_user_path):
            try:
                os.remove(temp_user_path)
            except Exception as cleanup_error:
                logging.warning(f"Failed to cleanup temp file {temp_user_path}: {cleanup_error}")
# ==========================================


@router.get("/community/scores")
def list_community_scores(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    authorization: str = Header(default=""),
):
    current_user = optional_user_from_authorization(authorization)
    return ok(
        list_community_scores_data(
            page=optional_query_int(page, 1),
            page_size=optional_query_int(page_size, 20),
            keyword=keyword,
            tag=tag,
            current_user=current_user,
        )
    )


@router.get("/community/tags")
def list_community_tags():
    return ok(list_community_tags_data())


@router.get("/community/scores/{score_id}")
def get_community_score_detail(score_id: str, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    try:
        return ok(get_community_score_detail_data(score_id, current_user=current_user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/community/scores")
def publish_community_score(payload: CommunityScorePublishRequest, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    return ok(publish_community_score_data(payload.model_dump(), current_user=current_user))


@router.post("/community/scores/upload")
async def upload_community_score(
    file: UploadFile = File(...),
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
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file exceeds 20MB limit")

    current_user = optional_user_from_authorization(authorization)
    payload = {
        "title": title,
        "description": description,
        "style": style,
        "instrument": instrument,
        "price": price,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
        "source_file_name": file.filename or "community-upload.bin",
        "is_public": True,
    }
    published = publish_community_score_data(payload, current_user=current_user)
    published["upload"] = {
        "file_name": file.filename or "community-upload.bin",
        "size_bytes": len(content),
        "content_type": file.content_type or "application/octet-stream",
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


@router.post("/community/scores/{score_id}/like")
def like_score(score_id: str, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    try:
        return ok(set_score_like(score_id, liked=True, current_user=current_user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/community/scores/{score_id}/like")
def unlike_score(score_id: str, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    try:
        return ok(set_score_like(score_id, liked=False, current_user=current_user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/community/scores/{score_id}/favorite")
def favorite_score(score_id: str, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    try:
        return ok(set_score_favorite(score_id, favorited=True, current_user=current_user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/community/scores/{score_id}/favorite")
def unfavorite_score(score_id: str, authorization: str = Header(default="")):
    current_user = optional_user_from_authorization(authorization)
    try:
        return ok(set_score_favorite(score_id, favorited=False, current_user=current_user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/logs/audio")
def audio_log(payload: AudioLogRequest):
    return ok(record_audio_log(payload.model_dump()))


@router.get("/charts/pitch-curve")
def pitch_curve(
    analysis_id: str = Query(...),
    mode: str = Query("compare"),
    reference_pitch_path: str | None = Query(None),
    user_pitch_path: str | None = Query(None),
):
    reference_curve = resolve_pitch_sequence_source(
        pitch_path=reference_pitch_path,
        fallback_id=f"{analysis_id}_reference",
        duration=3.0,
    )
    user_curve = resolve_pitch_sequence_source(
        pitch_path=user_pitch_path,
        fallback_id=f"{analysis_id}_user",
        duration=3.0,
    )
    return ok({"analysis_id": analysis_id, **build_pitch_comparison_payload(reference_curve, user_curve, mode=mode)})


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
