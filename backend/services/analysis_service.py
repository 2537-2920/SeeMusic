"""End-to-end audio analysis orchestration and persistence helpers."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import importlib
import logging
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.core.pitch.audio_utils import infer_audio_metadata, estimate_duration_from_bytes
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.pitch.pitch_sequence_utils import (
    DEFAULT_HOP_MS,
    compress_pitch_sequence_to_note_events,
    expand_note_events_to_pitch_sequence,
    extract_note_events_from_result,
    is_note_event_sequence,
)
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.utils.audio_logger import record_audio_processing_log
from backend.utils.data_visualizer import build_pitch_curve


logger = logging.getLogger(__name__)
PITCH_SEQUENCE_FORMAT_NOTE_EVENTS = "note_events"
# 开启数据库持久化模式
USE_DB: bool = True
_session_factory = None
ANALYSIS_RESULTS: dict[str, dict[str, Any]] = {}


def _load_soundfile():
    try:
        return importlib.import_module("soundfile")
    except ModuleNotFoundError as exc:
        raise RuntimeError("环境缺少 soundfile，无法读取节奏评分所需的音频文件。") from exc


def set_db_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


@contextmanager
def _session_scope() -> Iterator[Any]:
    if _session_factory is None:
        raise RuntimeError("DB mode enabled but no session factory configured")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_analysis_results() -> None:
    ANALYSIS_RESULTS.clear()


def _store_analysis_result_in_memory(payload: dict[str, Any]) -> None:
    ANALYSIS_RESULTS[payload["analysis_id"]] = deepcopy(payload)


def _get_cached_pitch_sequence(
    analysis_id: str,
    *,
    is_reference: bool | None = None,
) -> list[dict[str, Any]] | None:
    stored = ANALYSIS_RESULTS.get(analysis_id)
    if stored is None:
        return None
    sequence = list(stored.get("pitch_sequence") or [])
    if is_reference is None:
        return deepcopy(sequence)
    if bool(stored.get("is_reference")) == is_reference:
        return deepcopy(sequence)
    return None


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_ready(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return str(value)


def _pitch_meta_from_params(
    params: dict[str, Any] | None,
    *,
    sample_rate: int | None,
    original_point_count: int,
    is_reference: bool,
) -> dict[str, Any]:
    pitch_params = params or {}
    return {
        "frame_ms": int(pitch_params.get("frame_ms") or 20),
        "hop_ms": int(pitch_params.get("hop_ms") or DEFAULT_HOP_MS),
        "algorithm": str(pitch_params.get("algorithm") or "yin"),
        "sample_rate": sample_rate,
        "original_point_count": int(original_point_count),
        "is_reference": bool(is_reference),
    }


def _merge_result_payload(
    *,
    existing_result: dict[str, Any] | None,
    result_data: dict[str, Any] | None,
    pitch_sequence: list[dict[str, Any]] | None,
    params: dict[str, Any] | None,
    sample_rate: int | None,
    is_reference: bool,
) -> dict[str, Any]:
    merged: dict[str, Any] = _json_ready(deepcopy(existing_result or {}))
    merged.update(_json_ready(deepcopy(result_data or {})))

    if pitch_sequence is None:
        return merged

    if is_note_event_sequence(pitch_sequence):
        note_events = _json_ready(deepcopy(pitch_sequence))
        original_point_count = len(pitch_sequence)
    else:
        note_events = compress_pitch_sequence_to_note_events(
            _json_ready(deepcopy(pitch_sequence)),
            hop_ms=int((params or {}).get("hop_ms") or DEFAULT_HOP_MS),
        )
        original_point_count = len(pitch_sequence)

    merged.update(
        {
            "pitch_sequence_format": PITCH_SEQUENCE_FORMAT_NOTE_EVENTS,
            "pitch_sequence": note_events,
            "pitch_meta": _json_ready(
                _pitch_meta_from_params(
                    params,
                    sample_rate=sample_rate,
                    original_point_count=original_point_count,
                    is_reference=is_reference,
                )
            ),
        }
    )
    return merged


def _serialize_pitch_sequence_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "time": float(row.time),
            "frequency": float(row.frequency) if row.frequency is not None else None,
            "note": row.note,
            "confidence": float(row.confidence) if row.confidence is not None else None,
            "cents_offset": float(row.cents_offset) if row.cents_offset is not None else None,
        }
        for row in rows
    ]


def _replace_pitch_sequence_rows(
    session: Any,
    *,
    analysis_id: str,
    pitch_sequence: list[dict[str, Any]],
    is_reference: bool,
) -> None:
    from backend.db.models import PitchSequence

    session.query(PitchSequence).filter_by(analysis_id=analysis_id, is_reference=is_reference).delete()
    for item in pitch_sequence:
        session.add(
            PitchSequence(
                analysis_id=analysis_id,
                time=float(item.get("time", 0.0)),
                frequency=float(item["frequency"]) if item.get("frequency") is not None else None,
                note=item.get("note"),
                confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
                cents_offset=float(item["cents_offset"]) if item.get("cents_offset") is not None else None,
                is_reference=is_reference,
            )
        )


def _load_note_events_from_analysis(
    session: Any,
    *,
    analysis_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from backend.db.models import AudioAnalysis

    analysis = session.execute(
        select(AudioAnalysis).where(AudioAnalysis.analysis_id == analysis_id)
    ).scalar_one_or_none()
    if analysis is None:
        return [], {}
    return extract_note_events_from_result(analysis.result)


def _build_analysis_payload(
    *,
    analysis_id: str,
    file_name: str | None = None,
    file_url: str | None = None,
    sample_rate: int | None = None,
    duration: float | None = None,
    bpm: int | None = None,
    status: int = 1,
    params: dict[str, Any] | None = None,
    result_data: dict[str, Any] | None = None,
    pitch_sequence: list[dict[str, Any]] | None = None,
    user_id: int | None = None,
    is_reference: bool = False,
) -> dict[str, Any]:
    return {
        "analysis_id": analysis_id,
        "file_name": file_name,
        "file_url": file_url,
        "sample_rate": sample_rate,
        "duration": duration,
        "bpm": bpm,
        "status": status,
        "params": _json_ready(deepcopy(params or {})),
        "result_data": _json_ready(deepcopy(result_data or {})),
        "pitch_sequence": _json_ready(deepcopy(pitch_sequence or [])),
        "user_id": user_id,
        "is_reference": is_reference,
    }


def cache_analysis_result(
    *,
    analysis_id: str,
    file_name: str | None = None,
    file_url: str | None = None,
    sample_rate: int | None = None,
    duration: float | None = None,
    bpm: int | None = None,
    status: int = 1,
    params: dict[str, Any] | None = None,
    result_data: dict[str, Any] | None = None,
    pitch_sequence: list[dict[str, Any]] | None = None,
    user_id: int | None = None,
    is_reference: bool = False,
) -> None:
    _store_analysis_result_in_memory(
        _build_analysis_payload(
            analysis_id=analysis_id,
            file_name=file_name,
            file_url=file_url,
            sample_rate=sample_rate,
            duration=duration,
            bpm=bpm,
            status=status,
            params=params,
            result_data=result_data,
            pitch_sequence=pitch_sequence,
            user_id=user_id,
            is_reference=is_reference,
        )
    )


def save_analysis_result(
    *,
    analysis_id: str,
    file_name: str | None = None,
    file_url: str | None = None,
    sample_rate: int | None = None,
    duration: float | None = None,
    bpm: int | None = None,
    status: int = 1,
    params: dict[str, Any] | None = None,
    result_data: dict[str, Any] | None = None,
    pitch_sequence: list[dict[str, Any]] | None = None,
    user_id: int | None = None,
    is_reference: bool = False,
) -> None:
    payload = _build_analysis_payload(
        analysis_id=analysis_id,
        file_name=file_name,
        file_url=file_url,
        sample_rate=sample_rate,
        duration=duration,
        bpm=bpm,
        status=status,
        params=params,
        result_data=result_data,
        pitch_sequence=pitch_sequence,
        user_id=user_id,
        is_reference=is_reference,
    )
    _store_analysis_result_in_memory(payload)
    if not USE_DB:
        return

    from backend.db.models import AudioAnalysis

    try:
        with _session_scope() as session:
            analysis = session.execute(
                select(AudioAnalysis).where(AudioAnalysis.analysis_id == analysis_id)
            ).scalar_one_or_none()
            persisted_result = _merge_result_payload(
                existing_result=analysis.result if analysis is not None else None,
                result_data=result_data,
                pitch_sequence=payload["pitch_sequence"] if pitch_sequence is not None else None,
                params=params,
                sample_rate=sample_rate,
                is_reference=is_reference,
            )
            if analysis is None:
                analysis = AudioAnalysis(
                    user_id=user_id,
                    analysis_id=analysis_id,
                    file_name=file_name,
                    file_url=file_url,
                    sample_rate=sample_rate,
                    duration=duration,
                    bpm=bpm,
                    status=status,
                    params=_json_ready(deepcopy(params or {})),
                    result=persisted_result,
                )
                session.add(analysis)
                session.flush()
            else:
                analysis.user_id = user_id if user_id is not None else analysis.user_id
                analysis.file_name = file_name or analysis.file_name
                analysis.file_url = file_url or analysis.file_url
                analysis.sample_rate = sample_rate if sample_rate is not None else analysis.sample_rate
                analysis.duration = duration if duration is not None else analysis.duration
                analysis.bpm = bpm if bpm is not None else analysis.bpm
                analysis.status = status
                analysis.params = _json_ready(deepcopy(params or analysis.params or {}))
                analysis.result = persisted_result
                session.add(analysis)
                session.flush()
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to persist analysis result %s to DB; using in-memory fallback instead: %s",
            analysis_id,
            exc,
        )
        _store_analysis_result_in_memory(payload)


def save_pitch_sequence_cache(
    analysis_id: str,
    pitch_sequence: list[dict[str, Any]],
    *,
    is_reference: bool = False,
) -> None:
    if not USE_DB or not pitch_sequence:
        return
    try:
        with _session_scope() as session:
            _replace_pitch_sequence_rows(
                session,
                analysis_id=analysis_id,
                pitch_sequence=pitch_sequence,
                is_reference=is_reference,
            )
    except SQLAlchemyError as exc:
        logger.warning("Failed to persist pitch_sequence cache for %s: %s", analysis_id, exc)


def get_saved_pitch_sequence(
    analysis_id: str,
    *,
    is_reference: bool | None = None,
    populate_cache: bool = False,
) -> list[dict[str, Any]] | None:
    cached_sequence = _get_cached_pitch_sequence(analysis_id, is_reference=is_reference)
    if cached_sequence:
        if populate_cache and USE_DB:
            save_pitch_sequence_cache(
                analysis_id,
                cached_sequence,
                is_reference=bool(is_reference),
            )
        return cached_sequence
    if not USE_DB:
        return None

    from backend.db.models import PitchSequence

    try:
        with _session_scope() as session:
            statement = select(PitchSequence).where(PitchSequence.analysis_id == analysis_id).order_by(PitchSequence.time.asc())
            if is_reference is not None:
                statement = statement.where(PitchSequence.is_reference == is_reference)
            rows = list(session.execute(statement).scalars())
            if rows:
                return _serialize_pitch_sequence_rows(rows)

            note_events, pitch_meta = _load_note_events_from_analysis(session, analysis_id=analysis_id)
            if not note_events:
                return None
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to load pitch sequence %s from DB; using in-memory fallback if available: %s",
            analysis_id,
            exc,
        )
        return _get_cached_pitch_sequence(analysis_id, is_reference=is_reference)

    expanded_sequence = expand_note_events_to_pitch_sequence(
        note_events,
        hop_ms=int((pitch_meta or {}).get("hop_ms") or DEFAULT_HOP_MS),
    )
    if is_reference is not None and bool((pitch_meta or {}).get("is_reference", False)) != is_reference:
        return None
    if populate_cache and expanded_sequence:
        save_pitch_sequence_cache(
            analysis_id,
            expanded_sequence,
            is_reference=bool((pitch_meta or {}).get("is_reference", False)),
        )
    return expanded_sequence or None


def analyze_audio(file_name: str, audio_bytes: bytes, sample_rate: int | None = None) -> dict[str, Any]:
    from backend.core.rhythm.beat_detection import detect_beats

    inferred_sample_rate = sample_rate or 16000
    estimated_duration = estimate_duration_from_bytes(audio_bytes, sample_rate=inferred_sample_rate)
    metadata = infer_audio_metadata(file_name, sample_rate=inferred_sample_rate, duration=estimated_duration)
    pitch_sequence = detect_pitch_sequence(
        file_name=file_name,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        audio_bytes=audio_bytes,
    )
    beat_result = detect_beats(file_name, audio_bytes=audio_bytes)
    score = build_score_from_pitch_sequence(pitch_sequence, auto_detect_key=True, arrangement_mode="piano_solo")
    pitch_curve = build_pitch_curve(pitch_sequence, pitch_sequence)
    log_entry = record_audio_processing_log(
        file_name=file_name,
        audio_bytes=audio_bytes,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        analysis_id=metadata["analysis_id"],
        source="service",
        stage="analyze_audio",
        params={"pipeline": "analyze_audio"},
    )
    save_analysis_result(
        analysis_id=metadata["analysis_id"],
        file_name=file_name,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        bpm=int(beat_result.get("bpm", 0) or 0) or None,
        status=1,
        params={"pipeline": "analyze_audio"},
        result_data={"beat_result": beat_result, "score_id": score["score_id"], "log_id": log_entry["log_id"]},
        pitch_sequence=pitch_sequence,
    )
    return {
        "analysis_id": metadata["analysis_id"],
        "pitch_sequence": pitch_sequence,
        "beat_result": beat_result,
        "score": score,
        "pitch_curve": pitch_curve,
        "log": log_entry,
    }


async def process_rhythm_scoring(
    user_audio_path: str,
    ref_audio_path: str,
    language: str = "en",
    scoring_model: str = "balanced",
    threshold_ms: float = 50.0,
) -> dict[str, Any]:
    from backend.core.rhythm.beat_detection import AdvancedBeatDetector
    from backend.core.rhythm.i18n import FeedbackFormatter
    from backend.core.rhythm.rhythm_analysis import AdvancedRhythmAnalyzer

    beat_detector = AdvancedBeatDetector()
    rhythm_analyzer = AdvancedRhythmAnalyzer(threshold_ms=threshold_ms)
    soundfile = _load_soundfile()

    try:
        user_audio, user_sr = soundfile.read(user_audio_path, dtype="float32")
        ref_audio, ref_sr = soundfile.read(ref_audio_path, dtype="float32")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Audio file not found: {exc.filename}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to read audio file: {str(exc)}") from exc

    if len(user_audio.shape) > 1:
        user_audio = user_audio.mean(axis=1)
    if len(ref_audio.shape) > 1:
        ref_audio = ref_audio.mean(axis=1)

    try:
        user_beat_result = beat_detector.get_beats(user_audio, user_sr)
        ref_beat_result = beat_detector.get_beats(ref_audio, ref_sr)
        user_beats = user_beat_result["beats"]
        ref_beats = ref_beat_result["beats"]
    except Exception as exc:
        raise RuntimeError(f"Beat detection failed: {str(exc)}") from exc

    try:
        comparison_result = rhythm_analyzer.compare_rhythm(
            user_beats,
            ref_beats,
            scoring_model=scoring_model,
            language=language,
        )
    except Exception as exc:
        raise RuntimeError(f"Rhythm comparison failed: {str(exc)}") from exc

    formatter = FeedbackFormatter(language)
    return {
        "score": comparison_result["score"],
        "timing_accuracy": comparison_result["timing_accuracy"],
        "mean_deviation_ms": comparison_result["mean_deviation_ms"],
        "max_deviation_ms": comparison_result["max_deviation_ms"],
        "std_deviation_ms": comparison_result["std_deviation_ms"],
        "missing_beats": comparison_result["missing_beats"],
        "extra_beats": comparison_result["extra_beats"],
        "valid_matches": comparison_result["valid_matches"],
        "total_ref_beats": comparison_result["total_ref_beats"],
        "coverage_ratio": comparison_result["coverage_ratio"],
        "user_consistency": comparison_result["user_consistency"],
        "ref_consistency": comparison_result["ref_consistency"],
        "consistency_ratio": comparison_result["consistency_ratio"],
        "tempo_analysis": comparison_result["tempo_analysis"],
        "error_classification": comparison_result["error_classification"],
        "feedback": comparison_result["feedback"],
        "detailed_assessment": comparison_result["detailed_assessment"],
        "language": language,
        "scoring_model": scoring_model,
        "analysis_type": "rhythm_comparison",
        "reference_duration": float(len(ref_audio) / ref_sr),
        "user_duration": float(len(user_audio) / user_sr),
        "reference_bpm": ref_beat_result.get("bpm", 0),
        "user_bpm": user_beat_result.get("bpm", 0),
        "formatter_language": formatter.language,
    }
