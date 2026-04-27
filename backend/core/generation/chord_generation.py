"""Chord generation built on top of the guitar lead-sheet engine."""

from __future__ import annotations

from typing import Any

from backend.core.guitar.lead_sheet import generate_guitar_lead_sheet


def generate_chord_sequence(
    key: str,
    tempo: int,
    style: str,
    melody: list[dict[str, Any]],
    time_signature: str = "4/4",
) -> dict[str, Any]:
    return generate_guitar_lead_sheet(
        key=key,
        tempo=tempo,
        style=style,
        melody=melody,
        time_signature=time_signature,
        title="Generated Chord Track",
    )

