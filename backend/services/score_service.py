"""Score service helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.export.export_utils import build_score_export_payload
from backend.core.score.score_utils import (
    apply_operations,
    get_score,
    redo_score as _redo_score,
    save_score,
    undo_score as _undo_score,
)
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence


class ScoreServiceError(Exception):
    """Base class for score service errors."""


class ScoreNotFoundError(ScoreServiceError):
    """Raised when the requested score does not exist."""


class ScoreOperationError(ScoreServiceError):
    """Raised when a score operation payload is invalid."""


def _load_score(score_id: str) -> Dict[str, Any]:
    try:
        return get_score(score_id)
    except KeyError as exc:
        raise ScoreNotFoundError(f"score {score_id} not found") from exc


def create_score_from_pitch_sequence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return build_score_from_pitch_sequence(
        payload["pitch_sequence"],
        tempo=payload.get("tempo", 120),
        time_signature=payload.get("time_signature", "4/4"),
        key_signature=payload.get("key_signature", "C"),
    )


def edit_score(score_id: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    score = _load_score(score_id)
    try:
        updated = apply_operations(score, operations)
    except ValueError as exc:
        raise ScoreOperationError(str(exc)) from exc
    return save_score(updated)


def export_score(score_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    score = _load_score(score_id)
    export_format = str(payload.get("format", "pdf"))
    return build_score_export_payload(
        score,
        export_format=export_format,
        page_size=str(payload.get("page_size", "A4")),
        with_annotations=bool(payload.get("with_annotations", True)),
    )


def undo_score_action(score_id: str) -> Dict[str, Any]:
    try:
        return _undo_score(score_id)
    except KeyError as exc:
        raise ScoreNotFoundError(f"score {score_id} not found") from exc


def redo_score_action(score_id: str) -> Dict[str, Any]:
    try:
        return _redo_score(score_id)
    except KeyError as exc:
        raise ScoreNotFoundError(f"score {score_id} not found") from exc


undo_score = undo_score_action
redo_score = redo_score_action
