"""Frequency, meter, and duration helpers for score generation."""

from __future__ import annotations

import math
import re
from typing import Iterable

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_ALIASES = {
    "Bb": "A#",
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
}
DURATION_TO_BEATS = {
    "sixteenth": 0.25,
    "eighth": 0.5,
    "dotted_eighth": 0.75,
    "quarter": 1.0,
    "dotted_quarter": 1.5,
    "half": 2.0,
    "dotted_half": 3.0,
    "whole": 4.0,
}
DEFAULT_ALLOWED_BEATS = tuple(sorted(DURATION_TO_BEATS.values()))


def frequency_to_midi(frequency: float) -> int | None:
    if frequency <= 0:
        return None
    return round(69 + 12 * math.log2(frequency / 440.0))


def midi_to_note(midi: int | None) -> str:
    if midi is None:
        return "Rest"
    name = NOTE_NAMES[midi % 12]
    octave = midi // 12 - 1
    return f"{name}{octave}"


def note_to_midi(note: str) -> int | None:
    if note == "Rest":
        return None
    match = re.fullmatch(r"([A-G](?:#|b)?)(-?\d+)", note)
    if not match:
        raise ValueError(f"unsupported note name: {note}")
    name, octave_text = match.groups()
    normalized_name = NOTE_ALIASES.get(name, name)
    if normalized_name not in NOTE_NAMES:
        raise ValueError(f"unsupported note name: {note}")
    octave = int(octave_text)
    return NOTE_NAMES.index(normalized_name) + (octave + 1) * 12


def midi_to_frequency(midi: int | None) -> float:
    if midi is None:
        return 0.0
    return round(440.0 * (2 ** ((midi - 69) / 12)), 2)


def frequency_to_note(frequency: float) -> str:
    return midi_to_note(frequency_to_midi(frequency))


def note_to_frequency(note: str) -> float:
    return midi_to_frequency(note_to_midi(note))


def parse_time_signature(time_signature: str) -> tuple[int, int]:
    numerator_text, denominator_text = time_signature.split("/", maxsplit=1)
    numerator = int(numerator_text)
    denominator = int(denominator_text)
    if numerator <= 0 or denominator <= 0:
        raise ValueError(f"invalid time signature: {time_signature}")
    return numerator, denominator


def beats_per_measure(time_signature: str) -> float:
    numerator, denominator = parse_time_signature(time_signature)
    return round(numerator * (4 / denominator), 3)


def seconds_to_beats(seconds: float, tempo: int) -> float:
    if tempo <= 0:
        raise ValueError("tempo must be positive")
    return round(seconds * tempo / 60, 3)


def beats_to_seconds(beats: float, tempo: int) -> float:
    if tempo <= 0:
        raise ValueError("tempo must be positive")
    return round(beats * 60 / tempo, 3)


def quantize_beats(beats: float, allowed_beats: Iterable[float] = DEFAULT_ALLOWED_BEATS) -> float:
    values = tuple(sorted(float(value) for value in allowed_beats))
    if not values:
        raise ValueError("allowed_beats cannot be empty")
    if beats <= 0:
        return values[0]
    return round(min(values, key=lambda candidate: (abs(candidate - beats), candidate)), 3)


def beats_to_duration_label(beats: float) -> str:
    quantized = quantize_beats(beats)
    for label, label_beats in DURATION_TO_BEATS.items():
        if abs(label_beats - quantized) < 1e-6:
            return label
    return "custom"


def duration_label_to_beats(duration: str | None) -> float:
    if not duration:
        return DURATION_TO_BEATS["quarter"]
    return DURATION_TO_BEATS.get(duration, DURATION_TO_BEATS["quarter"])
