"""WhisperX-based lyric transcription helpers for piano score generation."""

from __future__ import annotations

import importlib
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.core.pitch.audio_utils import AudioDependencyError

logger = logging.getLogger(__name__)

VOCAL_TRACK_NAMES = {"vocal", "vocals", "lead_vocal"}
MAX_ASR_AUDIO_DURATION_SECONDS = 600.0
WHISPERX_MODEL_SIZE = "base"
WHISPERX_DEVICE = "cpu"
WHISPERX_COMPUTE_TYPE = "int8"
_WHITESPACE_RE = re.compile(r"\s+")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def normalize_whisperx_language(value: Any) -> str | None:
    normalized = str(value or "").strip().lower().replace("_", "-")
    if not normalized or normalized == "auto":
        return None
    if normalized in {"zh-cn", "zh-hans", "cn", "chs", "zh-tw", "zh-hant", "cht"}:
        return "zh"
    if normalized == "english":
        return "en"
    if normalized == "japanese":
        return "ja"
    if normalized == "korean":
        return "ko"
    return normalized


def validate_whisperx_runtime() -> None:
    if shutil.which("ffmpeg") is None:
        raise AudioDependencyError("当前环境缺少 ffmpeg，无法运行 WhisperX 自动歌词识别。")
    try:
        importlib.import_module("whisperx")
    except ModuleNotFoundError as exc:
        raise AudioDependencyError("当前环境未安装 whisperx，无法运行 WhisperX 自动歌词识别。") from exc


def _normalize_track_name(name: Any) -> str:
    return str(name or "").strip().lower()


def _compact_text(text: Any) -> str:
    normalized = _WHITESPACE_RE.sub(" ", str(text or "").replace("\n", " ").replace("\r", " ")).strip()
    return normalized


def _contains_cjk(text: Any) -> bool:
    return bool(_CJK_RE.search(str(text or "")))


def infer_whisperx_retry_language(*context_texts: Any, preferred_language: str | None = None) -> str | None:
    normalized_preference = normalize_whisperx_language(preferred_language)
    if normalized_preference:
        return normalized_preference
    if any(_contains_cjk(text) for text in context_texts):
        return "zh"
    return None


def _combined_transcription_text(transcription: dict[str, Any] | None) -> str:
    segments = [segment for segment in list((transcription or {}).get("segments") or []) if isinstance(segment, dict)]
    joined = " ".join(_compact_text(segment.get("text")) for segment in segments)
    return _compact_text(joined)


def should_retry_whisperx_transcription(
    transcription: dict[str, Any] | None,
    *,
    retry_language: str | None,
) -> bool:
    normalized_retry = normalize_whisperx_language(retry_language)
    if normalized_retry != "zh":
        return False

    payload = transcription or {}
    detected_language = str(payload.get("language") or "").strip().lower()
    combined_text = _combined_transcription_text(payload)
    if not combined_text:
        return True
    if _contains_cjk(combined_text):
        return False
    if detected_language.startswith("zh"):
        return False
    if detected_language in {"en", "fr", "de", "es", "it"}:
        return True

    compact = combined_text.replace(" ", "")
    latin_ratio = len(_LATIN_RE.findall(compact)) / max(len(compact), 1)
    return latin_ratio >= 0.4


def _guess_language_joiner(language: str | None) -> str:
    normalized = str(language or "").strip().lower()
    if normalized.startswith(("zh", "ja", "ko")):
        return ""
    return " "


def _join_token_texts(tokens: list[str], language: str | None) -> str:
    joiner = _guess_language_joiner(language)
    meaningful = [token for token in tokens if token]
    if not meaningful:
        return ""
    return joiner.join(meaningful) if joiner else "".join(meaningful)


def _load_track_audio_bytes(track: dict[str, Any]) -> bytes:
    file_path = Path(str(track.get("file_path") or "").strip())
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Separated track file not found: {file_path}")
    return file_path.read_bytes()


def select_whisperx_audio_source(
    *,
    file_name: str,
    audio_bytes: bytes,
    separation_result: dict[str, Any] | None = None,
    melody_track: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    tracks = [track for track in list((separation_result or {}).get("tracks") or []) if isinstance(track, dict)]
    selected_track_name = _normalize_track_name((melody_track or {}).get("name"))
    selected_track_file = str((melody_track or {}).get("file_name") or "").strip()

    def try_track(track: dict[str, Any], source: str) -> dict[str, Any] | None:
        try:
            return {
                "source": source,
                "track_name": str(track.get("name") or source),
                "file_name": str(track.get("file_name") or file_name or "audio.wav"),
                "audio_bytes": _load_track_audio_bytes(track),
                "warnings": warnings,
            }
        except FileNotFoundError as exc:
            warnings.append(f"歌词识别候选轨缺失，已回退到其他音轨：{exc}")
            return None

    for track in tracks:
        if _normalize_track_name(track.get("name")) in VOCAL_TRACK_NAMES:
            chosen = try_track(track, "vocal_track")
            if chosen is not None:
                return chosen

    for track in tracks:
        if _normalize_track_name(track.get("name")) == selected_track_name and selected_track_name:
            chosen = try_track(track, "melody_track")
            if chosen is not None:
                return chosen

    for track in tracks:
        if str(track.get("file_name") or "").strip() == selected_track_file and selected_track_file:
            chosen = try_track(track, "melody_track")
            if chosen is not None:
                return chosen

    for track in tracks:
        chosen = try_track(track, "separated_track")
        if chosen is not None:
            return chosen

    return {
        "source": "mixed_audio",
        "track_name": "mix",
        "file_name": file_name,
        "audio_bytes": audio_bytes,
        "warnings": warnings,
    }


def _load_whisperx():
    validate_whisperx_runtime()
    return importlib.import_module("whisperx")


def _write_temp_audio_file(audio_bytes: bytes, file_name: str) -> str:
    suffix = Path(str(file_name or "")).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(audio_bytes)
        handle.flush()
        return handle.name


def transcribe_audio_with_whisperx(
    *,
    audio_bytes: bytes,
    file_name: str,
    title: str | None = None,
    preferred_language: str | None = None,
    model_size: str = WHISPERX_MODEL_SIZE,
    device: str = WHISPERX_DEVICE,
    compute_type: str = WHISPERX_COMPUTE_TYPE,
) -> dict[str, Any]:
    whisperx = _load_whisperx()
    temp_path = _write_temp_audio_file(audio_bytes, file_name)
    try:
        audio = whisperx.load_audio(temp_path)
        model = whisperx.load_model(model_size, device, compute_type=compute_type)
        requested_language = normalize_whisperx_language(preferred_language)
        retry_language = infer_whisperx_retry_language(file_name, title, preferred_language=preferred_language)

        def run_transcription(language: str | None) -> dict[str, Any]:
            kwargs: dict[str, Any] = {"batch_size": 1}
            if language:
                kwargs["language"] = language
            return model.transcribe(audio, **kwargs)

        transcription = run_transcription(requested_language)
        warnings: list[str] = []
        retry_language_used: str | None = None
        if requested_language is None and should_retry_whisperx_transcription(
            transcription,
            retry_language=retry_language,
        ):
            retry_language_used = retry_language
            transcription = run_transcription(retry_language)
            if retry_language_used == "zh":
                warnings.append("检测到中文上下文且首次转写结果疑似误判，已自动回退为中文重试。")
    except Exception as exc:
        raise RuntimeError(f"WhisperX 转写失败：{exc}") from exc
    finally:
        Path(temp_path).unlink(missing_ok=True)
    return {
        "audio": audio,
        "transcription": transcription,
        "warnings": warnings,
        "requested_language": requested_language,
        "retry_language": retry_language,
        "retry_language_used": retry_language_used,
    }


def align_transcription_with_whisperx(
    transcription: dict[str, Any],
    *,
    audio: Any,
    device: str = WHISPERX_DEVICE,
) -> tuple[dict[str, Any], list[str]]:
    whisperx = _load_whisperx()
    language = str(transcription.get("language") or "").strip().lower()
    if not language:
        return transcription, ["WhisperX 未返回语言信息，已跳过逐词对齐。"]

    try:
        model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
        aligned = whisperx.align(
            transcription.get("segments") or [],
            model_a,
            metadata,
            audio,
            device,
            return_char_alignments=False,
        )
        return aligned, []
    except Exception as exc:
        logger.warning("WhisperX alignment failed for language=%s: %s", language, exc)
        return transcription, [f"WhisperX 逐词对齐失败，已回退为逐行时间戳：{exc}"]


def normalize_whisperx_result_to_lyrics_payload(
    result: dict[str, Any] | None,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    normalized_warnings = list(warnings or [])
    payload = result or {}
    language = str(payload.get("language") or "").strip().lower() or None
    segments = [segment for segment in list(payload.get("segments") or []) if isinstance(segment, dict)]

    lines: list[dict[str, Any]] = []
    has_token_timestamps = False
    has_line_timestamps = False

    for segment in segments:
        line_text = _compact_text(segment.get("text"))
        line_time = segment.get("start")
        if line_time is not None:
            try:
                line_time = round(float(line_time), 3)
                has_line_timestamps = True
            except (TypeError, ValueError):
                line_time = None

        tokens: list[dict[str, Any]] = []
        for word in list(segment.get("words") or []):
            if not isinstance(word, dict):
                continue
            token_text = _compact_text(word.get("word") or word.get("text"))
            if not token_text:
                continue
            token_time = word.get("start")
            if token_time is not None:
                try:
                    token_time = round(float(token_time), 3)
                    has_token_timestamps = True
                except (TypeError, ValueError):
                    token_time = None
            tokens.append({"text": token_text, "time": token_time})

        timed_tokens = [token for token in tokens if token.get("time") is not None]
        if timed_tokens:
            lines.append(
                {
                    "time": line_time if line_time is not None else timed_tokens[0]["time"],
                    "text": line_text or _join_token_texts([str(token["text"]) for token in tokens], language),
                    "tokens": tokens,
                }
            )
            continue

        if line_text:
            lines.append({"time": line_time, "text": line_text, "tokens": []})

    if not lines:
        return {
            "status": "missing",
            "source": "whisperx_asr",
            "has_timestamps": False,
            "timing_kind": "none",
            "lines": [],
            "line_count": 0,
            "warnings": normalized_warnings,
            "language": language,
        }

    timing_kind = "token" if has_token_timestamps else "line" if has_line_timestamps else "none"
    return {
        "status": "imported",
        "source": "whisperx_asr",
        "has_timestamps": timing_kind != "none",
        "timing_kind": timing_kind,
        "lines": lines,
        "line_count": len(lines),
        "warnings": normalized_warnings,
        "language": language,
    }


__all__ = [
    "MAX_ASR_AUDIO_DURATION_SECONDS",
    "WHISPERX_COMPUTE_TYPE",
    "WHISPERX_DEVICE",
    "WHISPERX_MODEL_SIZE",
    "align_transcription_with_whisperx",
    "infer_whisperx_retry_language",
    "normalize_whisperx_language",
    "normalize_whisperx_result_to_lyrics_payload",
    "select_whisperx_audio_source",
    "should_retry_whisperx_transcription",
    "transcribe_audio_with_whisperx",
    "validate_whisperx_runtime",
]
