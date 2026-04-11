"""Export utility helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.core.score.note_mapping import beats_per_measure, beats_to_seconds


def build_export_files(resource_id: str, formats: list[str]) -> list[dict]:
    return [
        {
            "format": fmt,
            "download_url": f"https://example.com/download/{resource_id}.{fmt}",
            "expires_in": 3600,
        }
        for fmt in formats
    ]


def build_score_export_payload(
    score: Dict[str, Any],
    export_format: str,
    page_size: str = "A4",
    with_annotations: bool = True,
) -> Dict[str, Any]:
    if export_format == "midi":
        manifest = _build_midi_manifest(score)
    else:
        manifest = _build_visual_manifest(score, export_format, page_size, with_annotations)
    return {
        "score_id": score["score_id"],
        "format": export_format,
        "file_name": f"{score['score_id']}.{export_format}",
        "download_url": None,
        "manifest": manifest,
    }


def _build_midi_manifest(score: Dict[str, Any]) -> Dict[str, Any]:
    measure_length = beats_per_measure(score["time_signature"])
    events: List[Dict[str, Any]] = []

    for measure in score.get("measures", []):
        for note in measure.get("notes", []):
            if note.get("is_rest"):
                continue
            absolute_beats = ((measure["measure_no"] - 1) * measure_length) + (float(note["start_beat"]) - 1.0)
            events.append(
                {
                    "event": "note",
                    "note_id": note["note_id"],
                    "pitch": note["pitch"],
                    "frequency": note["frequency"],
                    "start_seconds": beats_to_seconds(absolute_beats, score["tempo"]),
                    "duration_seconds": beats_to_seconds(note["beats"], score["tempo"]),
                    "measure_no": measure["measure_no"],
                    "start_beat": note["start_beat"],
                    "beats": note["beats"],
                }
            )

    return {
        "kind": "midi",
        "tempo": score["tempo"],
        "time_signature": score["time_signature"],
        "key_signature": score["key_signature"],
        "tracks": [
            {
                "track_id": "melody",
                "events": events,
            }
        ],
    }


def _build_visual_manifest(
    score: Dict[str, Any],
    export_format: str,
    page_size: str,
    with_annotations: bool,
) -> Dict[str, Any]:
    measures_per_system = 4
    systems_per_page = 2
    pages: List[Dict[str, Any]] = []
    current_page: Dict[str, Any] | None = None
    current_system: Dict[str, Any] | None = None

    for index, measure in enumerate(score.get("measures", []), start=1):
        if (index - 1) % measures_per_system == 0:
            if current_system and current_page is not None:
                current_page["systems"].append(current_system)
            if current_page is None or len(current_page["systems"]) >= systems_per_page:
                if current_page is not None:
                    pages.append(current_page)
                current_page = {"page_no": len(pages) + 1, "systems": []}
            current_system = {
                "system_no": len(current_page["systems"]) + 1,
                "measure_range": [measure["measure_no"], measure["measure_no"]],
                "measures": [],
            }

        layout_notes = [
            {
                "note_id": note["note_id"],
                "pitch": note["pitch"],
                "duration": note["duration"],
                "beats": note["beats"],
                "start_beat": note["start_beat"],
                "x_ratio": round((float(note["start_beat"]) - 1.0) / max(measure["total_beats"], 1), 3),
                "is_rest": note["is_rest"],
            }
            for note in measure.get("notes", [])
        ]
        if current_system is None:
            current_system = {
                "system_no": 1,
                "measure_range": [measure["measure_no"], measure["measure_no"]],
                "measures": [],
            }
        current_system["measure_range"][1] = measure["measure_no"]
        current_system["measures"].append(
            {
                "measure_no": measure["measure_no"],
                "total_beats": measure["total_beats"],
                "used_beats": measure["used_beats"],
                "notes": layout_notes,
            }
        )

    if current_system and current_page is not None:
        current_page["systems"].append(current_system)
    if current_page is not None:
        pages.append(current_page)

    return {
        "kind": export_format,
        "page_size": page_size,
        "with_annotations": with_annotations,
        "tempo": score["tempo"],
        "time_signature": score["time_signature"],
        "key_signature": score["key_signature"],
        "pages": pages,
    }
