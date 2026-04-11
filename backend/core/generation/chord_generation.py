"""Chord generation stubs."""

from __future__ import annotations

from typing import Any, Dict, List


def generate_chord_sequence(key: str, tempo: int, style: str, melody: List[Dict[str, Any]]) -> dict:
    chords = [
        {"time": 0.0, "symbol": f"{key}maj7"},
        {"time": 2.0, "symbol": f"{key}6"},
        {"time": 4.0, "symbol": f"{key}sus4"},
    ]
    return {"key": key, "tempo": tempo, "style": style, "chords": chords, "melody_size": len(melody)}

