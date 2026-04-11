"""Rhythm scoring helpers."""

from __future__ import annotations


def score_rhythm(reference_beats: list[float], user_beats: list[float]) -> dict:
    paired = list(zip(reference_beats, user_beats))
    errors = []
    total_deviation = 0.0
    for ref, user in paired:
        deviation_ms = round((user - ref) * 1000, 2)
        total_deviation += abs(deviation_ms)
        if abs(deviation_ms) > 40:
            errors.append(
                {
                    "time": user,
                    "deviation_ms": deviation_ms,
                    "level": "slight" if abs(deviation_ms) <= 80 else "major",
                }
            )
    average = total_deviation / max(len(paired), 1)
    score = max(0, round(100 - average / 2))
    return {"score": score, "errors": errors}

