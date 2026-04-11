"""In-memory score storage and editing helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
from uuid import uuid4


SCORES: Dict[str, Dict[str, Any]] = {}


def _snapshot(score: Dict[str, Any]) -> Dict[str, Any]:
    clone = deepcopy(score)
    clone.pop("undo_stack", None)
    clone.pop("redo_stack", None)
    return clone


def create_score(
    measures: List[Dict[str, Any]],
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str = "C",
) -> Dict[str, Any]:
    score_id = f"score_{uuid4().hex[:8]}"
    score = {
        "score_id": score_id,
        "tempo": tempo,
        "time_signature": time_signature,
        "key_signature": key_signature,
        "measures": measures,
        "version": 1,
        "undo_stack": [],
        "redo_stack": [],
    }
    SCORES[score_id] = deepcopy(score)
    return _snapshot(score)


def get_score(score_id: str) -> Dict[str, Any]:
    if score_id not in SCORES:
        raise KeyError(f"score {score_id} not found")
    return deepcopy(SCORES[score_id])


def save_score(score: Dict[str, Any]) -> Dict[str, Any]:
    SCORES[score["score_id"]] = deepcopy(score)
    return _snapshot(score)


def apply_operations(score: Dict[str, Any], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    working = deepcopy(score)
    working.setdefault("undo_stack", [])
    working.setdefault("redo_stack", [])
    working["undo_stack"].append(_snapshot(working))
    for operation in operations:
        op_type = operation.get("type")
        if op_type == "update_time_signature":
            working["time_signature"] = operation.get("value", working["time_signature"])
        elif op_type == "update_key_signature":
            working["key_signature"] = operation.get("value", working["key_signature"])
        elif op_type == "update_tempo":
            working["tempo"] = operation.get("value", working["tempo"])
        elif op_type == "add_note":
            measure_no = operation.get("measure_no", 1)
            note = operation.get("note", {})
            while len(working["measures"]) < measure_no:
                working["measures"].append({"measure_no": len(working["measures"]) + 1, "notes": []})
            working["measures"][measure_no - 1].setdefault("notes", []).append(
                {
                    "beat": operation.get("beat", 1),
                    **note,
                }
            )
        elif op_type == "delete_note":
            note_id = operation.get("note_id")
            for measure in working["measures"]:
                measure["notes"] = [note for note in measure.get("notes", []) if note.get("note_id") != note_id]
        elif op_type == "update_note":
            note_id = operation.get("note_id")
            for measure in working["measures"]:
                for note in measure.get("notes", []):
                    if note.get("note_id") == note_id:
                        note.update(operation.get("note", {}))
    working["version"] = working.get("version", 1) + 1
    working["redo_stack"] = []
    SCORES[working["score_id"]] = deepcopy(working)
    return _snapshot(working)


def undo_score(score_id: str) -> Dict[str, Any]:
    score = get_score(score_id)
    if not score.get("undo_stack"):
        return score
    previous = score["undo_stack"].pop()
    previous.setdefault("redo_stack", []).append(_snapshot(score))
    SCORES[score_id] = deepcopy(previous)
    return _snapshot(previous)


def redo_score(score_id: str) -> Dict[str, Any]:
    score = get_score(score_id)
    if not score.get("redo_stack"):
        return score
    next_state = score["redo_stack"].pop()
    next_state.setdefault("undo_stack", []).append(_snapshot(score))
    SCORES[score_id] = deepcopy(next_state)
    return _snapshot(next_state)

