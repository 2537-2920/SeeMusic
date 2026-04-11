"""Frequency and note mapping helpers."""

from __future__ import annotations

import math

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def frequency_to_note(frequency: float) -> str:
    if frequency <= 0:
        return "Rest"
    midi = round(69 + 12 * math.log2(frequency / 440.0))
    name = NOTE_NAMES[midi % 12]
    octave = midi // 12 - 1
    return f"{name}{octave}"


def note_to_frequency(note: str) -> float:
    if note == "Rest":
        return 0.0
    name = note[:-1]
    octave = int(note[-1])
    midi = NOTE_NAMES.index(name) + (octave + 1) * 12
    return round(440.0 * (2 ** ((midi - 69) / 12)), 2)

