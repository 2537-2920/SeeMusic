"""In-memory canonical score storage and MusicXML snapshot history helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.core.score.musicxml_utils import build_canonical_score_from_musicxml


SCORES: dict[str, dict[str, Any]] = {}


def snapshot_score(score: dict[str, Any]) -> dict[str, Any]:
    clone = deepcopy(score)
    clone.pop("undo_stack", None)
    clone.pop("redo_stack", None)
    return clone


def _prepare_score_for_storage(score: dict[str, Any]) -> dict[str, Any]:
    prepared = deepcopy(score)
    canonical = build_canonical_score_from_musicxml(
        str(prepared.get("musicxml") or ""),
        score_id=str(prepared.get("score_id") or ""),
        title=str(prepared.get("title") or "") or None,
        version=int(prepared.get("version", 1)),
        project_id=int(prepared["project_id"]) if prepared.get("project_id") is not None else None,
    )
    prepared.update(canonical)
    if prepared.get("project_id") is None:
        prepared.pop("project_id", None)
    prepared["undo_stack"] = deepcopy(prepared.get("undo_stack", []))
    prepared["redo_stack"] = deepcopy(prepared.get("redo_stack", []))
    return prepared


def create_score(
    *,
    musicxml: str,
    title: str | None = None,
    score_id: str | None = None,
    project_id: int | None = None,
    version: int = 1,
) -> dict[str, Any]:
    score = _prepare_score_for_storage(
        {
            "score_id": score_id,
            "project_id": project_id,
            "title": title,
            "version": version,
            "musicxml": musicxml,
            "undo_stack": [],
            "redo_stack": [],
        }
    )
    SCORES[score["score_id"]] = deepcopy(score)
    return snapshot_score(score)


def get_score(score_id: str) -> dict[str, Any]:
    if score_id not in SCORES:
        raise KeyError(f"score {score_id} not found")
    return snapshot_score(SCORES[score_id])


def get_score_state(score_id: str) -> dict[str, Any]:
    if score_id not in SCORES:
        raise KeyError(f"score {score_id} not found")
    return deepcopy(SCORES[score_id])


def reset_score_cache() -> None:
    SCORES.clear()


def save_score(score: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_score_for_storage(score)
    SCORES[prepared["score_id"]] = deepcopy(prepared)
    return snapshot_score(prepared)


def update_score_musicxml(score: dict[str, Any], musicxml: str) -> dict[str, Any]:
    working = _prepare_score_for_storage(score)
    working["undo_stack"].append(snapshot_score(working))
    working["redo_stack"] = []

    canonical = build_canonical_score_from_musicxml(
        musicxml,
        score_id=working["score_id"],
        title=working.get("title"),
        version=int(working.get("version", 1)) + 1,
        project_id=int(working["project_id"]) if working.get("project_id") is not None else None,
    )
    working.update(canonical)
    SCORES[working["score_id"]] = deepcopy(working)
    return snapshot_score(working)


def undo_score(score_id: str) -> dict[str, Any]:
    score = get_score_state(score_id)
    if not score.get("undo_stack"):
        return snapshot_score(score)

    previous_public_state = score["undo_stack"].pop()
    score["redo_stack"].append(snapshot_score(score))
    restored = _prepare_score_for_storage(
        {
            **previous_public_state,
            "undo_stack": score["undo_stack"],
            "redo_stack": score["redo_stack"],
        }
    )
    SCORES[score_id] = deepcopy(restored)
    return snapshot_score(restored)


def redo_score(score_id: str) -> dict[str, Any]:
    score = get_score_state(score_id)
    if not score.get("redo_stack"):
        return snapshot_score(score)

    next_public_state = score["redo_stack"].pop()
    score["undo_stack"].append(snapshot_score(score))
    restored = _prepare_score_for_storage(
        {
            **next_public_state,
            "undo_stack": score["undo_stack"],
            "redo_stack": score["redo_stack"],
        }
    )
    SCORES[score_id] = deepcopy(restored)
    return snapshot_score(restored)
