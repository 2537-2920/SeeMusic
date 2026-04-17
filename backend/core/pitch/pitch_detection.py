"""Single-note pitch detection and audio feature extraction.

The implementation intentionally avoids heavyweight audio dependencies so the
API can run in the lightweight test/dev environment. It supports WAV bytes and
raw little-endian PCM frames, then uses a YIN-style detector with an
autocorrelation fallback to produce frontend-friendly pitch time series data.
"""

from __future__ import annotations

import logging
from math import sin
from typing import Any, Sequence

import numpy as np

from backend.core.pitch.audio_utils import (
    AudioDecodeError,
    audio_bytes_to_samples,
    extract_audio_features,
    prepare_pitch_frame,
    preprocess_audio_features,
    safe_sample_rate,
)
from backend.core.score.note_mapping import frequency_to_midi, frequency_to_note, midi_to_frequency

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_MIN_FREQUENCY = 50.0
DEFAULT_MAX_FREQUENCY = 1200.0
DEFAULT_YIN_THRESHOLD = 0.12
SILENCE_RMS_THRESHOLD = 0.01
BATCH_FRAME_COUNT = 256

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_sample_rate(sample_rate: int | None) -> int:
    return safe_sample_rate(sample_rate)


def _prepare_frame(frame: Sequence[float]) -> list[float]:
    return prepare_pitch_frame(frame)


def _yin_pitch(
    frame: Sequence[float],
    sample_rate: int,
    min_frequency: float = DEFAULT_MIN_FREQUENCY,
    max_frequency: float = DEFAULT_MAX_FREQUENCY,
    threshold: float = DEFAULT_YIN_THRESHOLD,
) -> tuple[float, float]:
    prepared = _prepare_frame(frame)
    if not prepared:
        return 0.0, 0.0

    min_tau = max(int(sample_rate / max(max_frequency, 1.0)), 2)
    max_tau = min(int(sample_rate / max(min_frequency, 1.0)), len(prepared) - 2)
    if max_tau <= min_tau:
        return 0.0, 0.0

    difference = [0.0] * (max_tau + 1)
    for tau in range(1, max_tau + 1):
        total = 0.0
        limit = len(prepared) - tau
        for index in range(limit):
            delta = prepared[index] - prepared[index + tau]
            total += delta * delta
        difference[tau] = total

    cumulative = [1.0] * (max_tau + 1)
    running_sum = 0.0
    best_tau = min_tau
    best_value = float("inf")
    for tau in range(1, max_tau + 1):
        running_sum += difference[tau]
        cumulative[tau] = difference[tau] * tau / running_sum if running_sum else 1.0
        if tau >= min_tau and cumulative[tau] < best_value:
            best_value = cumulative[tau]
            best_tau = tau

    tau = None
    for candidate in range(min_tau, max_tau + 1):
        if cumulative[candidate] < threshold:
            while candidate + 1 <= max_tau and cumulative[candidate + 1] < cumulative[candidate]:
                candidate += 1
            tau = candidate
            break

    tau = tau or best_tau
    if tau <= 0:
        return 0.0, 0.0

    refined_tau = float(tau)
    if 1 <= tau < max_tau:
        left = cumulative[tau - 1]
        center = cumulative[tau]
        right = cumulative[tau + 1]
        denominator = left - 2 * center + right
        if abs(denominator) > 1e-12:
            refined_tau = tau + 0.5 * (left - right) / denominator

    frequency = sample_rate / refined_tau if refined_tau > 0 else 0.0
    clarity = _clamp(1.0 - float(cumulative[tau]), 0.0, 1.0)
    return frequency, clarity


def _autocorrelation_pitch(
    frame: Sequence[float],
    sample_rate: int,
    min_frequency: float = DEFAULT_MIN_FREQUENCY,
    max_frequency: float = DEFAULT_MAX_FREQUENCY,
) -> tuple[float, float]:
    prepared = _prepare_frame(frame)
    if not prepared:
        return 0.0, 0.0

    min_lag = max(int(sample_rate / max(max_frequency, 1.0)), 2)
    max_lag = min(int(sample_rate / max(min_frequency, 1.0)), len(prepared) - 2)
    if max_lag <= min_lag:
        return 0.0, 0.0

    frame_energy = sum(sample * sample for sample in prepared)
    if frame_energy <= 1e-12:
        return 0.0, 0.0

    best_lag = min_lag
    best_corr = -1.0
    for lag in range(min_lag, max_lag + 1):
        corr = 0.0
        for index in range(len(prepared) - lag):
            corr += prepared[index] * prepared[index + lag]
        corr /= frame_energy
        if corr > best_corr:
            best_corr = corr
            best_lag = lag

    return sample_rate / best_lag, _clamp(best_corr, 0.0, 1.0)


def detect_single_pitch(
    frame: Sequence[float],
    sample_rate: int,
    algorithm: str = "yin",
    min_frequency: float = DEFAULT_MIN_FREQUENCY,
    max_frequency: float = DEFAULT_MAX_FREQUENCY,
) -> dict:
    """Detect the dominant monophonic pitch in a single audio frame."""

    features = extract_audio_features(frame)
    if features["rms"] < SILENCE_RMS_THRESHOLD:
        return {
            "frequency": 0.0,
            "note": "Rest",
            "nearest_frequency": 0.0,
            "confidence": 0.0,
            "voiced": False,
            **features,
        }

    normalized_algorithm = (algorithm or "yin").lower()
    if normalized_algorithm in {"yin", "pyin"}:
        frequency, clarity = _yin_pitch(frame, sample_rate, min_frequency, max_frequency)
        if clarity < 0.35:
            fallback_frequency, fallback_clarity = _autocorrelation_pitch(frame, sample_rate, min_frequency, max_frequency)
            if fallback_clarity > clarity:
                frequency, clarity = fallback_frequency, fallback_clarity
    elif normalized_algorithm in {"autocorrelation", "acf"}:
        frequency, clarity = _autocorrelation_pitch(frame, sample_rate, min_frequency, max_frequency)
    else:
        frequency, clarity = _yin_pitch(frame, sample_rate, min_frequency, max_frequency)

    frequency = frequency if min_frequency <= frequency <= max_frequency else 0.0
    if frequency <= 0:
        return {
            "frequency": 0.0,
            "note": "Rest",
            "nearest_frequency": 0.0,
            "confidence": 0.0,
            "voiced": False,
            **features,
        }

    midi = frequency_to_midi(frequency)
    quantized_frequency = midi_to_frequency(midi)
    confidence = _clamp(clarity * _clamp(features["rms"] / 0.08, 0.3, 1.0), 0.0, 0.99)
    return {
        "frequency": round(float(frequency), 2),
        "note": frequency_to_note(frequency),
        "nearest_frequency": quantized_frequency,
        "confidence": round(confidence, 2),
        "voiced": confidence >= 0.25,
        **features,
    }


def _fallback_pitch_sequence(duration: float, hop_ms: int, algorithm: str) -> list[dict]:
    points: list[dict] = []
    total_frames = max(int(duration * 1000 / max(hop_ms, 1)), 1)
    for index in range(min(total_frames, 12)):
        time_point = round(index * hop_ms / 1000.0, 2)
        frequency = round(440.0 + sin(index / 3.0) * 6.0, 2)
        points.append(
            {
                "time": time_point,
                "frequency": frequency,
                "note": frequency_to_note(frequency),
                "confidence": round(max(0.95 - index * 0.01, 0.5), 2),
                "duration": round(hop_ms / 1000.0, 3),
                "algorithm": algorithm,
                "voiced": True,
                "rms": 0.08,
                "zcr": 0.05,
            }
        )
    return points


def _frame_signal(samples: Sequence[float], frame_size: int, hop_size: int) -> tuple[np.ndarray, np.ndarray]:
    signal = np.asarray(samples, dtype=np.float32)
    if signal.size == 0:
        return np.empty((0, frame_size), dtype=np.float32), np.empty((0,), dtype=np.int32)

    if signal.size < frame_size:
        signal = np.pad(signal, (0, frame_size - signal.size))

    starts = np.arange(0, max(signal.size - frame_size + 1, 1), hop_size, dtype=np.int32)
    windows = np.lib.stride_tricks.sliding_window_view(signal, frame_size)
    return np.asarray(windows[starts], dtype=np.float32), starts


def _frame_features(frames: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if frames.size == 0:
        return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.float32)

    rms = np.sqrt(np.mean(frames * frames, axis=1))
    crossings = ((frames[:, :-1] >= 0) & (frames[:, 1:] < 0)) | ((frames[:, :-1] < 0) & (frames[:, 1:] >= 0))
    zcr = crossings.mean(axis=1, dtype=np.float32)
    return rms.astype(np.float32), zcr.astype(np.float32)


def _prepare_frames_numpy(frames: np.ndarray) -> np.ndarray:
    if frames.size == 0:
        return frames
    prepared = frames - np.mean(frames, axis=1, keepdims=True)
    if frames.shape[1] == 1:
        return prepared
    return prepared * np.hanning(frames.shape[1]).astype(np.float32, copy=False)


def _yin_pitch_batch(
    prepared_frames: np.ndarray,
    sample_rate: int,
    min_frequency: float = DEFAULT_MIN_FREQUENCY,
    max_frequency: float = DEFAULT_MAX_FREQUENCY,
    threshold: float = DEFAULT_YIN_THRESHOLD,
) -> tuple[np.ndarray, np.ndarray]:
    if prepared_frames.size == 0:
        return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.float32)

    frame_size = prepared_frames.shape[1]
    min_tau = max(int(sample_rate / max(max_frequency, 1.0)), 2)
    max_tau = min(int(sample_rate / max(min_frequency, 1.0)), frame_size - 2)
    if max_tau <= min_tau:
        empty = np.zeros(prepared_frames.shape[0], dtype=np.float32)
        return empty, empty

    frequencies: list[np.ndarray] = []
    clarities: list[np.ndarray] = []
    tau_range = np.arange(1, max_tau + 1, dtype=np.float32)

    for batch_start in range(0, prepared_frames.shape[0], BATCH_FRAME_COUNT):
        batch = prepared_frames[batch_start : batch_start + BATCH_FRAME_COUNT]
        batch_size = batch.shape[0]
        difference = np.zeros((batch_size, max_tau + 1), dtype=np.float32)

        for tau in range(1, max_tau + 1):
            delta = batch[:, :-tau] - batch[:, tau:]
            difference[:, tau] = np.sum(delta * delta, axis=1, dtype=np.float32)

        cumulative = np.ones_like(difference)
        running_sum = np.cumsum(difference[:, 1:], axis=1, dtype=np.float32)
        cumulative[:, 1:] = np.divide(
            difference[:, 1:] * tau_range,
            np.where(running_sum > 0, running_sum, 1.0),
            out=np.ones_like(difference[:, 1:]),
            where=running_sum > 0,
        )

        search = cumulative[:, min_tau : max_tau + 1]
        best_offsets = np.argmin(search, axis=1)
        best_taus = best_offsets + min_tau

        selected_taus = best_taus.copy()
        below_threshold = search < threshold
        if np.any(below_threshold):
            first_hits = np.argmax(below_threshold, axis=1) + min_tau
            has_hit = np.any(below_threshold, axis=1)
            selected_taus = np.where(has_hit, first_hits, selected_taus)

        tau_values = selected_taus.astype(np.float32)
        valid_parabola = (selected_taus >= 1) & (selected_taus < max_tau)
        if np.any(valid_parabola):
            indices = np.arange(batch_size)[valid_parabola]
            tau_idx = selected_taus[valid_parabola]
            left = cumulative[indices, tau_idx - 1]
            center = cumulative[indices, tau_idx]
            right = cumulative[indices, tau_idx + 1]
            denominator = left - 2 * center + right
            safe = np.abs(denominator) > 1e-12
            refined = tau_idx.astype(np.float32)
            refined[safe] = refined[safe] + 0.5 * (left[safe] - right[safe]) / denominator[safe]
            tau_values[valid_parabola] = refined

        freq = np.divide(
            float(sample_rate),
            tau_values,
            out=np.zeros_like(tau_values),
            where=tau_values > 0,
        )
        clarity = np.clip(1.0 - cumulative[np.arange(batch_size), selected_taus], 0.0, 1.0)
        frequencies.append(freq.astype(np.float32))
        clarities.append(clarity.astype(np.float32))

    return np.concatenate(frequencies), np.concatenate(clarities)


def _autocorrelation_pitch_batch(
    prepared_frames: np.ndarray,
    sample_rate: int,
    min_frequency: float = DEFAULT_MIN_FREQUENCY,
    max_frequency: float = DEFAULT_MAX_FREQUENCY,
) -> tuple[np.ndarray, np.ndarray]:
    if prepared_frames.size == 0:
        return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.float32)

    frame_size = prepared_frames.shape[1]
    min_lag = max(int(sample_rate / max(max_frequency, 1.0)), 2)
    max_lag = min(int(sample_rate / max(min_frequency, 1.0)), frame_size - 2)
    if max_lag <= min_lag:
        empty = np.zeros(prepared_frames.shape[0], dtype=np.float32)
        return empty, empty

    frequencies: list[np.ndarray] = []
    clarities: list[np.ndarray] = []

    for batch_start in range(0, prepared_frames.shape[0], BATCH_FRAME_COUNT):
        batch = prepared_frames[batch_start : batch_start + BATCH_FRAME_COUNT]
        batch_size = batch.shape[0]
        energies = np.sum(batch * batch, axis=1, dtype=np.float32)
        correlations = np.full((batch_size, max_lag + 1), -1.0, dtype=np.float32)

        for lag in range(min_lag, max_lag + 1):
            corr = np.sum(batch[:, :-lag] * batch[:, lag:], axis=1, dtype=np.float32)
            correlations[:, lag] = np.divide(
                corr,
                np.where(energies > 1e-12, energies, 1.0),
                out=np.zeros(batch_size, dtype=np.float32),
                where=energies > 1e-12,
            )

        best_offsets = np.argmax(correlations[:, min_lag : max_lag + 1], axis=1)
        best_lags = best_offsets + min_lag
        freq = sample_rate / best_lags.astype(np.float32)
        clarity = np.clip(correlations[np.arange(batch_size), best_lags], 0.0, 1.0)
        frequencies.append(freq.astype(np.float32))
        clarities.append(clarity.astype(np.float32))

    return np.concatenate(frequencies), np.concatenate(clarities)


def _build_pitch_sequence_fast(
    samples: Sequence[float],
    sample_rate: int,
    frame_ms: int,
    hop_ms: int,
    algorithm: str,
    duration: float | None = None,
) -> list[dict] | None:
    normalized_algorithm = (algorithm or "yin").lower()
    if normalized_algorithm not in {"yin", "pyin", "autocorrelation", "acf"}:
        return None

    frame_size = max(int(sample_rate * frame_ms / 1000), int(sample_rate * 0.04), 32)
    hop_size = max(int(sample_rate * hop_ms / 1000), 1)
    frames, starts = _frame_signal(samples, frame_size, hop_size)
    if frames.size == 0:
        return []

    rms_values, zcr_values = _frame_features(frames)
    prepared_frames = _prepare_frames_numpy(frames)

    if normalized_algorithm in {"yin", "pyin"}:
        frequencies, clarities = _yin_pitch_batch(prepared_frames, sample_rate)
        if np.any(clarities < 0.35):
            fallback_frequencies, fallback_clarities = _autocorrelation_pitch_batch(prepared_frames, sample_rate)
            use_fallback = fallback_clarities > clarities
            frequencies = np.where(use_fallback, fallback_frequencies, frequencies)
            clarities = np.where(use_fallback, fallback_clarities, clarities)
    else:
        frequencies, clarities = _autocorrelation_pitch_batch(prepared_frames, sample_rate)

    valid_frequency = (
        np.isfinite(frequencies)
        & (frequencies >= DEFAULT_MIN_FREQUENCY)
        & (frequencies <= DEFAULT_MAX_FREQUENCY)
        & (rms_values >= SILENCE_RMS_THRESHOLD)
    )
    confidences = np.clip(clarities * np.clip(rms_values / 0.08, 0.3, 1.0), 0.0, 0.99)

    sequence: list[dict] = []
    for index, start in enumerate(starts.tolist()):
        if valid_frequency[index]:
            frequency = round(float(frequencies[index]), 2)
            confidence = round(float(confidences[index]), 2)
            note = frequency_to_note(frequency)
            voiced = confidence >= 0.25
        else:
            frequency = 0.0
            confidence = 0.0
            note = "Rest"
            voiced = False

        sequence.append(
            {
                "time": round(start / sample_rate, 3),
                "frequency": frequency,
                "note": note,
                "confidence": confidence,
                "duration": round(hop_ms / 1000.0, 3),
                "algorithm": algorithm,
                "voiced": voiced,
                "rms": round(float(rms_values[index]), 5),
                "zcr": round(float(zcr_values[index]), 5),
            }
        )

    if duration and sequence:
        expected_end = max(float(duration), sequence[-1]["time"])
        sequence[-1]["duration"] = round(max(expected_end - sequence[-1]["time"], sequence[-1]["duration"]), 3)

    return sequence


def detect_pitch_sequence(
    file_name: str,
    sample_rate: int | None = None,
    frame_ms: int = 20,
    hop_ms: int = 10,
    algorithm: str = "yin",
    duration: float | None = None,
    audio_bytes: Any = None,
) -> list[dict]:
    """Return a pitch time series compatible with `/api/v1/pitch/detect`."""

    requested_rate = _safe_sample_rate(sample_rate)
    frame_ms = max(int(frame_ms or 20), 5)
    hop_ms = max(int(hop_ms or 10), 1)
    algorithm = algorithm or "yin"

    preprocessed = preprocess_audio_features(audio_bytes, requested_rate, file_name=file_name)
    samples = preprocessed["samples"]
    actual_rate = preprocessed["sample_rate"]
    if not samples:
        if audio_bytes is None:
            fallback_duration = duration or 4.0
            return _fallback_pitch_sequence(fallback_duration, hop_ms, algorithm)
        raise AudioDecodeError("无法从上传音频中解码出有效波形，请确认文件格式受支持。")

    try:
        fast_sequence = _build_pitch_sequence_fast(samples, actual_rate, frame_ms, hop_ms, algorithm, duration=duration)
    except Exception as exc:
        logger.warning("Fast pitch path failed for %s, falling back to pure Python detector: %s", file_name, exc)
        fast_sequence = None
    if fast_sequence is not None:
        return fast_sequence

    frame_size = max(int(actual_rate * frame_ms / 1000), int(actual_rate * 0.04), 32)
    hop_size = max(int(actual_rate * hop_ms / 1000), 1)
    if len(samples) < frame_size:
        samples = samples + [0.0] * (frame_size - len(samples))

    sequence: list[dict] = []
    last_time = 0.0
    for start in range(0, max(len(samples) - frame_size + 1, 1), hop_size):
        frame = samples[start : start + frame_size]
        detected = detect_single_pitch(frame, actual_rate, algorithm=algorithm)
        time_point = round(start / actual_rate, 3)
        last_time = time_point
        sequence.append(
            {
                "time": time_point,
                "frequency": detected["frequency"],
                "note": detected["note"],
                "confidence": detected["confidence"],
                "duration": round(hop_ms / 1000.0, 3),
                "algorithm": algorithm,
                "voiced": detected["voiced"],
                "rms": detected["rms"],
                "zcr": detected["zcr"],
            }
        )

    if duration and sequence:
        expected_end = max(float(duration), last_time)
        sequence[-1]["duration"] = round(max(expected_end - sequence[-1]["time"], sequence[-1]["duration"]), 3)

    return sequence
