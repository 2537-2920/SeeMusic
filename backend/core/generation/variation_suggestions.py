"""Variation suggestion stubs."""

from __future__ import annotations


def generate_variation_suggestions(score_id: str, style: str, difficulty: str) -> dict:
    suggestions = [
        {
            "type": "rhythm_change",
            "description": "将第 2 小节节奏改为切分音",
        },
        {
            "type": "melody_ornament",
            "description": "在长音位置加入倚音与滑音",
        },
    ]
    return {"score_id": score_id, "style": style, "difficulty": difficulty, "suggestions": suggestions}

