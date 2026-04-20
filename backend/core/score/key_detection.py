"""Key estimation and key-aware pitch spelling helpers."""

from __future__ import annotations

import math
from typing import Any

from backend.core.pitch.pitch_sequence_utils import is_note_event_item
from backend.core.score.note_mapping import frequency_to_note, note_to_midi


SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")
PITCH_CLASS_CANDIDATES = {
    0: ("C", "B#"),
    1: ("C#", "Db"),
    2: ("D",),
    3: ("D#", "Eb"),
    4: ("E", "Fb"),
    5: ("F", "E#"),
    6: ("F#", "Gb"),
    7: ("G",),
    8: ("G#", "Ab"),
    9: ("A",),
    10: ("A#", "Bb"),
    11: ("B", "Cb"),
}
ACCIDENTAL_TO_VALUE = {"": 0, "#": 1, "b": -1}
MAJOR_KEY_TO_FIFTHS = {
    "Cb": -7,
    "Gb": -6,
    "Db": -5,
    "Ab": -4,
    "Eb": -3,
    "Bb": -2,
    "F": -1,
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "C#": 7,
}
MINOR_KEY_TO_FIFTHS = {
    "Abm": -7,
    "Ebm": -6,
    "Bbm": -5,
    "Fm": -4,
    "Cm": -3,
    "Gm": -2,
    "Dm": -1,
    "Am": 0,
    "Em": 1,
    "Bm": 2,
    "F#m": 3,
    "C#m": 4,
    "G#m": 5,
    "D#m": 6,
    "A#m": 7,
}
CANONICAL_MAJOR_KEY_BY_TOKEN = {key.upper(): key for key in MAJOR_KEY_TO_FIFTHS}
CANONICAL_MINOR_KEY_BY_TOKEN = {key.upper(): key for key in MINOR_KEY_TO_FIFTHS}
MAJOR_PROFILE = (
    6.35,
    2.23,
    3.48,
    2.33,
    4.38,
    4.09,
    2.52,
    5.19,
    2.39,
    3.66,
    2.29,
    2.88,
)
MINOR_PROFILE = (
    6.33,
    2.68,
    3.52,
    5.38,
    2.60,
    3.53,
    2.54,
    4.75,
    3.98,
    2.69,
    3.34,
    3.17,
)


def normalize_key_signature_text(value: str | None, default: str = "C") -> str:
    fallback = default if default.endswith("m") else CANONICAL_MAJOR_KEY_BY_TOKEN.get(default.upper(), "C")
    if not value:
        return fallback
    compact = str(value).strip().replace(" ", "")
    if not compact:
        return fallback
    upper = compact.upper()
    if upper.endswith("M") and len(compact) > 1 and compact[-1].islower():
        return CANONICAL_MINOR_KEY_BY_TOKEN.get(upper, fallback)
    return CANONICAL_MAJOR_KEY_BY_TOKEN.get(upper, fallback)


def key_signature_to_fifths_and_mode(value: str | None) -> tuple[int, str]:
    canonical = normalize_key_signature_text(value)
    if canonical.endswith("m"):
        return int(MINOR_KEY_TO_FIFTHS.get(canonical, 0)), "minor"
    return int(MAJOR_KEY_TO_FIFTHS.get(canonical, 0)), "major"


def build_key_signature_step_map(key_signature: str | None) -> dict[str, int]:
    fifths, _ = key_signature_to_fifths_and_mode(key_signature)
    accidentals = {step: 0 for step in "ABCDEFG"}
    if fifths > 0:
        for step in SHARP_ORDER[:fifths]:
            accidentals[step] = 1
    elif fifths < 0:
        for step in FLAT_ORDER[: abs(fifths)]:
            accidentals[step] = -1
    return accidentals


def _duration_weight(item: dict[str, Any]) -> float:
    if is_note_event_item(item):
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        return max(end - start, 0.05)
    duration = float(item.get("duration") or 0.0)
    if duration > 0:
        return duration
    return 0.05


def _resolved_note(item: dict[str, Any]) -> str:
    note = str(item.get("note") or "").strip()
    if note:
        return note
    if is_note_event_item(item):
        frequency = float(item.get("frequency_avg") or 0.0)
    else:
        frequency = float(item.get("frequency") or 0.0)
    return frequency_to_note(frequency)


def _confidence_weight(item: dict[str, Any]) -> float:
    confidence = item.get("confidence")
    if confidence is None:
        return 1.0
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(value):
        return 1.0
    return max(0.5, min(value, 1.0))


def _collect_pitch_statistics(pitch_sequence: list[dict[str, Any]] | None) -> dict[str, Any]:
    histogram = [0.0] * 12
    first_pitch_class: int | None = None
    last_pitch_class: int | None = None
    longest_pitch_class: int | None = None
    longest_weight = -1.0

    items = sorted(
        list(pitch_sequence or []),
        key=lambda item: float(item.get("start", item.get("time", 0.0))),
    )
    for item in items:
        note = _resolved_note(item)
        midi = note_to_midi(note)
        if midi is None:
            continue
        weight = _duration_weight(item) * _confidence_weight(item)
        if weight <= 0:
            continue
        pitch_class = int(midi % 12)
        histogram[pitch_class] += weight
        if first_pitch_class is None:
            first_pitch_class = pitch_class
        last_pitch_class = pitch_class
        if weight > longest_weight:
            longest_weight = weight
            longest_pitch_class = pitch_class

    total_weight = sum(histogram)
    normalized = [value / total_weight for value in histogram] if total_weight > 0 else histogram
    return {
        "histogram": histogram,
        "normalized_histogram": normalized,
        "total_weight": total_weight,
        "first_pitch_class": first_pitch_class,
        "last_pitch_class": last_pitch_class,
        "longest_pitch_class": longest_pitch_class,
    }


def _rotate_profile(profile: tuple[float, ...], tonic_pitch_class: int) -> list[float]:
    total = sum(profile) or 1.0
    return [profile[(pitch_class - tonic_pitch_class) % 12] / total for pitch_class in range(12)]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _tonic_pitch_class(key_signature: str) -> int:
    tonic = key_signature[:-1] if key_signature.endswith("m") else key_signature
    midi = note_to_midi(f"{tonic}4")
    if midi is None:
        return 0
    return int(midi % 12)


def analyze_key_signature(
    pitch_sequence: list[dict[str, Any]] | None,
    *,
    fallback_key_signature: str = "C",
) -> dict[str, Any]:
    fallback = normalize_key_signature_text(fallback_key_signature, default="C")
    stats = _collect_pitch_statistics(pitch_sequence)
    if stats["total_weight"] <= 0:
        fifths, mode = key_signature_to_fifths_and_mode(fallback)
        tonic = fallback[:-1] if fallback.endswith("m") else fallback
        return {
            "key_signature": fallback,
            "tonic": tonic,
            "mode": mode,
            "fifths": fifths,
            "confidence": 0.0,
            "candidates": [{"key_signature": fallback, "mode": mode, "score": 0.0}],
        }

    candidates: list[dict[str, Any]] = []
    for key_signature, fifths in MAJOR_KEY_TO_FIFTHS.items():
        tonic_pitch_class = _tonic_pitch_class(key_signature)
        rotated = _rotate_profile(MAJOR_PROFILE, tonic_pitch_class)
        score = _cosine_similarity(stats["normalized_histogram"], rotated)
        if stats["last_pitch_class"] == tonic_pitch_class:
            score += 0.18
        if stats["longest_pitch_class"] == tonic_pitch_class:
            score += 0.08
        if stats["first_pitch_class"] == tonic_pitch_class:
            score += 0.03
        candidates.append(
            {
                "key_signature": key_signature,
                "tonic": key_signature,
                "mode": "major",
                "fifths": fifths,
                "score": score,
            }
        )

    for key_signature, fifths in MINOR_KEY_TO_FIFTHS.items():
        tonic = key_signature[:-1]
        tonic_pitch_class = _tonic_pitch_class(key_signature)
        rotated = _rotate_profile(MINOR_PROFILE, tonic_pitch_class)
        score = _cosine_similarity(stats["normalized_histogram"], rotated)
        if stats["last_pitch_class"] == tonic_pitch_class:
            score += 0.2
        if stats["longest_pitch_class"] == tonic_pitch_class:
            score += 0.09
        if stats["first_pitch_class"] == tonic_pitch_class:
            score += 0.04
        candidates.append(
            {
                "key_signature": key_signature,
                "tonic": tonic,
                "mode": "minor",
                "fifths": fifths,
                "score": score,
            }
        )

    ranked = sorted(candidates, key=lambda item: float(item["score"]), reverse=True)
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    margin = float(best["score"]) - float(second["score"]) if second is not None else float(best["score"])
    confidence = max(0.0, min(0.99, margin * 4.0))
    return {
        "key_signature": str(best["key_signature"]),
        "tonic": str(best["tonic"]),
        "mode": str(best["mode"]),
        "fifths": int(best["fifths"]),
        "confidence": round(confidence, 2),
        "candidates": [
            {
                "key_signature": str(candidate["key_signature"]),
                "mode": str(candidate["mode"]),
                "score": round(float(candidate["score"]), 4),
            }
            for candidate in ranked[:3]
        ],
    }


def detect_key_signature(
    pitch_sequence: list[dict[str, Any]] | None,
    *,
    fallback_key_signature: str = "C",
) -> str:
    return str(
        analyze_key_signature(
            pitch_sequence,
            fallback_key_signature=fallback_key_signature,
        )["key_signature"]
    )


def _accidental_for_note_name(note_name: str) -> str:
    if len(note_name) > 1 and note_name[1] in {"#", "b"}:
        return note_name[1]
    return ""


def _candidate_octave(note_name: str, midi: int, base_octave: int) -> int:
    for octave in (base_octave - 1, base_octave, base_octave + 1):
        if note_to_midi(f"{note_name}{octave}") == midi:
            return octave
    return base_octave


def respell_note_for_key(note: str, key_signature: str | None) -> str:
    midi = note_to_midi(note)
    if midi is None:
        return "Rest"

    base_octave = midi // 12 - 1
    pitch_class = int(midi % 12)
    key_map = build_key_signature_step_map(key_signature)
    fifths, _ = key_signature_to_fifths_and_mode(key_signature)
    key_direction = 1 if fifths > 0 else -1 if fifths < 0 else 0
    original_accidental = _accidental_for_note_name(str(note))
    original_direction = ACCIDENTAL_TO_VALUE.get(original_accidental, 0)

    def candidate_sort_key(note_name: str) -> tuple[int, int, int, int]:
        accidental = _accidental_for_note_name(note_name)
        accidental_value = ACCIDENTAL_TO_VALUE.get(accidental, 0)
        expected_value = key_map.get(note_name[0], 0)
        distance_to_key = abs(accidental_value - expected_value)

        if accidental_value == 0:
            direction_penalty = 0
        elif key_direction == 0:
            direction_penalty = 0 if accidental_value == original_direction else 1
        else:
            direction_penalty = 0 if accidental_value == key_direction else 1

        accidental_penalty = 0 if accidental_value == 0 else 1
        original_penalty = 0 if accidental_value == original_direction else 1
        return distance_to_key, direction_penalty, accidental_penalty, original_penalty

    chosen = min(PITCH_CLASS_CANDIDATES[pitch_class], key=candidate_sort_key)
    return f"{chosen}{_candidate_octave(chosen, midi, base_octave)}"


def respell_pitch_sequence_for_key(
    pitch_sequence: list[dict[str, Any]] | None,
    key_signature: str | None,
) -> list[dict[str, Any]]:
    resolved_key = normalize_key_signature_text(key_signature, default="C")
    respelled: list[dict[str, Any]] = []
    for item in list(pitch_sequence or []):
        updated = dict(item)
        note = _resolved_note(updated)
        if note and note != "Rest":
            updated["note"] = respell_note_for_key(note, resolved_key)
        respelled.append(updated)
    return respelled
