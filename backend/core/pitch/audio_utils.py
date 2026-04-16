"""Audio helpers for pitch analysis.

The pitch detector deliberately stays dependency-light, so this module keeps a
small set of pure-Python preprocessing utilities for uploaded bytes, raw PCM,
sample arrays, and multi-track payloads.
"""

from __future__ import annotations

import io
import importlib
import math
import tempfile
import wave
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4

from backend.numba_compat import ensure_numba_cache_dir

DEFAULT_SAMPLE_RATE = 16000
RAW_PCM_EXTENSIONS = {".raw", ".pcm", ".s16", ".f32"}
COMPRESSED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".flac", ".opus", ".webm"}


class AudioDecodeError(ValueError):
    """Raised when uploaded audio bytes cannot be decoded into samples."""


class AudioDependencyError(RuntimeError):
    """Raised when optional audio decoding dependencies are unavailable."""


def infer_audio_metadata(file_name: str, sample_rate: int | None = None, duration: float | None = None) -> dict:
    return {
        "analysis_id": f"an_{uuid4().hex[:12]}",
        "file_name": file_name,
        "sample_rate": sample_rate or DEFAULT_SAMPLE_RATE,
        "duration": duration or 60.0,
    }


def estimate_duration_from_bytes(audio_bytes: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> float:
    if not audio_bytes:
        return 0.0
    return round(len(audio_bytes) / max(sample_rate * 2, 1), 2)


def safe_sample_rate(sample_rate: int | None) -> int:
    rate = sample_rate or DEFAULT_SAMPLE_RATE
    return int(rate) if int(rate) > 0 else DEFAULT_SAMPLE_RATE


def _file_extension(file_name: str | None) -> str:
    if not file_name:
        return ""
    return Path(file_name).suffix.lower()


def _is_wave_bytes(audio_bytes: bytes) -> bool:
    return audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"


def _should_allow_raw_pcm(file_name: str | None, allow_raw_pcm: bool | None) -> bool:
    if allow_raw_pcm is not None:
        return allow_raw_pcm
    if file_name is None:
        return True
    return _file_extension(file_name) in RAW_PCM_EXTENSIONS


def _load_librosa():
    try:
        ensure_numba_cache_dir()
        return importlib.import_module("librosa")
    except ModuleNotFoundError as exc:
        raise AudioDependencyError("环境缺少 librosa，无法解码压缩音频格式。") from exc


def _decode_with_librosa(audio_bytes: bytes, file_name: str | None, sample_rate: int) -> tuple[list[float], int]:
    suffix = _file_extension(file_name) or ".audio"
    temp_path: str | None = None
    try:
        librosa = _load_librosa()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            temp_path = handle.name
            handle.write(audio_bytes)
            handle.flush()
        samples, decoded_rate = librosa.load(temp_path, sr=None, mono=True)
    except AudioDependencyError:
        raise
    except Exception as exc:
        readable_name = file_name or "音频文件"
        raise AudioDecodeError(
            f"无法解码该音频格式：{readable_name}。请上传有效的 WAV、MP3、M4A、OGG 或显式 RAW/PCM 音频。"
        ) from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)

    return _coerce_sample_list(samples), safe_sample_rate(decoded_rate or sample_rate)


def _normalize_int_samples(raw: bytes, sample_width: int, channels: int) -> list[float]:
    if not raw:
        return []

    channels = max(int(channels or 1), 1)
    sample_width = max(int(sample_width or 2), 1)

    values: list[float] = []
    frame_width = sample_width * channels
    usable_length = len(raw) - (len(raw) % frame_width)

    for frame_start in range(0, usable_length, frame_width):
        channel_values: list[float] = []
        for channel in range(channels):
            start = frame_start + channel * sample_width
            chunk = raw[start : start + sample_width]
            if sample_width == 1:
                value = (chunk[0] - 128) / 128.0
            else:
                integer = int.from_bytes(chunk, byteorder="little", signed=True)
                max_abs = float(1 << (8 * sample_width - 1))
                value = integer / max_abs
            channel_values.append(value)
        values.append(sum(channel_values) / len(channel_values))

    return values


def audio_bytes_to_samples(
    audio_bytes: bytes | None,
    sample_rate: int | None = None,
    *,
    file_name: str | None = None,
    allow_raw_pcm: bool | None = None,
) -> tuple[list[float], int]:
    """Decode uploaded audio bytes into mono float samples.

    WAV files are decoded with the standard library. Compressed formats are
    decoded via the project's optional audio stack. Raw PCM fallback is only
    enabled for explicit RAW/PCM inputs or callers that opt in.
    """

    rate = safe_sample_rate(sample_rate)
    if not audio_bytes:
        return [], rate

    if _is_wave_bytes(audio_bytes):
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                rate = wav_file.getframerate() or rate
                raw = wav_file.readframes(wav_file.getnframes())
                samples = _normalize_int_samples(raw, wav_file.getsampwidth(), wav_file.getnchannels())
                return samples, rate
        except (wave.Error, EOFError) as exc:
            raise AudioDecodeError("WAV 音频文件损坏或无法读取。") from exc

    if _should_allow_raw_pcm(file_name, allow_raw_pcm):
        return _normalize_int_samples(audio_bytes, sample_width=2, channels=1), rate

    return _decode_with_librosa(audio_bytes, file_name, rate)


def extract_audio_features(frame: Sequence[float]) -> dict[str, float]:
    """Extract lightweight features used by pitch detection and visual reports."""

    if not frame:
        return {"rms": 0.0, "zcr": 0.0, "peak": 0.0, "energy": 0.0}

    rms = math.sqrt(sum(sample * sample for sample in frame) / len(frame))
    peak = max(abs(sample) for sample in frame)
    crossings = 0
    previous = frame[0]
    for sample in frame[1:]:
        if (previous >= 0 > sample) or (previous < 0 <= sample):
            crossings += 1
        previous = sample
    zcr = crossings / max(len(frame) - 1, 1)
    return {
        "rms": round(rms, 5),
        "zcr": round(zcr, 5),
        "peak": round(peak, 5),
        "energy": round(rms * rms, 7),
    }


def prepare_pitch_frame(frame: Sequence[float]) -> list[float]:
    """Remove DC offset and apply a Hann window before pitch estimation."""

    if not frame:
        return []
    dc = mean(frame)
    length = len(frame)
    if length == 1:
        return [frame[0] - dc]
    return [
        (sample - dc) * (0.5 - 0.5 * math.cos(2 * math.pi * index / (length - 1)))
        for index, sample in enumerate(frame)
    ]


def _coerce_sample_list(value: Any) -> list[float]:
    if isinstance(value, (bytes, bytearray, str)) or value is None:
        return []
    if not isinstance(value, Sequence):
        try:
            sample = float(value)
        except (TypeError, ValueError):
            return []
        return [sample if math.isfinite(sample) else 0.0]

    samples: list[float] = []
    for item in value:
        if isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray, str)):
            nested = _coerce_sample_list(item)
            samples.append(sum(nested) / len(nested) if nested else 0.0)
            continue
        try:
            sample = float(item)
        except (TypeError, ValueError):
            sample = 0.0
        samples.append(sample if math.isfinite(sample) else 0.0)
    return samples


def _preprocess_track_samples(
    samples: Sequence[float],
    *,
    remove_dc: bool = True,
    noise_gate: float = 0.0,
) -> list[float]:
    if not samples:
        return []

    cleaned: list[float] = []
    for sample in samples:
        try:
            value = float(sample)
        except (TypeError, ValueError):
            value = 0.0
        cleaned.append(max(-1.0, min(1.0, value)) if math.isfinite(value) else 0.0)

    if remove_dc and cleaned:
        dc = mean(cleaned)
        cleaned = [sample - dc for sample in cleaned]

    gate = max(float(noise_gate or 0.0), 0.0)
    if gate:
        cleaned = [0.0 if abs(sample) < gate else sample for sample in cleaned]

    return cleaned


def _resample_linear(samples: Sequence[float], source_rate: int, target_rate: int) -> list[float]:
    if not samples or source_rate == target_rate:
        return list(samples)

    ratio = target_rate / max(source_rate, 1)
    target_length = max(int(round(len(samples) * ratio)), 1)
    if target_length == 1:
        return [samples[0]]

    result: list[float] = []
    scale = (len(samples) - 1) / max(target_length - 1, 1)
    for index in range(target_length):
        position = index * scale
        left = int(position)
        right = min(left + 1, len(samples) - 1)
        fraction = position - left
        result.append(samples[left] * (1.0 - fraction) + samples[right] * fraction)
    return result


def _decode_track_payload(payload: Any, default_rate: int, name: str) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        track_rate = safe_sample_rate(payload.get("sample_rate") or default_rate)
        track_name = str(payload.get("name") or payload.get("track") or name)
        byte_payload = payload.get("audio_bytes") or payload.get("bytes") or payload.get("pcm_bytes")
        allow_raw_pcm = payload.get("allow_raw_pcm")
        if isinstance(byte_payload, str):
            byte_payload = byte_payload.encode("utf-8")
        if isinstance(byte_payload, (bytes, bytearray)):
            samples, decoded_rate = audio_bytes_to_samples(
                bytes(byte_payload),
                track_rate,
                file_name=track_name,
                allow_raw_pcm=allow_raw_pcm,
            )
            return {"name": track_name, "samples": samples, "sample_rate": decoded_rate}

        sample_payload = payload.get("samples", payload.get("data", payload.get("frames", [])))
        return {"name": track_name, "samples": _coerce_sample_list(sample_payload), "sample_rate": track_rate}

    if isinstance(payload, (bytes, bytearray)):
        samples, decoded_rate = audio_bytes_to_samples(bytes(payload), default_rate, file_name=name)
        return {"name": name, "samples": samples, "sample_rate": decoded_rate}

    return {"name": name, "samples": _coerce_sample_list(payload), "sample_rate": default_rate}


def decode_audio_tracks(
    audio_input: Any,
    sample_rate: int | None = None,
    *,
    default_name: str = "mix",
) -> tuple[list[dict[str, Any]], int]:
    """Normalize mono or complex multi-track input into named sample tracks.

    Supported forms include raw/WAV bytes, a single sample sequence, a sequence
    of tracks, ``{"tracks": [...]}``, and mappings such as
    ``{"vocal": samples, "accompaniment": bytes}``.
    """

    target_rate = safe_sample_rate(sample_rate)
    if audio_input is None:
        return [], target_rate

    if isinstance(audio_input, Mapping) and "tracks" in audio_input:
        tracks_payload = audio_input.get("tracks") or []
        target_rate = safe_sample_rate(audio_input.get("sample_rate") or target_rate)
        tracks = [
            _decode_track_payload(track, target_rate, f"track_{index + 1}")
            for index, track in enumerate(tracks_payload)
        ]
        return tracks, target_rate

    if isinstance(audio_input, Mapping) and not any(
        key in audio_input for key in ("audio_bytes", "bytes", "pcm_bytes", "samples", "data", "frames")
    ):
        tracks = [
            _decode_track_payload(payload, target_rate, str(name))
            for name, payload in audio_input.items()
            if name not in {"sample_rate", "duration", "metadata"}
        ]
        return tracks, target_rate

    if isinstance(audio_input, Sequence) and not isinstance(audio_input, (bytes, bytearray, str)):
        if audio_input and all(isinstance(item, (Mapping, bytes, bytearray)) for item in audio_input):
            tracks = [
                _decode_track_payload(track, target_rate, f"track_{index + 1}")
                for index, track in enumerate(audio_input)
            ]
            return tracks, target_rate

        nested_lengths = [
            len(item)
            for item in audio_input
            if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray))
        ]
        if nested_lengths and max(nested_lengths) > 8:
            tracks = [
                _decode_track_payload(track, target_rate, f"track_{index + 1}")
                for index, track in enumerate(audio_input)
            ]
            return tracks, target_rate

        if audio_input and all(
            isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)) for item in audio_input
        ):
            return [_decode_track_payload(audio_input, target_rate, default_name)], target_rate

    return [_decode_track_payload(audio_input, target_rate, default_name)], target_rate


def mix_audio_tracks(tracks: Sequence[dict[str, Any]], sample_rate: int, normalize: bool = True) -> list[float]:
    """Mix preprocessed tracks with RMS-aware weights for polyphonic inputs."""

    if not tracks:
        return []

    prepared: list[list[float]] = []
    weights: list[float] = []
    target_rate = safe_sample_rate(sample_rate)
    for track in tracks:
        samples = track.get("samples", [])
        track_rate = safe_sample_rate(track.get("sample_rate") or target_rate)
        resampled = _resample_linear(samples, track_rate, target_rate)
        features = extract_audio_features(resampled)
        prepared.append(resampled)
        weights.append(max(features["rms"], 0.02))

    max_length = max((len(samples) for samples in prepared), default=0)
    if max_length == 0:
        return []

    weight_sum = sum(weights) or 1.0
    mixed: list[float] = []
    for index in range(max_length):
        value = 0.0
        for samples, weight in zip(prepared, weights):
            if index < len(samples):
                value += samples[index] * weight
        mixed.append(value / weight_sum)

    peak = max((abs(sample) for sample in mixed), default=0.0)
    if normalize and peak > 0.98:
        mixed = [sample / peak * 0.98 for sample in mixed]
    return mixed


def preprocess_audio_features(
    audio_input: Any,
    sample_rate: int | None = None,
    *,
    file_name: str = "mix",
    remove_dc: bool = True,
    noise_gate: float = 0.003,
    normalize: bool = True,
) -> dict[str, Any]:
    """Decode, clean, align, and mix audio before pitch feature extraction."""

    target_rate = safe_sample_rate(sample_rate)
    decoded_tracks, target_rate = decode_audio_tracks(audio_input, target_rate, default_name=file_name)
    tracks: list[dict[str, Any]] = []
    for index, track in enumerate(decoded_tracks):
        raw_samples = track.get("samples", [])
        cleaned = _preprocess_track_samples(raw_samples, remove_dc=remove_dc, noise_gate=noise_gate)
        track_rate = safe_sample_rate(track.get("sample_rate") or target_rate)
        tracks.append(
            {
                "name": str(track.get("name") or f"track_{index + 1}"),
                "sample_rate": track_rate,
                "samples": cleaned,
                "features": extract_audio_features(cleaned),
            }
        )

    mixed = mix_audio_tracks(tracks, target_rate, normalize=normalize)
    return {
        "sample_rate": target_rate,
        "track_count": len(tracks),
        "tracks": tracks,
        "samples": mixed,
        "features": extract_audio_features(mixed),
    }
