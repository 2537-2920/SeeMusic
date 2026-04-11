"""In-memory score storage, editing, and history helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
from uuid import uuid4

from backend.core.score.note_mapping import (
    beats_per_measure,
    beats_to_duration_label,
    duration_label_to_beats,
    frequency_to_note,
    note_to_frequency,
)


SCORES: Dict[str, Dict[str, Any]] = {}


def _snapshot(score: Dict[str, Any]) -> Dict[str, Any]:
    clone = deepcopy(score)
    clone.pop("undo_stack", None)
    clone.pop("redo_stack", None)
    return clone


def _normalize_note(note: Dict[str, Any], default_note_id: str | None = None) -> Dict[str, Any]:
    normalized = deepcopy(note)
    normalized["note_id"] = normalized.get("note_id") or default_note_id or f"n_{uuid4().hex[:8]}"
    normalized["is_rest"] = bool(normalized.get("is_rest") or normalized.get("pitch") == "Rest")

    if normalized["is_rest"]:
        normalized["pitch"] = "Rest"
        normalized["frequency"] = 0.0
    else:
        if normalized.get("frequency") is None and normalized.get("pitch"):
            normalized["frequency"] = note_to_frequency(str(normalized["pitch"]))
        elif normalized.get("pitch") in (None, "") and normalized.get("frequency") is not None:
            normalized["pitch"] = frequency_to_note(float(normalized["frequency"]))
        normalized["frequency"] = round(float(normalized.get("frequency", 0.0)), 2)
        normalized["pitch"] = str(normalized.get("pitch", "Rest"))

    beats = normalized.get("beats")
    if beats is None:
        beats = duration_label_to_beats(normalized.get("duration"))
    normalized["beats"] = round(max(float(beats), 0.25), 3)

    start_beat = float(normalized.get("start_beat", 1.0))
    normalized["start_beat"] = round(start_beat, 3)
    normalized["end_beat"] = round(normalized["start_beat"] + normalized["beats"], 3)
    normalized["duration"] = normalized.get("duration") or beats_to_duration_label(normalized["beats"])
    if "time" in normalized and normalized["time"] is not None:
        normalized["time"] = round(float(normalized["time"]), 3)
    if "duration_seconds" in normalized and normalized["duration_seconds"] is not None:
        normalized["duration_seconds"] = round(float(normalized["duration_seconds"]), 3)
    return normalized


def _normalize_measure(measure: Dict[str, Any], measure_no: int, total_beats: float) -> Dict[str, Any]:
    notes = [_normalize_note(note) for note in measure.get("notes", [])]
    notes.sort(key=lambda item: (item["start_beat"], item["note_id"]))
    return {
        "measure_no": measure_no,
        "notes": notes,
        "total_beats": total_beats,
        "used_beats": round(sum(note["beats"] for note in notes), 3),
    }


def _prepare_score_for_storage(score: Dict[str, Any]) -> Dict[str, Any]:
    prepared = deepcopy(score)
    prepared["score_id"] = prepared.get("score_id") or f"score_{uuid4().hex[:8]}"
    prepared["tempo"] = int(prepared.get("tempo", 120))
    prepared["time_signature"] = str(prepared.get("time_signature", "4/4"))
    prepared["key_signature"] = str(prepared.get("key_signature", "C"))
    prepared["version"] = int(prepared.get("version", 1))
    prepared["undo_stack"] = deepcopy(prepared.get("undo_stack", []))
    prepared["redo_stack"] = deepcopy(prepared.get("redo_stack", []))

    total_beats = beats_per_measure(prepared["time_signature"])
    measures = prepared.get("measures") or [{"measure_no": 1, "notes": []}]
    prepared["measures"] = [
        _normalize_measure(measure, index, total_beats)
        for index, measure in enumerate(sorted(measures, key=lambda item: item.get("measure_no", 0) or 0), start=1)
    ]
    prepared["measure_count"] = len(prepared["measures"])
    return prepared


def _ensure_measure(score: Dict[str, Any], measure_no: int) -> Dict[str, Any]:
    total_beats = beats_per_measure(score["time_signature"])
    while len(score["measures"]) < measure_no:
        score["measures"].append(
            {
                "measure_no": len(score["measures"]) + 1,
                "notes": [],
                "total_beats": total_beats,
                "used_beats": 0.0,
            }
        )
    return score["measures"][measure_no - 1]


def _find_note_location(score: Dict[str, Any], note_id: str) -> tuple[Dict[str, Any], int]:
    for measure in score["measures"]:
        for index, note in enumerate(measure.get("notes", [])):
            if note.get("note_id") == note_id:
                return measure, index
    raise ValueError(f"note {note_id} not found")


def _recalculate_score(score: Dict[str, Any]) -> Dict[str, Any]:
    total_beats = beats_per_measure(score["time_signature"])
    normalized_measures = []
    for index, measure in enumerate(score.get("measures", []), start=1):
        normalized_measures.append(_normalize_measure(measure, index, total_beats))
    score["measures"] = normalized_measures or [{"measure_no": 1, "notes": [], "total_beats": total_beats, "used_beats": 0.0}]
    score["measure_count"] = len(score["measures"])
    return score


def create_score(
    measures: List[Dict[str, Any]],
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str = "C",
) -> Dict[str, Any]:
    score = _prepare_score_for_storage(
        {
            "score_id": f"score_{uuid4().hex[:8]}",
            "tempo": tempo,
            "time_signature": time_signature,
            "key_signature": key_signature,
            "measures": measures,
            "version": 1,
            "undo_stack": [],
            "redo_stack": [],
        }
    )
    SCORES[score["score_id"]] = deepcopy(score)
    return _snapshot(score)


def get_score(score_id: str) -> Dict[str, Any]:
    if score_id not in SCORES:
        raise KeyError(f"score {score_id} not found")
    return deepcopy(SCORES[score_id])


def save_score(score: Dict[str, Any]) -> Dict[str, Any]:
    prepared = _prepare_score_for_storage(score)
    SCORES[prepared["score_id"]] = deepcopy(prepared)
    return _snapshot(prepared)


def apply_operations(score: Dict[str, Any], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    working = _prepare_score_for_storage(score)
    working["undo_stack"].append(_snapshot(working))
    working["redo_stack"] = []

    for operation in operations:
        op_type = operation.get("type")
        if op_type == "update_time_signature":
            working["time_signature"] = str(operation.get("value", working["time_signature"]))
        elif op_type == "update_key_signature":
            working["key_signature"] = str(operation.get("value", working["key_signature"]))
        elif op_type == "update_tempo":
            working["tempo"] = int(operation.get("value", working["tempo"]))
        elif op_type == "add_note":
            measure_no = max(int(operation.get("measure_no", 1)), 1)
            measure = _ensure_measure(working, measure_no)
            note_payload = deepcopy(operation.get("note") or {})
            note_payload["start_beat"] = float(note_payload.get("start_beat", operation.get("beat", 1.0)))
            measure["notes"].append(_normalize_note(note_payload))
        elif op_type == "delete_note":
            measure, index = _find_note_location(working, str(operation.get("note_id")))
            measure["notes"].pop(index)
        elif op_type == "update_note":
            measure, index = _find_note_location(working, str(operation.get("note_id")))
            updated_note = deepcopy(measure["notes"][index])
            updated_note.update(deepcopy(operation.get("note") or {}))
            if operation.get("beat") is not None:
                updated_note["start_beat"] = float(operation["beat"])
            measure["notes"][index] = _normalize_note(updated_note, default_note_id=updated_note["note_id"])
        else:
            raise ValueError(f"unsupported score operation: {op_type}")

    working["version"] = int(working.get("version", 1)) + 1
    return _recalculate_score(working)


def undo_score(score_id: str) -> Dict[str, Any]:
    score = get_score(score_id)
    if not score.get("undo_stack"):
        return _snapshot(score)

    previous_public_state = score["undo_stack"].pop()
    score["redo_stack"].append(_snapshot(score))
    restored = _prepare_score_for_storage(
        {
            **previous_public_state,
            "undo_stack": score["undo_stack"],
            "redo_stack": score["redo_stack"],
        }
    )
    SCORES[score_id] = deepcopy(restored)
    return _snapshot(restored)


def redo_score(score_id: str) -> Dict[str, Any]:
    score = get_score(score_id)
    if not score.get("redo_stack"):
        return _snapshot(score)

    next_public_state = score["redo_stack"].pop()
    score["undo_stack"].append(_snapshot(score))
    restored = _prepare_score_for_storage(
        {
            **next_public_state,
            "undo_stack": score["undo_stack"],
            "redo_stack": score["redo_stack"],
        }
    )
    SCORES[score_id] = deepcopy(restored)
    return _snapshot(restored)
