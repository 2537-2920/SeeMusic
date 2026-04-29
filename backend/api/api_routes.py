"""REST and WebSocket routes for the Music AI System."""

from __future__ import annotations

from copy import deepcopy
import base64
import json
import os
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi import Response
from urllib.parse import quote

from backend.api.schemas import (
    AnalyzeRhythmRequest,
    AudioLogRequest,
    ChordGenerationRequest,
    CommunityCommentCreateRequest,
    CommunityScorePublishRequest,
    DiziScoreExportRequest,
    DiziScoreRequest,
    GuzhengScoreExportRequest,
    GuzhengScoreRequest,
    GuitarLeadSheetExportRequest,
    GuitarLeadSheetRequest,
    HistoryCreateRequest,
    LoginRequest,
    PitchCompareRequest,
    PitchToScoreRequest,
    PreferencesUpdateRequest,
    RegisterRequest,
    ReportExportRequest,
    RhythmScoreRequest,
    ScoreExportRequest,
    ScoreReExportRequest,
    ScoreUpdateRequest,
    TransposeSuggestionRequest,
    UserUpdatePayload,
    VariationSuggestionRequest,
)
from backend.export.traditional_export import (
    TraditionalExportCompileError,
    TraditionalExportDependencyError,
    TraditionalExportError,
    export_traditional_score,
)
from backend.export.guitar_export import (
    GuitarExportDependencyError,
    GuitarExportError,
    export_guitar_lead_sheet_pdf,
)
from backend.core.dizi.audio_pipeline import generate_dizi_score_from_audio
from backend.core.dizi.notation import (
    generate_dizi_score,
    generate_dizi_score_from_musicxml,
    generate_dizi_score_from_pitch_sequence,
)
from backend.core.guzheng.audio_pipeline import generate_guzheng_score_from_audio
from backend.core.guzheng.notation import (
    generate_guzheng_score,
    generate_guzheng_score_from_musicxml,
    generate_guzheng_score_from_pitch_sequence,
)
from backend.core.guitar.audio_pipeline import generate_guitar_lead_sheet_from_audio
from backend.core.guitar.lead_sheet import generate_guitar_lead_sheet, generate_guitar_lead_sheet_from_musicxml
from backend.core.generation.chord_generation import generate_chord_sequence
from backend.core.generation.transpose_suggestions import generate_transpose_suggestions
from backend.core.generation.variation_suggestions import generate_variation_suggestions
from backend.core.pitch.audio_utils import AudioDecodeError, AudioDependencyError, estimate_duration_from_bytes, infer_audio_metadata
from backend.core.pitch.pitch_comparison import build_pitch_comparison_payload, load_pitch_sequence_json
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.realtime_tuning import analyze_audio_frame
from backend.core.score.audio_pipeline import prepare_piano_score_from_audio
from backend.core.score.key_detection import analyze_key_signature
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.services import analysis_service
from backend.services.reference_track_service import (
    get_reference_track_by_ref_id,
    resolve_storage_url_path,
    search_reference_tracks as search_reference_tracks_data,
)
from backend.services.report_service import (
    ReportExportFileNotFoundError,
    ReportExportNotFoundError,
    export_report,
    get_report_export_file,
)
from backend.services.community_service import (
    save_user_avatar,
    get_score_pdf_content,
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
    get_score,
    get_score_export_file,
    get_score_export_record,
    list_score_exports,
    regenerate_score_export,
    redo_score,
    undo_score,
)
from backend.user.history_manager import delete_history, list_history, save_history
from backend.user.user_system import get_current_user, get_user_by_token, login_user, logout_user, register_user, get_preferences, update_preferences, update_user_info
from backend.utils.audio_logger import record_audio_log, record_audio_processing_log, get_audio_logs, read_audio_logs_from_file

# 引入节奏处理服务与项目配置项
from backend.services.analysis_service import (
    cache_analysis_result,
    evaluate_singing,
    get_analysis_result,
    get_saved_pitch_sequence,
    process_rhythm_scoring,
    save_analysis_result,
)
from backend.config.settings import settings


router = APIRouter(prefix="/api/v1", tags=["api"])
logger = logging.getLogger(__name__)

INLINE_PREVIEW_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
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
ASYNC_ANALYSIS_STATUS_PENDING = "pending"
ASYNC_ANALYSIS_STATUS_RUNNING = "running"
ASYNC_ANALYSIS_STATUS_COMPLETED = "completed"
ASYNC_ANALYSIS_STATUS_FAILED = "failed"
ASYNC_ANALYSIS_STAGE_QUEUED = "queued"
ASYNC_ANALYSIS_STAGE_SEPARATION = "separation"
ASYNC_ANALYSIS_STAGE_PITCH_DETECTION = "pitch_detection"
ASYNC_ANALYSIS_STAGE_SCORE_BUILD = "score_build"
ASYNC_ANALYSIS_STAGE_COMPLETED = "completed"
ASYNC_ANALYSIS_STAGE_FAILED = "failed"

def ok(data: Any, message: str = "success") -> Dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


@router.get("/health")
def api_health() -> Dict[str, str]:
    return {"status": "ok"}


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
        saved_sequence = get_saved_pitch_sequence(fallback_id, populate_cache=True)
        if saved_sequence:
            return saved_sequence
        if fallback_id.endswith("_reference"):
            saved_sequence = get_saved_pitch_sequence(fallback_id[: -len("_reference")], populate_cache=True)
            if saved_sequence:
                return saved_sequence
        if fallback_id.endswith("_user"):
            saved_sequence = get_saved_pitch_sequence(fallback_id[: -len("_user")], populate_cache=True)
            if saved_sequence:
                return saved_sequence
        raise HTTPException(status_code=404, detail=f"未找到分析 ID 对应的音高序列：{fallback_id}")
    raise HTTPException(status_code=400, detail="missing pitch source")


def _normalize_pitch_detect_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AudioDependencyError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AudioDecodeError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="音高检测服务发生未知错误。")


def _ensure_detected_pitch(sequence: list[dict[str, Any]]) -> None:
    has_pitch = any(float(item.get("frequency") or 0.0) > 0 and bool(item.get("voiced", True)) for item in sequence)
    if not has_pitch:
        raise HTTPException(status_code=400, detail="未检测到可用的音高，请上传更清晰的单音旋律音频。")


def _persist_analysis_result_non_blocking(
    background_tasks: BackgroundTasks | None,
    **payload: Any,
) -> None:
    cache_analysis_result(**payload)
    if not analysis_service.USE_DB:
        return
    if background_tasks is None:
        save_analysis_result(**payload)
        return
    background_tasks.add_task(analysis_service.save_analysis_result, **payload)


def _resolve_dizi_score_result(payload: DiziScoreRequest | DiziScoreExportRequest) -> dict[str, Any]:
    if payload.score_id:
        score = get_score(payload.score_id)
        return generate_dizi_score_from_musicxml(
            musicxml=score["musicxml"],
            key=str(score.get("key_signature") or payload.key or "C"),
            tempo=int(score.get("tempo") or payload.tempo or 120),
            time_signature=str(score.get("time_signature") or payload.time_signature or "4/4"),
            flute_type=payload.flute_type,
            style=payload.style,
            title=str(score.get("title") or payload.title or "Untitled Dizi Chart"),
        )

    melody = [dict(item) for item in payload.melody]
    key = str(payload.key or "C")
    tempo = int(payload.tempo or 120)
    time_signature = str(payload.time_signature or "4/4")
    title = str(payload.title or "Untitled Dizi Chart")
    style = str(payload.style or "traditional")
    flute_type = str(payload.flute_type or "G")

    if melody:
        return generate_dizi_score(
            key=key,
            tempo=tempo,
            time_signature=time_signature,
            flute_type=flute_type,
            style=style,
            melody=melody,
            title=title,
        )

    pitch_sequence = [item.model_dump() for item in payload.pitch_sequence]
    if not pitch_sequence and payload.analysis_id:
        pitch_sequence = get_saved_pitch_sequence(str(payload.analysis_id), populate_cache=True) or []
    if not pitch_sequence:
        raise HTTPException(status_code=400, detail="missing melody, score_id, or pitch source")

    return generate_dizi_score_from_pitch_sequence(
        pitch_sequence=pitch_sequence,
        tempo=tempo,
        time_signature=time_signature,
        flute_type=flute_type,
        key=payload.key,
        style=style,
        title=title,
    )


def _resolve_guitar_lead_sheet_result(payload: GuitarLeadSheetRequest | GuitarLeadSheetExportRequest) -> dict[str, Any]:
    if payload.score_id:
        score = get_score(payload.score_id)
        return generate_guitar_lead_sheet_from_musicxml(
            musicxml=score["musicxml"],
            key=str(score.get("key_signature") or payload.key or "C"),
            tempo=int(score.get("tempo") or payload.tempo or 120),
            time_signature=str(score.get("time_signature") or payload.time_signature or "4/4"),
            style=payload.style,
            title=str(score.get("title") or payload.title or "Untitled Guitar Lead Sheet"),
        )

    melody = [dict(item) for item in payload.melody]
    key = str(payload.key or "C")
    tempo = int(payload.tempo or 120)
    time_signature = str(payload.time_signature or "4/4")
    title = str(payload.title or "Untitled Guitar Lead Sheet")

    if melody:
        return generate_guitar_lead_sheet(
            key=key,
            tempo=tempo,
            style=payload.style,
            melody=melody,
            time_signature=time_signature,
            title=title,
        )

    pitch_sequence = [item.model_dump() for item in payload.pitch_sequence]
    if not pitch_sequence and payload.analysis_id:
        pitch_sequence = get_saved_pitch_sequence(str(payload.analysis_id), populate_cache=True) or []
    if not pitch_sequence:
        raise HTTPException(status_code=400, detail="missing melody, score_id, or pitch source")

    temporary_score = build_score_from_pitch_sequence(
        pitch_sequence,
        tempo=tempo,
        time_signature=time_signature,
        key_signature=payload.key,
        title=title,
        auto_detect_key=not bool((payload.key or "").strip()),
        arrangement_mode="melody",
    )
    return generate_guitar_lead_sheet_from_musicxml(
        musicxml=temporary_score["musicxml"],
        key=str(temporary_score.get("key_signature") or key),
        tempo=int(temporary_score.get("tempo") or tempo),
        time_signature=str(temporary_score.get("time_signature") or time_signature),
        style=payload.style,
        title=str(temporary_score.get("title") or title),
    )


def _resolve_guzheng_score_result(payload: GuzhengScoreRequest | GuzhengScoreExportRequest) -> dict[str, Any]:
    if payload.score_id:
        score = get_score(payload.score_id)
        return generate_guzheng_score_from_musicxml(
            musicxml=score["musicxml"],
            key=str(score.get("key_signature") or payload.key or "C"),
            tempo=int(score.get("tempo") or payload.tempo or 120),
            time_signature=str(score.get("time_signature") or payload.time_signature or "4/4"),
            style=payload.style,
            title=str(score.get("title") or payload.title or "Untitled Guzheng Chart"),
        )

    melody = [dict(item) for item in payload.melody]
    key = str(payload.key or "C")
    tempo = int(payload.tempo or 120)
    time_signature = str(payload.time_signature or "4/4")
    title = str(payload.title or "Untitled Guzheng Chart")
    style = str(payload.style or "traditional")

    if melody:
        return generate_guzheng_score(
            key=key,
            tempo=tempo,
            time_signature=time_signature,
            style=style,
            melody=melody,
            title=title,
        )

    pitch_sequence = [item.model_dump() for item in payload.pitch_sequence]
    if not pitch_sequence and payload.analysis_id:
        pitch_sequence = get_saved_pitch_sequence(str(payload.analysis_id), populate_cache=True) or []
    if not pitch_sequence:
        raise HTTPException(status_code=400, detail="missing melody, score_id, or pitch source")

    return generate_guzheng_score_from_pitch_sequence(
        pitch_sequence=pitch_sequence,
        tempo=tempo,
        time_signature=time_signature,
        key=payload.key,
        style=style,
        title=title,
    )


def _resolve_reference_audio_source(ref_id: str) -> tuple[str, dict[str, Any] | None]:
    normalized_ref_id = str(ref_id or "").strip()
    if not normalized_ref_id:
        raise HTTPException(status_code=400, detail="参考音频 ID 不能为空。")

    reference_track = get_reference_track_by_ref_id(normalized_ref_id)
    if reference_track is not None:
        try:
            resolved = resolve_storage_url_path(reference_track["audio_url"])
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not resolved.exists():
            raise HTTPException(
                status_code=404,
                detail=f"参考音频文件不存在：{reference_track['audio_url']}",
            )
        return str(resolved), reference_track

    fallback_path = os.path.join("assets", "references", f"{normalized_ref_id}.wav")
    if os.path.exists(fallback_path):
        return fallback_path, None

    raise HTTPException(
        status_code=404,
        detail=f"Reference audio with ID '{normalized_ref_id}' not found in MySQL or assets/references.",
    )


@router.post("/pitch/detect")
async def pitch_detect(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的音频文件为空。")
    logger.info(
        "Pitch detect started file=%s size=%sB algorithm=%s frame_ms=%s hop_ms=%s",
        file.filename or "audio",
        len(content),
        algorithm,
        frame_ms,
        hop_ms,
    )
    resolved_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(content, resolved_sample_rate)
    metadata = infer_audio_metadata(file.filename or "audio", resolved_sample_rate, estimated_duration or None)
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
    metadata["sample_rate"] = int(log_entry.get("sample_rate") or metadata["sample_rate"])
    metadata["duration"] = float(log_entry.get("duration") or metadata["duration"])
    try:
        pitches = detect_pitch_sequence(
            file_name=file.filename or "audio",
            sample_rate=metadata["sample_rate"],
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            duration=metadata["duration"],
            audio_bytes=content,
        )
    except Exception as exc:
        raise _normalize_pitch_detect_error(exc) from exc
    _ensure_detected_pitch(pitches)
    key_detection = analyze_key_signature(pitches)
    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        status=1,
        params={"frame_ms": frame_ms, "hop_ms": hop_ms, "algorithm": algorithm, "source": "pitch_detect"},
        result_data={"log_id": log_entry["log_id"], "key_detection": key_detection},
        pitch_sequence=pitches,
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
            "detected_key_signature": key_detection["key_signature"],
            "key_detection": key_detection,
            "pitch_sequence": pitches,
            "audio_log": log_entry,
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
    total_bytes = 0
    for index, upload in enumerate(files):
        content = await upload.read()
        if not content:
            continue
        track_name = upload.filename or f"track_{index + 1}"
        tracks.append({"name": track_name, "audio_bytes": content, "sample_rate": resolved_sample_rate})
        durations.append(estimate_duration_from_bytes(content, resolved_sample_rate))
        total_bytes += len(content)

    if not tracks:
        raise HTTPException(status_code=400, detail="uploaded tracks are empty")

    duration = max(durations) if durations else None
    metadata = infer_audio_metadata("multitrack", resolved_sample_rate, duration or None)
    log_entry = record_audio_processing_log(
        file_name="multitrack",
        audio_bytes=b"\x00" * total_bytes,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="pitch_detect_multitrack",
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "track_count": len(tracks),
            "tracks": [track["name"] for track in tracks],
        },
    )
    try:
        pitches = detect_pitch_sequence(
            file_name="multitrack",
            sample_rate=metadata["sample_rate"],
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            duration=metadata["duration"],
            audio_bytes={"sample_rate": metadata["sample_rate"], "tracks": tracks},
        )
    except Exception as exc:
        raise _normalize_pitch_detect_error(exc) from exc
    _ensure_detected_pitch(pitches)
    key_detection = analyze_key_signature(pitches)
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
            "detected_key_signature": key_detection["key_signature"],
            "key_detection": key_detection,
            "pitch_sequence": pitches,
            "audio_log": log_entry,
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
def score_from_pitch_sequence(payload: PitchToScoreRequest, authorization: str = Header(default="")):
    payload_data = payload.model_dump()
    try:
        return ok(create_score_from_pitch_sequence(payload_data))
    except UserNotFoundError as exc:
        current_user = optional_user_from_authorization(authorization)
        fallback_user_id = current_user.get("user_id") if current_user else None
        if (
            fallback_user_id is not None
            and str(fallback_user_id).isdigit()
            and int(fallback_user_id) != int(payload_data["user_id"])
        ):
            payload_data["user_id"] = int(fallback_user_id)
            try:
                return ok(create_score_from_pitch_sequence(payload_data))
            except UserNotFoundError:
                pass
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/score/from-audio")
async def score_from_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: int = Form(...),
    title: str = Form(""),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
    tempo: int = Form(120),
    time_signature: str = Form("4/4"),
    bpm_hint: Optional[int] = Form(None),
    beat_sensitivity: float = Form(0.5),
    separation_model: str = Form("demucs"),
    separation_stems: int = Form(2),
    arrangement_mode: str = Form("piano_solo"),
    authorization: str = Header(default=""),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的音频文件为空。")

    resolved_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(content, resolved_sample_rate)
    metadata = infer_audio_metadata(file.filename or "audio", resolved_sample_rate, estimated_duration or None)
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="score_from_audio",
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "bpm_hint": bpm_hint,
            "beat_sensitivity": beat_sensitivity,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
            "arrangement_mode": arrangement_mode,
        },
    )
    resolved_arrangement_mode = "piano_solo"
    try:
        pipeline_result = prepare_piano_score_from_audio(
            file_name=file.filename or "audio",
            audio_bytes=content,
            analysis_id=metadata["analysis_id"],
            fallback_tempo=int(tempo or 120),
            time_signature=time_signature,
            sample_rate=metadata["sample_rate"],
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            bpm_hint=bpm_hint,
            beat_sensitivity=beat_sensitivity,
            separation_model=separation_model,
            separation_stems=separation_stems,
        )
    except (AudioDecodeError, AudioDependencyError) as exc:
        raise _normalize_pitch_detect_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"钢琴智能识谱失败：{exc}") from exc

    score_payload = {
        "user_id": int(user_id),
        "title": title or None,
        "analysis_id": metadata["analysis_id"],
        "tempo": int(pipeline_result.get("tempo") or tempo or 120),
        "time_signature": time_signature,
        "key_signature": pipeline_result.get("detected_key_signature") or "C",
        "auto_detect_key": False,
        "arrangement_mode": resolved_arrangement_mode,
        "pitch_sequence": pipeline_result["pitch_sequence"],
    }
    try:
        score = create_score_from_pitch_sequence(score_payload)
    except UserNotFoundError as exc:
        current_user = optional_user_from_authorization(authorization)
        fallback_user_id = current_user.get("user_id") if current_user else None
        if (
            fallback_user_id is not None
            and str(fallback_user_id).isdigit()
            and int(fallback_user_id) != int(score_payload["user_id"])
        ):
            score_payload["user_id"] = int(fallback_user_id)
            try:
                score = create_score_from_pitch_sequence(score_payload)
            except UserNotFoundError:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        else:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        bpm=int(pipeline_result.get("tempo") or 0) or None,
        status=1,
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "time_signature": time_signature,
            "bpm_hint": bpm_hint,
            "beat_sensitivity": beat_sensitivity,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
            "arrangement_mode": resolved_arrangement_mode,
            "source": "score_from_audio",
        },
        result_data={
            "score_id": score["score_id"],
            "arrangement_mode": resolved_arrangement_mode,
            "score_mode": score.get("score_mode"),
            "beat_result": pipeline_result.get("beat_result"),
            "tempo_detection": pipeline_result.get("tempo_detection"),
            "key_detection": pipeline_result.get("key_detection"),
            "separation": pipeline_result.get("separation"),
            "melody_track": pipeline_result.get("melody_track"),
            "melody_track_candidates": pipeline_result.get("melody_track_candidates"),
            "log_id": log_entry["log_id"],
            "task_status": ASYNC_ANALYSIS_STATUS_COMPLETED,
            "task_stage": ASYNC_ANALYSIS_STAGE_COMPLETED,
        },
        pitch_sequence=pipeline_result["pitch_sequence"],
        user_id=int(user_id),
    )
    return ok(
        {
            **score,
            "analysis_id": metadata["analysis_id"],
            "pitch_sequence": pipeline_result["pitch_sequence"],
            "detected_key_signature": pipeline_result.get("detected_key_signature"),
            "key_detection": pipeline_result.get("key_detection"),
            "beat_result": pipeline_result.get("beat_result"),
            "tempo_detection": pipeline_result.get("tempo_detection"),
            "melody_track": pipeline_result.get("melody_track"),
            "melody_track_candidates": pipeline_result.get("melody_track_candidates"),
            "separation": pipeline_result.get("separation"),
            "warnings": pipeline_result.get("warnings"),
            "pipeline": pipeline_result.get("pipeline"),
            "piano_arrangement": score.get("piano_arrangement"),
            "audio_log": log_entry,
            "arrangement_mode": score.get("arrangement_mode") or resolved_arrangement_mode,
            "score_mode": score.get("score_mode") or "melody_transcription",
            "task_status": ASYNC_ANALYSIS_STATUS_COMPLETED,
            "task_stage": ASYNC_ANALYSIS_STAGE_COMPLETED,
        }
    )


@router.get("/analysis/{analysis_id}")
def analysis_detail(analysis_id: str):
    analysis_payload = get_analysis_result(analysis_id)
    if analysis_payload is None:
        raise HTTPException(status_code=404, detail=f"analysis {analysis_id} not found")

    result_data = deepcopy(analysis_payload.get("result_data") or {})
    pitch_sequence = list(analysis_payload.get("pitch_sequence") or [])
    if not pitch_sequence:
        pitch_sequence = get_saved_pitch_sequence(analysis_id, populate_cache=False) or []

    task_status = str(
        result_data.get("task_status")
        or (ASYNC_ANALYSIS_STATUS_COMPLETED if int(analysis_payload.get("status", 0) or 0) > 0 else ASYNC_ANALYSIS_STATUS_PENDING)
    )
    task_stage = str(
        result_data.get("task_stage")
        or (ASYNC_ANALYSIS_STAGE_COMPLETED if task_status == ASYNC_ANALYSIS_STATUS_COMPLETED else ASYNC_ANALYSIS_STAGE_QUEUED)
    )

    params = dict(analysis_payload.get("params") or {})
    params.pop("lyrics_mode", None)

    response_payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "task_status": task_status,
        "task_stage": task_stage,
        "status": int(analysis_payload.get("status", 0) or 0),
        "file_name": analysis_payload.get("file_name"),
        "sample_rate": analysis_payload.get("sample_rate"),
        "duration": analysis_payload.get("duration"),
        "bpm": analysis_payload.get("bpm"),
        "params": params,
        "error": result_data.get("error"),
        "warnings": result_data.get("warnings") or [],
    }

    score_id = str(result_data.get("score_id") or "").strip()
    if score_id:
        try:
            score = get_score(score_id)
            response_payload.update(score)
            response_payload.pop("lyrics_import", None)
            response_payload.pop("lyrics_mode", None)
        except ScoreNotFoundError:
            response_payload["score_id"] = score_id

    response_payload.update(
        {
            "score_id": response_payload.get("score_id") or score_id or None,
            "pitch_sequence": pitch_sequence,
            "detected_key_signature": result_data.get("detected_key_signature"),
            "key_detection": result_data.get("key_detection"),
            "beat_result": result_data.get("beat_result"),
            "tempo_detection": result_data.get("tempo_detection"),
            "melody_track": result_data.get("melody_track"),
            "melody_track_candidates": result_data.get("melody_track_candidates"),
            "separation": result_data.get("separation"),
            "pipeline": result_data.get("pipeline"),
            "piano_arrangement": response_payload.get("piano_arrangement") or result_data.get("piano_arrangement"),
            "arrangement_mode": response_payload.get("arrangement_mode") or result_data.get("arrangement_mode"),
            "score_mode": response_payload.get("score_mode") or result_data.get("score_mode"),
        }
    )
    return ok(response_payload)


@router.get("/scores/{score_id}")
def score_detail(score_id: str):
    try:
        return ok(get_score(score_id))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/scores/{score_id}")
def patch_score(score_id: str, payload: ScoreUpdateRequest):
    try:
        return ok(edit_score(score_id, payload.musicxml))
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    bpm_hint: Optional[int] = Form(None),
    sensitivity: float = Form(0.5),
):
    from backend.core.rhythm.beat_detection import detect_beats

    content = await file.read()
    metadata = infer_audio_metadata(file.filename or "audio")
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="rhythm_beat_detect",
        params={"bpm_hint": bpm_hint, "sensitivity": sensitivity},
    )
    result = detect_beats(file.filename or "audio", bpm_hint=bpm_hint, sensitivity=sensitivity, audio_bytes=content)
    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=log_entry.get("sample_rate"),
        duration=log_entry.get("duration"),
        bpm=int(result.get("bpm", 0) or 0) or None,
        status=1,
        params={"bpm_hint": bpm_hint, "sensitivity": sensitivity, "source": "rhythm_beat_detect"},
        result_data={"beat_result": result, "log_id": log_entry["log_id"]},
    )
    return ok({"analysis_id": metadata["analysis_id"], **result, "audio_log": log_entry})


@router.post("/audio/separate-tracks")
async def audio_separate_tracks(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    model: str = Form("demucs"),
    stems: int = Form(2),
):
    from backend.core.separation.multi_track_separation import separate_tracks

    content = await file.read()
    metadata = infer_audio_metadata(file.filename or "audio")
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="audio_separate_tracks",
        params={"model": model, "stems": stems},
    )
    result = separate_tracks(file.filename or "audio", model=model, stems=stems, audio_bytes=content)
    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=result.get("sample_rate") or log_entry.get("sample_rate"),
        duration=log_entry.get("duration"),
        status=1,
        params={"model": model, "stems": stems, "source": "audio_separate_tracks"},
        result_data={"separation": result, "log_id": log_entry["log_id"]},
    )
    return ok({"analysis_id": metadata["analysis_id"], **result, "audio_log": log_entry})


@router.post("/singing/evaluate")
async def singing_evaluate(
    user_audio: UploadFile = File(...),
    reference_audio: UploadFile | None = File(None),
    reference_ref_id: str | None = Form(None),
    user_audio_mode: str = Form("with_accompaniment"),
    language: str = Form("zh"),
    scoring_model: str = Form("balanced"),
    threshold_ms: float = Form(50.0),
    separation_model: str = Form("demucs"),
):
    normalized_ref_id = str(reference_ref_id or "").strip()
    has_reference_upload = reference_audio is not None
    has_reference_ref_id = bool(normalized_ref_id)
    if has_reference_upload == has_reference_ref_id:
        raise HTTPException(status_code=400, detail="reference_audio and reference_ref_id must be provided exactly one at a time")

    reference_track: dict[str, Any] | None = None
    resolved_ref_id: str | None = None
    if has_reference_ref_id:
        reference_path, reference_track = _resolve_reference_audio_source(normalized_ref_id)
        resolved_ref_id = reference_track["ref_id"] if reference_track else normalized_ref_id
        reference_file_name = os.path.basename(reference_path)
        try:
            with open(reference_path, "rb") as handle:
                reference_content = handle.read()
        except OSError as exc:
            raise HTTPException(status_code=404, detail=f"参考音频文件无法读取：{reference_path}") from exc
    else:
        assert reference_audio is not None
        reference_file_name = reference_audio.filename or "reference.wav"
        reference_content = await reference_audio.read()

    user_content = await user_audio.read()
    try:
        result = evaluate_singing(
            reference_file_name=reference_file_name,
            reference_audio_bytes=reference_content,
            user_file_name=user_audio.filename or "user.wav",
            user_audio_bytes=user_content,
            user_audio_mode=user_audio_mode,
            language=language,
            scoring_model=scoring_model,
            threshold_ms=threshold_ms,
            separation_model=separation_model,
            reference_ref_id=resolved_ref_id,
            reference_track=reference_track,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logging.error("Singing evaluation failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Singing evaluation failed: {exc}") from exc
    return ok(result)


@router.get("/audio/download/{file_name}")
def download_separated_audio(file_name: str):
    storage_dir = getattr(settings, "storage_dir", "temp")
    safe_name = os.path.basename(file_name)
    file_path = os.path.join(storage_dir, "separated_tracks", safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="separated audio file not found")
    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="audio/wav",
        content_disposition_type="attachment",
    )


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
    background_tasks: BackgroundTasks,
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
    - ref_id: Reference audio ID (resolved from MySQL `reference_track` first, legacy fallback to assets/references)
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
    metadata = infer_audio_metadata(user_audio.filename or "audio")

    try:
        # Save uploaded file
        content = await user_audio.read()
        with open(temp_user_path, "wb") as f:
            f.write(content)
        log_entry = record_audio_processing_log(
            file_name=user_audio.filename or "audio",
            audio_bytes=content,
            analysis_id=metadata["analysis_id"],
            source="api",
            stage="analyze_rhythm_upload",
            params={"ref_id": ref_id, "language": language, "scoring_model": scoring_model, "threshold_ms": threshold_ms},
        )
        
        ref_audio_path, reference_track = _resolve_reference_audio_source(ref_id)
        
        # Call service layer core logic with language and scoring model support
        report = await process_rhythm_scoring(
            temp_user_path,
            ref_audio_path,
            language=language,
            scoring_model=scoring_model,
            threshold_ms=threshold_ms,
        )
        _persist_analysis_result_non_blocking(
            background_tasks,
            analysis_id=metadata["analysis_id"],
            file_name=user_audio.filename or "audio",
            sample_rate=log_entry.get("sample_rate"),
            duration=report.get("user_duration") or log_entry.get("duration"),
            bpm=int(report.get("user_bpm", 0) or 0) or None,
            status=1,
            params={"ref_id": ref_id, "language": language, "scoring_model": scoring_model, "threshold_ms": threshold_ms},
            result_data={
                "rhythm_report": report,
                "log_id": log_entry["log_id"],
                "reference_track": reference_track,
            },
        )

        return ok(
            {
                "analysis_id": metadata["analysis_id"],
                "resolved_ref_id": reference_track["ref_id"] if reference_track else ref_id,
                "reference_track": reference_track,
                **report,
                "audio_log": log_entry,
            }
        )

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


@router.get("/reference-tracks/search")
def reference_track_search(keyword: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)):
    return ok({"items": search_reference_tracks_data(keyword, limit=limit)})


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


@router.get("/community/scores/{score_id}/cover")
def get_community_score_cover_api(score_id: str):
    from backend.services.community_service import get_community_score_cover
    try:
        image_bytes, content_type = get_community_score_cover(score_id)
        return Response(content=image_bytes, media_type=content_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    # file_content_base64: str = Form(...), 
    cover_file: UploadFile | None = File(default=None),
    title: str = Form(...),
    style: str = Form("精选"),
    instrument: str = Form("乐谱"),
    price: float = Form(0.0),
    description: str = Form(""),
    tags: str = Form(""),
    authorization: str = Header(default=""),
):
    import asyncio
    import functools
    # Concurrently read file + cover, then encode in thread pool
    reads = [file.read()]
    if cover_file is not None:
        reads.append(cover_file.read())
    read_results = await asyncio.gather(*reads)
    content = read_results[0]
    cover_content = read_results[1] if cover_file is not None else None

    if not content:
        raise HTTPException(status_code=400, detail="empty upload file")
    if len(content) > COMMUNITY_SCORE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="file exceeds 20MB limit")
    if cover_content is not None:
        if not cover_content:
            raise HTTPException(status_code=400, detail="empty cover file")
        if len(cover_content) > COMMUNITY_COVER_MAX_BYTES:
            raise HTTPException(status_code=400, detail="cover image exceeds 5MB limit")
        _resolve_cover_suffix(cover_file)

    # Offload CPU-heavy base64 encode to thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    base64_string = await loop.run_in_executor(
        None, functools.partial(base64.b64encode, content)
    )
    base64_string = base64_string.decode('utf-8')

    cover_url = None
    current_user = optional_user_from_authorization(authorization)
    payload = {
        "title": title,
        "file_content_base64":base64_string,
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
        register_score_download(score_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    pdf_bytes, filename = get_score_pdf_content(score_id)

    encoded_filename = quote(filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


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


@router.get("/logs/audio")
def get_logs(
    analysis_id: str | None = Query(None),
    stage: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    persist: bool = Query(False),
):
    """Retrieve audio processing logs (采样率、时长、格式等调试数据).
    
    Query parameters:
    - analysis_id: Filter by specific analysis ID
    - stage: Filter by processing stage (e.g., 'pitch_detect', 'rhythm_beat_detect', 'analyze_audio')
    - limit: Maximum number of logs to return (default: 100, max: 1000)
    - persist: If true, read from disk file instead of in-memory cache
    
    Returns:
    - List of audio logs, each containing:
        - log_id: Unique log identifier
        - file_name: Processed audio file name
        - sample_rate: Audio sample rate (Hz)
        - duration: Audio duration (seconds)
        - channels: Number of audio channels
        - frame_count: Total audio frames
        - byte_size: Raw audio byte size
        - audio_format: Format (wav, mp3, etc.)
        - file_extension: File extension
        - subtype: Audio subtype (PCM16, etc.)
        - source: Source of the log (api, service, system)
        - stage: Processing stage
        - analysis_id: Associated analysis ID
        - created_at: UTC timestamp
        - params: Additional processing parameters
    """
    if persist:
        logs = read_audio_logs_from_file(limit=limit)
    else:
        logs = get_audio_logs(analysis_id=analysis_id, stage=stage, limit=limit)
    return ok({"total": len(logs), "logs": logs})


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
    return ok(generate_chord_sequence(payload.key, payload.tempo, payload.style, payload.melody, payload.time_signature))


@router.post("/generation/dizi-score-from-audio")
async def generation_dizi_score_from_audio_api(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
    title: str = Form("Untitled Dizi Chart"),
    key: str = Form(""),
    tempo: int = Form(120),
    time_signature: str = Form("4/4"),
    style: str = Form("traditional"),
    flute_type: str = Form("G"),
    bpm_hint: Optional[int] = Form(None),
    beat_sensitivity: float = Form(0.5),
    separation_model: str = Form("demucs"),
    separation_stems: int = Form(2),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的音频文件为空。")

    resolved_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(content, resolved_sample_rate)
    metadata = infer_audio_metadata(file.filename or "audio", resolved_sample_rate, estimated_duration or None)
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="dizi_score_audio",
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "style": style,
            "key": key,
            "flute_type": flute_type,
            "bpm_hint": bpm_hint,
            "beat_sensitivity": beat_sensitivity,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
        },
    )
    try:
        result = generate_dizi_score_from_audio(
            file_name=file.filename or "audio",
            audio_bytes=content,
            analysis_id=metadata["analysis_id"],
            title=title,
            key=key,
            tempo=tempo,
            time_signature=time_signature,
            style=style,
            flute_type=flute_type,
            sample_rate=metadata["sample_rate"],
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            bpm_hint=bpm_hint,
            beat_sensitivity=beat_sensitivity,
            separation_model=separation_model,
            separation_stems=separation_stems,
        )
    except (AudioDecodeError, AudioDependencyError) as exc:
        raise _normalize_pitch_detect_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"笛子谱生成失败：{exc}") from exc

    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        bpm=int(result.get("tempo") or 0) or None,
        status=1,
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "style": style,
            "key": key,
            "flute_type": flute_type,
            "bpm_hint": bpm_hint,
            "beat_sensitivity": beat_sensitivity,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
            "source": "dizi_score_audio",
        },
        result_data={
            "log_id": log_entry["log_id"],
            "key_detection": result.get("key_detection"),
            "tempo_detection": result.get("tempo_detection"),
            "separation": result.get("separation"),
            "melody_track": result.get("melody_track"),
            "warnings": result.get("warnings") or [],
            "lead_sheet_type": result.get("lead_sheet_type"),
            "flute_type": result.get("flute_type"),
        },
        pitch_sequence=result.get("pitch_sequence") or [],
    )
    return ok({**result, "audio_log": log_entry})


@router.post("/generation/dizi-score")
def generation_dizi_score_api(payload: DiziScoreRequest):
    try:
        return ok(_resolve_dizi_score_result(payload))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generation/dizi-score/export")
def generation_dizi_score_export_api(payload: DiziScoreExportRequest):
    try:
        result = _resolve_dizi_score_result(payload)
        export_payload = export_traditional_score(
            result,
            instrument_type="dizi",
            export_format=payload.format,
            storage_dir=settings.storage_dir,
            file_stem=(
                f"dizi_{result.get('title') or 'jianpu'}_"
                f"{payload.flute_type}_{payload.layout_mode}_{payload.annotation_layer}_{payload.format}"
            ),
            layout_mode=payload.layout_mode,
            annotation_layer=payload.annotation_layer,
        )
        return ok(export_payload)
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TraditionalExportDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (TraditionalExportCompileError, TraditionalExportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generation/guzheng-score-from-audio")
async def generation_guzheng_score_from_audio_api(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
    title: str = Form("Untitled Guzheng Chart"),
    key: str = Form(""),
    tempo: int = Form(120),
    time_signature: str = Form("4/4"),
    style: str = Form("traditional"),
    bpm_hint: Optional[int] = Form(None),
    beat_sensitivity: float = Form(0.5),
    separation_model: str = Form("demucs"),
    separation_stems: int = Form(2),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的音频文件为空。")

    resolved_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(content, resolved_sample_rate)
    metadata = infer_audio_metadata(file.filename or "audio", resolved_sample_rate, estimated_duration or None)
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="guzheng_score_audio",
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "style": style,
            "key": key,
            "bpm_hint": bpm_hint,
            "beat_sensitivity": beat_sensitivity,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
        },
    )
    try:
        result = generate_guzheng_score_from_audio(
            file_name=file.filename or "audio",
            audio_bytes=content,
            analysis_id=metadata["analysis_id"],
            title=title,
            key=key,
            tempo=tempo,
            time_signature=time_signature,
            style=style,
            sample_rate=metadata["sample_rate"],
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            bpm_hint=bpm_hint,
            beat_sensitivity=beat_sensitivity,
            separation_model=separation_model,
            separation_stems=separation_stems,
        )
    except (AudioDecodeError, AudioDependencyError) as exc:
        raise _normalize_pitch_detect_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"古筝谱生成失败：{exc}") from exc

    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        bpm=int(result.get("tempo") or 0) or None,
        status=1,
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "style": style,
            "key": key,
            "bpm_hint": bpm_hint,
            "beat_sensitivity": beat_sensitivity,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
            "source": "guzheng_score_audio",
        },
        result_data={
            "log_id": log_entry["log_id"],
            "key_detection": result.get("key_detection"),
            "tempo_detection": result.get("tempo_detection"),
            "separation": result.get("separation"),
            "melody_track": result.get("melody_track"),
            "warnings": result.get("warnings") or [],
            "lead_sheet_type": result.get("lead_sheet_type"),
        },
        pitch_sequence=result.get("pitch_sequence") or [],
    )
    return ok({**result, "audio_log": log_entry})


@router.post("/generation/guzheng-score")
def generation_guzheng_score_api(payload: GuzhengScoreRequest):
    try:
        return ok(_resolve_guzheng_score_result(payload))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generation/guzheng-score/export")
def generation_guzheng_score_export_api(payload: GuzhengScoreExportRequest):
    try:
        result = _resolve_guzheng_score_result(payload)
        export_payload = export_traditional_score(
            result,
            instrument_type="guzheng",
            export_format=payload.format,
            storage_dir=settings.storage_dir,
            file_stem=(
                f"guzheng_{result.get('title') or 'jianpu'}_"
                f"{payload.layout_mode}_{payload.annotation_layer}_{payload.format}"
            ),
            layout_mode=payload.layout_mode,
            annotation_layer=payload.annotation_layer,
        )
        return ok(export_payload)
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TraditionalExportDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (TraditionalExportCompileError, TraditionalExportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generation/guitar-lead-sheet-from-audio")
async def generation_guitar_lead_sheet_from_audio_api(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sample_rate: Optional[int] = Form(None),
    frame_ms: int = Form(20),
    hop_ms: int = Form(10),
    algorithm: str = Form("yin"),
    title: str = Form("Untitled Guitar Lead Sheet"),
    key: str = Form(""),
    tempo: int = Form(120),
    time_signature: str = Form("4/4"),
    style: str = Form("pop"),
    separation_model: str = Form("demucs"),
    separation_stems: int = Form(2),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的音频文件为空。")

    resolved_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(content, resolved_sample_rate)
    metadata = infer_audio_metadata(file.filename or "audio", resolved_sample_rate, estimated_duration or None)
    log_entry = record_audio_processing_log(
        file_name=file.filename or "audio",
        audio_bytes=content,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="guitar_lead_sheet_audio",
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "style": style,
            "key": key,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
        },
    )

    try:
        result = generate_guitar_lead_sheet_from_audio(
            file_name=file.filename or "audio",
            audio_bytes=content,
            analysis_id=metadata["analysis_id"],
            title=title,
            key=key,
            tempo=tempo,
            time_signature=time_signature,
            style=style,
            sample_rate=metadata["sample_rate"],
            frame_ms=frame_ms,
            hop_ms=hop_ms,
            algorithm=algorithm,
            separation_model=separation_model,
            separation_stems=separation_stems,
        )
    except (AudioDecodeError, AudioDependencyError) as exc:
        raise _normalize_pitch_detect_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"吉他弹唱谱生成失败：{exc}") from exc

    result = dict(result)
    result.pop("lyrics_import", None)
    result.pop("lyrics_mode", None)
    result.pop("lyrics_language", None)

    _persist_analysis_result_non_blocking(
        background_tasks,
        analysis_id=metadata["analysis_id"],
        file_name=file.filename or "audio",
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        status=1,
        params={
            "frame_ms": frame_ms,
            "hop_ms": hop_ms,
            "algorithm": algorithm,
            "tempo": tempo,
            "time_signature": time_signature,
            "style": style,
            "key": key,
            "separation_model": separation_model,
            "separation_stems": separation_stems,
            "source": "guitar_lead_sheet_audio",
        },
        result_data={
            "log_id": log_entry["log_id"],
            "key_detection": result.get("key_detection"),
            "separation": result.get("separation"),
            "melody_track": result.get("melody_track"),
            "warnings": result.get("warnings") or [],
        },
        pitch_sequence=result.get("pitch_sequence") or [],
    )
    return ok({**result, "audio_log": log_entry})


@router.post("/generation/guitar-lead-sheet")
def generation_guitar_lead_sheet(payload: GuitarLeadSheetRequest):
    try:
        return ok(_resolve_guitar_lead_sheet_result(payload))
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generation/guitar-lead-sheet/export")
def generation_guitar_lead_sheet_export(payload: GuitarLeadSheetExportRequest):
    try:
        result = _resolve_guitar_lead_sheet_result(payload)
        export_payload = export_guitar_lead_sheet_pdf(
            result,
            storage_dir=settings.storage_dir,
            file_stem=(
                f"guitar_{result.get('title') or 'lead_sheet'}_"
                f"{payload.layout_mode}_{payload.format}"
            ),
            layout_mode=payload.layout_mode,
        )
        return ok(export_payload)
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GuitarExportDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GuitarExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generation/variation-suggestions")
def generation_variations(payload: VariationSuggestionRequest):
    return ok(generate_variation_suggestions(payload.score_id, payload.style, payload.difficulty))


@router.post("/generation/transpose-suggestions")
def generation_transpose_suggestions(payload: TransposeSuggestionRequest):
    try:
        return ok(
            generate_transpose_suggestions(
                analysis_id=payload.analysis_id,
                current_key=payload.current_key,
                source_gender=payload.source_gender,
                target_gender=payload.target_gender,
                pitch_sequence=[item.model_dump() for item in payload.pitch_sequence],
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/register")
def auth_register(payload: RegisterRequest):
    return ok(register_user(payload.username, payload.password, payload.email))


@router.post("/auth/login")
def auth_login(payload: LoginRequest):
    return ok(login_user(payload.username, payload.password))


@router.post("/auth/logout")
def auth_logout(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing token")
    return ok(logout_user(token))


@router.get("/users/me")
def me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(current_user)


@router.patch("/users/me")
def update_me(payload: UserUpdatePayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    """更新个人资料接口"""
    # 提取有值的字段
    updates = payload.model_dump(exclude_unset=True)
    result = update_user_info(current_user["user_id"], updates)
    return ok(result)


# @router.post("/users/me/avatar")
# async def upload_avatar(file: UploadFile = File(...), current_user: Dict[str, Any] = Depends(get_current_user)):
#     """上传并更新个人头像"""
#     # 验证类型
#     ext = Path(file.filename).suffix.lower()
#     if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
#         raise HTTPException(status_code=400, detail="仅支持 jpg, png, webp 格式的图片")
    
#     # 生成唯一文件名
#     filename = f"avatar_{current_user['user_id']}_{uuid.uuid4().hex[:8]}{ext}"
#     save_path = Path("storage/avatars") / filename
    
#     try:
#         # 保存文件
#         content = await file.read()
#         with open(save_path, "wb") as f:
#             f.write(content)
        
#         # 更新数据库中的头像路径 (假设前端可以通过 /api/v1/users/me/avatar/filename 访问，这里暂存相对路径)
#         avatar_url = f"/api/v1/users/me/avatar/{filename}"
#         update_user_info(current_user["user_id"], {"avatar": avatar_url})
        
#         return ok({"avatar_url": avatar_url})
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")


# @router.get("/users/me/avatar/{filename}")
# def get_avatar(filename: str):
#     """读取头像文件流"""
#     path = Path("storage/avatars") / filename
#     if not path.exists():
#         raise HTTPException(status_code=404, detail="图片不存在")
#     return FileResponse(path)


@router.get("/users/me/history")
def get_history(current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(list_history(current_user["user_id"]))


@router.post("/users/me/history")
def post_history(payload: HistoryCreateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(save_history(current_user["user_id"], payload.model_dump()))


@router.delete("/users/me/history/{history_id}")
def remove_history(history_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(delete_history(current_user["user_id"], history_id))


@router.get("/users/me/preferences")
def get_user_preferences(current_user: Dict[str, Any] = Depends(get_current_user)):
    return ok(get_preferences(current_user["user_id"]))


@router.put("/users/me/preferences")
def update_user_preferences(payload: PreferencesUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    return ok(update_preferences(current_user["user_id"], updates))


@router.post("/reports/export")
def reports_export(payload: ReportExportRequest):
    return ok(export_report(payload.model_dump()))


@router.get("/reports/{report_id}/files/{file_name}/download")
def report_file_download(report_id: str, file_name: str):
    try:
        export_data = get_report_export_file(report_id, file_name)
    except ReportExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportExportFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=export_data["file_path"],
        filename=export_data["file_name"],
        media_type=export_data["content_type"],
        content_disposition_type="attachment",
    )

@router.post("/users/avatar")
async def update_avatar(
    file: UploadFile = File(...),
    authorization: str = Header(...)
):
    token = authorization.removeprefix("Bearer ").strip()
    user_info = get_user_by_token(token) 
    
    content = await file.read()
    
    avatar_url = save_user_avatar(user_info["user_id"], content, file.filename)
    
    return {"code": 0, "message": "success", "data": {"avatar_url": avatar_url}}
