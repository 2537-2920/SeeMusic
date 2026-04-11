"""Score service helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.core.score.score_utils import (
    apply_operations,
    create_score,
    get_score,
    redo_score as _redo_score,
    save_score,
    undo_score as _undo_score,
)
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence


def create_score_from_pitch_sequence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return build_score_from_pitch_sequence(
        payload["pitch_sequence"],
        tempo=payload.get("tempo", 120),
        time_signature=payload.get("time_signature", "4/4"),
        key_signature=payload.get("key_signature", "C"),
    )


def edit_score(score_id: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    score = get_score(score_id)
    updated = apply_operations(score, operations)
    return save_score(updated)


def export_score(score_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    score = get_score(score_id)
    return {
        "score_id": score_id,
        "format": payload.get("format", "pdf"),
        "download_url": f"https://example.com/download/{score_id}.{payload.get('format', 'pdf')}",
        "score_title": score.get("title", "untitled"),
    }


def undo_score_action(score_id: str) -> Dict[str, Any]:
    return _undo_score(score_id)


def redo_score_action(score_id: str) -> Dict[str, Any]:
    return _redo_score(score_id)


undo_score = undo_score_action
redo_score = redo_score_action
