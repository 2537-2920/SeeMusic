"""Shared jianpu intermediate representation helpers."""

from __future__ import annotations

from typing import Any

from backend.core.score.note_mapping import parse_time_signature


def _key_display(key_signature: str) -> str:
    text = str(key_signature or "C").strip() or "C"
    return text[:-1] if text.endswith("m") else text


def _mode_text(key_signature: str) -> str:
    return "小调" if str(key_signature or "").endswith("m") else "大调"


def _target_measures_per_line(measures: list[dict[str, Any]], time_signature: str) -> int:
    total = len(measures)
    if total <= 4:
        return max(total, 1)
    numerator, denominator = parse_time_signature(time_signature)
    average_note_count = (
        sum(len(list(measure.get("notes") or [])) for measure in measures) / total if total else 0.0
    )
    dense_measure_count = sum(1 for measure in measures if len(list(measure.get("notes") or [])) >= 6)

    if denominator == 8 and numerator >= 6 and numerator % 3 == 0:
        base = 3 if total <= 8 else 4
    elif time_signature == "3/4":
        base = 4
    else:
        base = 4 if total <= 12 else 5

    if average_note_count >= 5 or dense_measure_count >= max(total // 2, 2):
        base = max(2, base - 1)
    return max(1, min(base, total))


def build_jianpu_lines(
    measures: list[dict[str, Any]],
    *,
    time_signature: str,
) -> list[dict[str, Any]]:
    if not measures:
        return []

    measures_per_line = _target_measures_per_line(measures, time_signature)
    lines: list[dict[str, Any]] = []
    for index in range(0, len(measures), measures_per_line):
        line_measures = measures[index : index + measures_per_line]
        lines.append(
            {
                "line_no": len(lines) + 1,
                "measure_start": int(line_measures[0].get("measure_no") or index + 1),
                "measure_end": int(line_measures[-1].get("measure_no") or index + len(line_measures)),
                "measures": line_measures,
            }
        )
    return lines


def build_jianpu_pages(
    lines: list[dict[str, Any]],
    *,
    lines_per_page: int = 5,
) -> list[dict[str, Any]]:
    if not lines:
        return []

    pages: list[dict[str, Any]] = []
    page_size = max(int(lines_per_page or 5), 1)
    for index in range(0, len(lines), page_size):
        page_lines = lines[index : index + page_size]
        pages.append(
            {
                "page_no": len(pages) + 1,
                "line_start": int(page_lines[0].get("line_no") or index + 1),
                "line_end": int(page_lines[-1].get("line_no") or index + len(page_lines)),
                "measure_start": int(page_lines[0].get("measure_start") or 1),
                "measure_end": int(page_lines[-1].get("measure_end") or page_lines[-1].get("measure_start") or 1),
                "lines": page_lines,
            }
        )
    return pages


def build_jianpu_note_ir(
    note: dict[str, Any],
    *,
    annotation_text: str = "",
    annotation_hint: str = "",
    fingering_text: str = "",
    fingering_hint: str = "",
) -> dict[str, Any]:
    return {
        "note_id": note.get("note_id"),
        "pitch": note.get("pitch"),
        "measure_no": int(note.get("measure_no") or 1),
        "start_beat": float(note.get("start_beat") or 1.0),
        "beats": float(note.get("beats") or note.get("display_beats") or 1.0),
        "display_beats": float(note.get("display_beats") or note.get("beats") or 1.0),
        "degree_display": note.get("degree_display") or "0",
        "degree_no": int(note.get("degree_no") or 0),
        "accidental": note.get("accidental"),
        "octave_marks": {
            "above": int((note.get("octave_marks") or {}).get("above") or 0),
            "below": int((note.get("octave_marks") or {}).get("below") or 0),
        },
        "is_rest": bool(note.get("is_rest")),
        "technique_tags": list(note.get("technique_tags") or []),
        "annotation_text": str(annotation_text or ""),
        "annotation_hint": str(annotation_hint or ""),
        "fingering_text": str(fingering_text or ""),
        "fingering_hint": str(fingering_hint or ""),
        "source_note": note,
    }


def build_jianpu_ir(
    *,
    title: str,
    key: str,
    tempo: int,
    time_signature: str,
    instrument_type: str,
    instrument_name: str,
    instrument_subtitle: str,
    instrument_range: str,
    instrument_badge: str,
    measures: list[dict[str, Any]],
    statistics: dict[str, Any] | None = None,
    annotation_layers: list[str] | None = None,
    layout_mode: str = "preview",
    lines_per_page: int = 5,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lines = build_jianpu_lines(measures, time_signature=time_signature)
    pages = build_jianpu_pages(lines, lines_per_page=lines_per_page)
    note_count = sum(len(list(measure.get("notes") or [])) for measure in measures)

    return {
        "meta": {
            "title": title,
            "key_signature": key,
            "key_display": _key_display(key),
            "mode_text": _mode_text(key),
            "time_signature": time_signature,
            "tempo": int(tempo),
            "instrument_type": instrument_type,
            "instrument_name": instrument_name,
            "instrument_subtitle": instrument_subtitle,
            "instrument_range": instrument_range,
            "instrument_badge": instrument_badge,
            **dict(extra_meta or {}),
        },
        "statistics": {
            "measure_count": len(measures),
            "note_count": note_count,
            **dict(statistics or {}),
        },
        "annotation_layers": list(annotation_layers or ["basic", "fingering", "technique", "debug"]),
        "layout_mode": str(layout_mode or "preview"),
        "measures": measures,
        "lines": lines,
        "pages": pages,
    }
