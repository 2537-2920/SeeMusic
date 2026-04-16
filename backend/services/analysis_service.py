"""End-to-end audio analysis orchestration and persistence helpers."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import soundfile as sf
from sqlalchemy import select

from backend.config.settings import settings
from backend.core.pitch.pitch_comparison import build_pitch_comparison_payload
from backend.core.pitch.audio_utils import infer_audio_metadata, estimate_duration_from_bytes
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.utils.audio_logger import record_audio_processing_log
from backend.utils.data_visualizer import build_pitch_curve


USE_DB: bool = False
_session_factory = None
ANALYSIS_RESULTS: dict[str, dict[str, Any]] = {}


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
    payload = {
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
    if not USE_DB:
        ANALYSIS_RESULTS[analysis_id] = payload
        return

    from backend.db.models import AudioAnalysis, PitchSequence

    with _session_scope() as session:
        analysis = session.execute(select(AudioAnalysis).where(AudioAnalysis.analysis_id == analysis_id)).scalar_one_or_none()
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
                result=_json_ready(deepcopy(result_data or {})),
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
            analysis.result = _json_ready(deepcopy(result_data or analysis.result or {}))
            session.add(analysis)
            session.flush()

        if pitch_sequence is not None:
            session.query(PitchSequence).filter_by(analysis_id=analysis_id, is_reference=is_reference).delete()
            for item in payload["pitch_sequence"]:
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


def get_saved_pitch_sequence(analysis_id: str, *, is_reference: bool | None = None) -> list[dict[str, Any]] | None:
    if not USE_DB:
        stored = ANALYSIS_RESULTS.get(analysis_id)
        if stored is None:
            return None
        sequence = list(stored.get("pitch_sequence") or [])
        if is_reference is None:
            return deepcopy(sequence)
        if bool(stored.get("is_reference")) == is_reference:
            return deepcopy(sequence)
        return None

    from backend.db.models import PitchSequence

    with _session_scope() as session:
        statement = select(PitchSequence).where(PitchSequence.analysis_id == analysis_id).order_by(PitchSequence.time.asc())
        if is_reference is not None:
            statement = statement.where(PitchSequence.is_reference == is_reference)
        rows = list(session.execute(statement).scalars())
        if not rows:
            return None
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
    score = build_score_from_pitch_sequence(pitch_sequence)
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


def _ensure_wav_upload(file_name: str, audio_bytes: bytes, label: str) -> None:
    if not audio_bytes:
        raise ValueError(f"{label} audio is empty")
    if not file_name.lower().endswith(".wav"):
        raise ValueError(f"{label} audio must be a WAV file")
    if not (audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"):
        raise ValueError(f"{label} audio is not a valid WAV file")


def _write_uploaded_wav(file_name: str, audio_bytes: bytes, prefix: str) -> str:
    storage_dir = Path(getattr(settings, "storage_dir", "temp")) / "singing_evaluation"
    storage_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_name or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix, dir=storage_dir, delete=False) as handle:
        handle.write(audio_bytes)
        return handle.name


def _public_track_metadata(separation: dict[str, Any], vocal_track: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": separation.get("task_id"),
        "model": separation.get("model"),
        "backend_used": separation.get("backend_used"),
        "fallback_used": separation.get("fallback_used", False),
        "warnings": separation.get("warnings", []),
        "vocal_track": {
            "name": vocal_track.get("name"),
            "file_name": vocal_track.get("file_name"),
            "download_url": vocal_track.get("download_url"),
            "duration": vocal_track.get("duration"),
        },
    }


def _separate_vocal_track(
    *,
    file_name: str,
    audio_bytes: bytes,
    model: str,
    sample_rate: int,
) -> tuple[str, bytes, dict[str, Any]]:
    from backend.core.separation.multi_track_separation import separate_tracks

    separation = separate_tracks(
        file_name=file_name,
        model=model,
        stems=2,
        audio_bytes=audio_bytes,
        sample_rate=sample_rate,
    )
    if separation.get("status") != "completed":
        raise RuntimeError(f"vocal separation failed for {file_name}: {separation.get('error', 'unknown error')}")

    vocal_track = next((track for track in separation.get("tracks", []) if track.get("name") == "vocal"), None)
    if not vocal_track or not vocal_track.get("file_path"):
        raise RuntimeError(f"vocal separation did not return a vocal track for {file_name}")

    vocal_path = str(vocal_track["file_path"])
    with open(vocal_path, "rb") as handle:
        vocal_bytes = handle.read()

    return vocal_path, vocal_bytes, _public_track_metadata(separation, vocal_track)


def _normalize_user_audio_mode(user_audio_mode: str) -> str:
    normalized_mode = (user_audio_mode or "a_cappella").strip().lower()
    if normalized_mode in {"clear", "clean", "vocal", "acapella", "a-cappella", "清唱版本", "清唱"}:
        return "a_cappella"
    if normalized_mode in {"with_accompaniment", "accompanied", "mixed", "伴奏", "带伴奏版本", "带伴奏"}:
        return "with_accompaniment"
    if normalized_mode in {"a_cappella", "with_accompaniment"}:
        return normalized_mode
    raise ValueError("user_audio_mode must be either 'a_cappella' or 'with_accompaniment'")


def evaluate_singing(
    *,
    reference_file_name: str,
    reference_audio_bytes: bytes,
    user_file_name: str,
    user_audio_bytes: bytes,
    user_audio_mode: str = "a_cappella",
    language: str = "zh",
    scoring_model: str = "balanced",
    threshold_ms: float = 50.0,
    separation_model: str = "demucs",
    sample_rate: int = 44100,
    pitch_sample_rate: int = 16000,
) -> dict[str, Any]:
    """Evaluate singing using separated reference vocals and optional user vocal separation."""

    normalized_mode = _normalize_user_audio_mode(user_audio_mode)
    _ensure_wav_upload(reference_file_name, reference_audio_bytes, "reference")
    _ensure_wav_upload(user_file_name, user_audio_bytes, "user")

    metadata = infer_audio_metadata(user_file_name, sample_rate=pitch_sample_rate)
    reference_log = record_audio_processing_log(
        file_name=reference_file_name,
        audio_bytes=reference_audio_bytes,
        sample_rate=sample_rate,
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="singing_reference_upload",
        params={"separation_model": separation_model},
    )
    user_log = record_audio_processing_log(
        file_name=user_file_name,
        audio_bytes=user_audio_bytes,
        sample_rate=sample_rate,
        analysis_id=metadata["analysis_id"],
        source="api",
        stage="singing_user_upload",
        params={"user_audio_mode": normalized_mode, "separation_model": separation_model},
    )

    reference_vocal_path, reference_vocal_bytes, reference_separation = _separate_vocal_track(
        file_name=reference_file_name,
        audio_bytes=reference_audio_bytes,
        model=separation_model,
        sample_rate=sample_rate,
    )

    cleanup_paths: list[str] = []
    user_separation: dict[str, Any] | None = None
    if normalized_mode == "with_accompaniment":
        user_vocal_path, user_vocal_bytes, user_separation = _separate_vocal_track(
            file_name=user_file_name,
            audio_bytes=user_audio_bytes,
            model=separation_model,
            sample_rate=sample_rate,
        )
    else:
        user_vocal_path = _write_uploaded_wav(user_file_name, user_audio_bytes, "user_a_cappella_")
        cleanup_paths.append(user_vocal_path)
        user_vocal_bytes = user_audio_bytes

    try:
        rhythm_report = _json_ready(
            process_rhythm_scoring_sync(
                user_vocal_path,
                reference_vocal_path,
                language=language,
                scoring_model=scoring_model,
                threshold_ms=threshold_ms,
            )
        )
        reference_pitch_sequence = detect_pitch_sequence(
            file_name=f"{reference_file_name}:vocal",
            sample_rate=pitch_sample_rate,
            duration=rhythm_report.get("reference_duration"),
            audio_bytes=reference_vocal_bytes,
        )
        user_pitch_sequence = detect_pitch_sequence(
            file_name=f"{user_file_name}:vocal",
            sample_rate=pitch_sample_rate,
            duration=rhythm_report.get("user_duration"),
            audio_bytes=user_vocal_bytes,
        )
        pitch_comparison = build_pitch_comparison_payload(
            reference_pitch_sequence,
            user_pitch_sequence,
            mode="singing_evaluation",
        )

        rhythm_score = float(rhythm_report.get("score", 0.0) or 0.0)
        pitch_score = float(pitch_comparison["summary"].get("accuracy", 0.0) or 0.0)
        overall_score = round(rhythm_score * 0.5 + pitch_score * 0.5, 2)
        result_data = {
            "analysis_type": "singing_evaluation",
            "rhythm_report": rhythm_report,
            "pitch_comparison": pitch_comparison,
            "overall_score": overall_score,
            "user_audio_mode": normalized_mode,
            "reference_separation": reference_separation,
            "user_separation": user_separation,
            "logs": {
                "reference_log_id": reference_log["log_id"],
                "user_log_id": user_log["log_id"],
            },
        }

        save_analysis_result(
            analysis_id=metadata["analysis_id"],
            file_name=user_file_name,
            sample_rate=pitch_sample_rate,
            duration=rhythm_report.get("user_duration"),
            bpm=int(rhythm_report.get("user_bpm", 0) or 0) or None,
            status=1,
            params={
                "pipeline": "singing_evaluation",
                "user_audio_mode": normalized_mode,
                "language": language,
                "scoring_model": scoring_model,
                "threshold_ms": threshold_ms,
                "separation_model": separation_model,
            },
            result_data=result_data,
            pitch_sequence=user_pitch_sequence,
        )

        return {
            "analysis_id": metadata["analysis_id"],
            "overall_score": overall_score,
            "score": rhythm_report.get("score", 0.0),
            "user_audio_mode": normalized_mode,
            "rhythm": rhythm_report,
            "pitch_comparison": pitch_comparison,
            "reference_pitch_sequence": reference_pitch_sequence,
            "user_pitch_sequence": user_pitch_sequence,
            "reference_separation": reference_separation,
            "user_separation": user_separation,
            "audio_logs": {
                "reference": reference_log,
                "user": user_log,
            },
        }
    finally:
        for path in cleanup_paths:
            try:
                os.remove(path)
            except OSError:
                pass


def process_rhythm_scoring_sync(
    user_audio_path: str,
    ref_audio_path: str,
    language: str = "en",
    scoring_model: str = "balanced",
    threshold_ms: float = 50.0,
) -> dict[str, Any]:
    from backend.core.rhythm.beat_detection import AdvancedBeatDetector
    from backend.core.rhythm.i18n import FeedbackFormatter
    from backend.core.rhythm.rhythm_analysis import AdvancedRhythmAnalyzer

    rhythm_analyzer = AdvancedRhythmAnalyzer(threshold_ms=threshold_ms)

    try:
        user_audio, user_sr = sf.read(user_audio_path, dtype="float32")
        ref_audio, ref_sr = sf.read(ref_audio_path, dtype="float32")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Audio file not found: {exc.filename}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to read audio file: {str(exc)}") from exc

    if len(user_audio.shape) > 1:
        user_audio = user_audio.mean(axis=1)
    if len(ref_audio.shape) > 1:
        ref_audio = ref_audio.mean(axis=1)

    def coerce_float(value: Any) -> float:
        item = getattr(value, "item", None)
        if callable(item):
            try:
                value = item()
            except Exception:
                pass
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        return float(value or 0.0)

    def detect_audio_beats(audio: Any, sample_rate: int) -> dict[str, Any]:
        detector = AdvancedBeatDetector(sr=int(sample_rate))
        raw_result = detector.get_beats(audio)
        if isinstance(raw_result, tuple):
            if len(raw_result) >= 3:
                tempo, beat_times, info = raw_result[:3]
            elif len(raw_result) == 2:
                tempo, beat_times = raw_result
                info = {}
            else:
                raise ValueError("beat detector returned an empty tuple")
            return {
                "bpm": coerce_float(tempo),
                "beats": list(beat_times or []),
                "info": info or {},
            }
        if isinstance(raw_result, dict):
            beats = raw_result.get("beats", raw_result.get("beat_times", []))
            bpm = raw_result.get("bpm", raw_result.get("tempo", raw_result.get("primary_bpm", 0.0)))
            return {"bpm": coerce_float(bpm), "beats": list(beats or []), "info": raw_result}
        raise TypeError(f"unsupported beat detector result: {type(raw_result).__name__}")

    try:
        user_beat_result = detect_audio_beats(user_audio, user_sr)
        ref_beat_result = detect_audio_beats(ref_audio, ref_sr)
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


async def process_rhythm_scoring(
    user_audio_path: str,
    ref_audio_path: str,
    language: str = "en",
    scoring_model: str = "balanced",
    threshold_ms: float = 50.0,
) -> dict[str, Any]:
    return process_rhythm_scoring_sync(
        user_audio_path,
        ref_audio_path,
        language=language,
        scoring_model=scoring_model,
        threshold_ms=threshold_ms,
    )
