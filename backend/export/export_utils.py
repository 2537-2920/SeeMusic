"""Export utility helpers."""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from PIL import Image, ImageDraw, ImageFont

from backend.core.score.note_mapping import beats_per_measure, beats_to_seconds, parse_time_signature

try:
    from reportlab.lib.pagesizes import A4, LETTER
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover - exercised in runtime environments without reportlab
    A4 = LETTER = None
    canvas = None


TICKS_PER_QUARTER = 480
PAGE_SIZES = {"A4": A4, "LETTER": LETTER}
NOTE_NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
DIATONIC_STEPS = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
MEASURES_PER_SYSTEM = 4
DEFAULT_PAGE_WIDTH = 1240.0
DEFAULT_PAGE_HEIGHT = 1754.0
PAGE_GAP = 48
PAPER_COLOR = "#fffdf8"
INK_COLOR = "#1f2933"
MUTED_COLOR = "#5b6472"
ACCENT_COLOR = "#8a5a2f"


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
    file_stem: str | None = None,
) -> Dict[str, Any]:
    if export_format == "midi":
        manifest = _build_midi_manifest(score)
    else:
        manifest = _build_visual_manifest(score, export_format, page_size, with_annotations)
    stem = file_stem or score["score_id"]
    return {
        "score_id": score["score_id"],
        "format": export_format,
        "file_name": f"{stem}.{export_format}",
        "download_url": None,
        "manifest": manifest,
    }



def write_score_export(
    score: Dict[str, Any],
    export_format: str,
    storage_dir: Path,
    page_size: str = "A4",
    with_annotations: bool = True,
    file_stem: str | None = None,
) -> Dict[str, Any]:
    payload = build_score_export_payload(
        score,
        export_format=export_format,
        page_size=page_size,
        with_annotations=with_annotations,
        file_stem=file_stem,
    )
    export_dir = storage_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    file_path = export_dir / payload["file_name"]

    if export_format == "midi":
        file_path.write_bytes(_build_midi_bytes(payload["manifest"]))
    elif export_format == "pdf":
        file_path.write_bytes(_build_pdf_bytes(score, payload["manifest"]))
    elif export_format == "png":
        file_path.write_bytes(_build_png_bytes(score, payload["manifest"]))
    else:
        raise ValueError(f"unsupported export format: {export_format}")

    payload["download_url"] = f"/storage/exports/{payload['file_name']}"
    payload["file_path"] = str(file_path)
    return payload



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
        "tracks": [{"track_id": "melody", "events": events}],
    }



def _build_visual_manifest(
    score: Dict[str, Any],
    export_format: str,
    page_size: str,
    with_annotations: bool,
) -> Dict[str, Any]:
    layout = _build_notation_layout(
        score,
        page_width=DEFAULT_PAGE_WIDTH,
        page_height=DEFAULT_PAGE_HEIGHT,
        page_size=page_size,
        with_annotations=with_annotations,
    )
    pages = [_manifest_page(page) for page in layout["pages"]]
    return {
        "kind": export_format,
        "page_size": page_size,
        "with_annotations": with_annotations,
        "tempo": score["tempo"],
        "time_signature": score["time_signature"],
        "key_signature": score["key_signature"],
        "pages": pages,
    }



def _build_midi_bytes(manifest: Dict[str, Any]) -> bytes:
    tempo = int(manifest["tempo"])
    numerator, denominator = parse_time_signature(str(manifest["time_signature"]))
    microseconds_per_quarter = int(60_000_000 / max(tempo, 1))

    track_events: list[tuple[int, bytes]] = [
        (0, b"\xFF\x51\x03" + microseconds_per_quarter.to_bytes(3, "big")),
        (0, b"\xFF\x58\x04" + bytes([numerator, _denominator_power(denominator), 24, 8])),
    ]

    for event in sorted(manifest["tracks"][0]["events"], key=lambda item: (item["start_seconds"], item["note_id"])):
        start_tick = _seconds_to_ticks(float(event["start_seconds"]), tempo)
        duration_tick = max(_seconds_to_ticks(float(event["duration_seconds"]), tempo), 1)
        note_number = _pitch_to_midi_number(str(event["pitch"]))
        track_events.append((start_tick, bytes([0x90, note_number, 96])))
        track_events.append((start_tick + duration_tick, bytes([0x80, note_number, 0])))

    track_events.sort(key=lambda item: (item[0], item[1][0]))
    track_data = bytearray()
    previous_tick = 0
    for tick, data in track_events:
        delta = tick - previous_tick
        track_data.extend(_encode_variable_length(delta))
        track_data.extend(data)
        previous_tick = tick
    track_data.extend(_encode_variable_length(0))
    track_data.extend(b"\xFF\x2F\x00")

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER)
    track = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    return header + track



def _build_pdf_bytes(score: Dict[str, Any], manifest: Dict[str, Any]) -> bytes:
    if canvas is None or A4 is None:
        raise RuntimeError("PDF export requires reportlab to be installed")

    page_size_name = str(manifest["page_size"]).upper()
    page_size = PAGE_SIZES.get(page_size_name, A4) or A4
    width, height = page_size
    layout = _build_notation_layout(
        score,
        page_width=float(width),
        page_height=float(height),
        page_size=page_size_name,
        with_annotations=bool(manifest.get("with_annotations", True)),
    )

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=page_size)
    renderer = _PdfRenderer(pdf, float(width), float(height))

    for page_index, page in enumerate(layout["pages"]):
        if page_index > 0:
            pdf.showPage()
            renderer = _PdfRenderer(pdf, float(width), float(height))
        _render_notation_page(renderer, score, page, bool(manifest.get("with_annotations", True)), show_page_frame=False)

    pdf.save()
    return buffer.getvalue()



def _build_png_bytes(score: Dict[str, Any], manifest: Dict[str, Any]) -> bytes:
    page_width = int(DEFAULT_PAGE_WIDTH)
    page_height = int(DEFAULT_PAGE_HEIGHT)
    layout = _build_notation_layout(
        score,
        page_width=float(page_width),
        page_height=float(page_height),
        page_size=str(manifest["page_size"]),
        with_annotations=bool(manifest.get("with_annotations", True)),
    )

    page_count = max(len(layout["pages"]), 1)
    image_height = (page_count * page_height) + max(page_count - 1, 0) * PAGE_GAP
    image = Image.new("RGB", (page_width, image_height), "#f3efe6")

    for page_index, page in enumerate(layout["pages"]):
        offset_y = page_index * (page_height + PAGE_GAP)
        renderer = _PngRenderer(image, offset_y=offset_y)
        _render_notation_page(renderer, score, page, bool(manifest.get("with_annotations", True)), show_page_frame=True)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

def _build_notation_layout(
    score: Dict[str, Any],
    *,
    page_width: float,
    page_height: float,
    page_size: str,
    with_annotations: bool,
) -> Dict[str, Any]:
    measures = list(score.get("measures") or [])
    if not measures:
        measures = [{"measure_no": 1, "notes": [], "total_beats": beats_per_measure(score["time_signature"]), "used_beats": 0.0}]

    numerator, denominator = parse_time_signature(str(score.get("time_signature", "4/4")))
    beam_group_span = 1.5 if denominator == 8 and numerator % 3 == 0 and numerator >= 6 else 1.0

    margin_x = max(54.0, round(page_width * 0.065, 2))
    top_margin = max(56.0, round(page_height * 0.05, 2))
    bottom_margin = max(42.0, round(page_height * 0.045, 2))
    header_height = max(88.0, round(page_height * 0.11, 2))
    staff_spacing = max(10.0, min(18.0, round(page_width * 0.012, 2)))
    system_height = max(138.0, round(staff_spacing * 9.8 + 56.0, 2))
    systems_per_page = max(int((page_height - top_margin - bottom_margin - header_height) // system_height), 1)

    measure_chunks = list(_chunked(measures, MEASURES_PER_SYSTEM))
    pages: List[Dict[str, Any]] = []
    system_counter = 0

    for page_no, system_groups in enumerate(_chunked(measure_chunks, systems_per_page), start=1):
        page_layout = {
            "page_no": page_no,
            "width": page_width,
            "height": page_height,
            "title": score.get("title") or "SeeMusic Lead Sheet",
            "subtitle": f"Score {score['score_id']}    Tempo {score['tempo']} BPM    Key {score['key_signature']}    Time {score['time_signature']}",
            "systems": [],
        }
        for system_index, system_measures in enumerate(system_groups, start=1):
            system_counter += 1
            system_top = top_margin + header_height + (system_index - 1) * system_height
            staff_top = system_top + 28.0
            staff_bottom = staff_top + (staff_spacing * 4)
            left_indent = max(70.0, round(page_width * 0.08, 2)) if system_counter == 1 else max(46.0, round(page_width * 0.055, 2))
            usable_width = page_width - (margin_x * 2) - left_indent
            measure_width = usable_width / max(len(system_measures), 1)
            system_layout = {
                "page_no": page_no,
                "system_no": system_counter,
                "system_index_in_page": system_index,
                "top": system_top,
                "staff_top": staff_top,
                "staff_bottom": staff_bottom,
                "staff_spacing": staff_spacing,
                "left": margin_x,
                "right": page_width - margin_x,
                "left_indent": left_indent,
                "show_signature": system_counter == 1,
                "measures": [],
                "ties": [],
            }
            flattened_notes: List[Dict[str, Any]] = []
            for measure_offset, measure in enumerate(system_measures):
                measure_start = margin_x + left_indent + (measure_offset * measure_width)
                measure_end = measure_start + measure_width
                measure_layout = {
                    "measure_no": measure["measure_no"],
                    "total_beats": float(measure.get("total_beats", beats_per_measure(score["time_signature"]))),
                    "used_beats": float(measure.get("used_beats", 0.0)),
                    "start_x": measure_start,
                    "end_x": measure_end,
                    "notes": [],
                    "beam_groups": [],
                }
                for note in measure.get("notes", []):
                    note_layout = _build_note_layout(note, measure_layout, staff_bottom, staff_spacing)
                    measure_layout["notes"].append(note_layout)
                    if note_layout.get("source_event_id"):
                        flattened_notes.append(note_layout)
                measure_layout["beam_groups"] = _build_measure_beams(
                    measure_layout["notes"],
                    beam_group_span=beam_group_span,
                    staff_spacing=staff_spacing,
                )
                system_layout["measures"].append(measure_layout)
            system_layout["ties"] = _build_system_ties(flattened_notes)
            page_layout["systems"].append(system_layout)
        pages.append(page_layout)

    return {
        "page_size": page_size,
        "with_annotations": with_annotations,
        "pages": pages,
    }



def _build_note_layout(
    note: Dict[str, Any],
    measure_layout: Dict[str, Any],
    staff_bottom: float,
    staff_spacing: float,
) -> Dict[str, Any]:
    total_beats = max(float(measure_layout["total_beats"]), 1.0)
    measure_padding = min(24.0, (measure_layout["end_x"] - measure_layout["start_x"]) * 0.16)
    inner_left = measure_layout["start_x"] + measure_padding
    inner_right = measure_layout["end_x"] - measure_padding
    usable_width = max(inner_right - inner_left, 1.0)
    start_beat = float(note.get("start_beat", 1.0)) - 1.0
    beat_span = max(float(note.get("beats", 1.0)), 0.25)
    beat_center = min(max(start_beat + (beat_span * 0.5), 0.0), total_beats)
    x = inner_left + (beat_center / total_beats) * usable_width
    staff_step = 4.0 if note.get("is_rest") else float(_pitch_to_staff_step(str(note.get("pitch", "E4"))))
    y = staff_bottom - (staff_step * (staff_spacing / 2.0)) if not note.get("is_rest") else staff_bottom - (staff_spacing * 2.0)
    note_head_width = staff_spacing * 1.35
    note_head_height = staff_spacing * 0.95
    style = _resolve_note_style(float(note.get("beats", 1.0)), bool(note.get("is_rest")))
    default_stem_up = staff_step < 4.0
    style["stem_up"] = default_stem_up
    stem_length = staff_spacing * 3.7
    stem_x = x + note_head_width * 0.46 if default_stem_up else x - note_head_width * 0.46
    stem_end_y = y - stem_length if default_stem_up else y + stem_length
    return {
        "note_id": note.get("note_id"),
        "source_event_id": note.get("source_event_id"),
        "pitch": note.get("pitch"),
        "duration": note.get("duration"),
        "beats": float(note.get("beats", 1.0)),
        "start_beat": float(note.get("start_beat", 1.0)),
        "is_rest": bool(note.get("is_rest")),
        "tied_to_next": bool(note.get("tied_to_next")),
        "tied_from_previous": bool(note.get("tied_from_previous")),
        "accidental": _extract_accidental(str(note.get("pitch", ""))),
        "staff_step": staff_step,
        "x": x,
        "y": y,
        "note_head_width": note_head_width,
        "note_head_height": note_head_height,
        "style": style,
        "ledger_steps": _ledger_steps(staff_step),
        "label": _render_note_label(note),
        "stem_x": stem_x,
        "stem_end_y": stem_end_y,
        "beam_shared_levels": 0,
        "beam_extra_flags": int(style["flags"]),
        "beam_direction_up": default_stem_up,
        "beam_group_id": None,
    }



def _build_measure_beams(notes: Sequence[Dict[str, Any]], *, beam_group_span: float, staff_spacing: float) -> List[Dict[str, Any]]:
    beam_groups: List[Dict[str, Any]] = []
    current_group: List[Dict[str, Any]] = []
    current_bucket: int | None = None

    def flush_group() -> None:
        nonlocal current_group, current_bucket
        if len(current_group) >= 2:
            built = _finalize_beam_group(current_group, len(beam_groups), staff_spacing)
            if built is not None:
                beam_groups.append(built)
        current_group = []
        current_bucket = None

    for note in notes:
        beam_count = int(note["style"]["flags"])
        if note.get("is_rest") or beam_count <= 0:
            flush_group()
            continue

        bucket = int((max(note["start_beat"] - 1.0, 0.0)) // max(beam_group_span, 0.25))
        if current_group and bucket != current_bucket:
            flush_group()
        current_group.append(note)
        current_bucket = bucket

    flush_group()
    return beam_groups



def _finalize_beam_group(notes: Sequence[Dict[str, Any]], group_index: int, staff_spacing: float) -> Dict[str, Any] | None:
    shared_levels = min(int(note["style"]["flags"]) for note in notes)
    if shared_levels <= 0:
        return None

    direction_up = (sum(float(note["staff_step"]) for note in notes) / max(len(notes), 1)) < 4.0
    min_stem_length = staff_spacing * 3.5
    x0 = float(notes[0]["x"])
    xN = float(notes[-1]["x"])
    dx = max(xN - x0, 1.0)
    natural_targets = [
        (float(note["y"]) - min_stem_length) if direction_up else (float(note["y"]) + min_stem_length)
        for note in notes
    ]
    slope = (natural_targets[-1] - natural_targets[0]) / dx
    max_total_slant = staff_spacing * 1.35
    total_slant = slope * dx
    if total_slant > max_total_slant:
        slope = max_total_slant / dx
    elif total_slant < -max_total_slant:
        slope = -max_total_slant / dx

    if direction_up:
        intercept = min(target - slope * (float(note["x"]) - x0) for note, target in zip(notes, natural_targets))
    else:
        intercept = max(target - slope * (float(note["x"]) - x0) for note, target in zip(notes, natural_targets))

    beam_gap = max(5.0, staff_spacing * 0.6)
    direction_sign = -1.0 if direction_up else 1.0
    segments: List[Dict[str, float]] = []

    for note in notes:
        stem_x = float(note["x"]) + float(note["note_head_width"]) * 0.46 if direction_up else float(note["x"]) - float(note["note_head_width"]) * 0.46
        stem_end_y = intercept + slope * (float(note["x"]) - x0)
        note["beam_group_id"] = f"beam_{group_index}"
        note["beam_shared_levels"] = shared_levels
        note["beam_extra_flags"] = max(0, int(note["style"]["flags"]) - shared_levels)
        note["beam_direction_up"] = direction_up
        note["stem_x"] = stem_x
        note["stem_end_y"] = stem_end_y

    for level in range(shared_levels):
        offset = level * beam_gap * direction_sign
        for first_note, second_note in zip(notes, notes[1:]):
            segments.append(
                {
                    "x1": float(first_note["stem_x"]),
                    "y1": float(first_note["stem_end_y"]) + offset,
                    "x2": float(second_note["stem_x"]),
                    "y2": float(second_note["stem_end_y"]) + offset,
                }
            )

    return {
        "group_id": f"beam_{group_index}",
        "direction_up": direction_up,
        "shared_levels": shared_levels,
        "segments": segments,
    }



def _build_system_ties(flattened_notes: Sequence[Dict[str, Any]]) -> List[Dict[str, float]]:
    ties: List[Dict[str, float]] = []
    for index, note in enumerate(flattened_notes):
        if not note.get("tied_to_next") or note.get("is_rest"):
            continue
        for next_note in flattened_notes[index + 1 :]:
            if next_note.get("source_event_id") == note.get("source_event_id"):
                start_x = float(note["x"]) + float(note["note_head_width"]) * 0.45
                end_x = float(next_note["x"]) - float(next_note["note_head_width"]) * 0.45
                if end_x <= start_x:
                    break
                ties.append(
                    {
                        "start_x": start_x,
                        "end_x": end_x,
                        "start_y": float(note["y"]) + float(note["note_head_height"]) * 0.8,
                        "end_y": float(next_note["y"]) + float(next_note["note_head_height"]) * 0.8,
                    }
                )
                break
    return ties



def _manifest_page(page: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "page_no": page["page_no"],
        "systems": [
            {
                "system_no": system["system_no"],
                "measure_range": [system["measures"][0]["measure_no"], system["measures"][-1]["measure_no"]],
                "measures": [
                    {
                        "measure_no": measure["measure_no"],
                        "total_beats": measure["total_beats"],
                        "used_beats": measure["used_beats"],
                        "notes": [
                            {
                                "note_id": note["note_id"],
                                "pitch": note["pitch"],
                                "duration": note["duration"],
                                "beats": note["beats"],
                                "start_beat": note["start_beat"],
                                "x_ratio": round((note["x"] - measure["start_x"]) / max(measure["end_x"] - measure["start_x"], 1.0), 3),
                                "is_rest": note["is_rest"],
                                "staff_step": round(float(note["staff_step"]), 3),
                                "beam_group_id": note.get("beam_group_id"),
                            }
                            for note in measure["notes"]
                        ],
                    }
                    for measure in system["measures"]
                ],
            }
            for system in page["systems"]
        ],
    }

class _PngRenderer:
    def __init__(self, image: Image.Image, *, offset_y: int = 0) -> None:
        self.image = image
        self.draw = ImageDraw.Draw(image)
        self.offset_y = offset_y
        self.width = float(image.size[0])
        self.height = float(image.size[1])

    def line(self, x1: float, y1: float, x2: float, y2: float, *, width: int = 1, color: str = INK_COLOR) -> None:
        self.draw.line((x1, y1 + self.offset_y, x2, y2 + self.offset_y), fill=color, width=width)

    def ellipse(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        outline: str = INK_COLOR,
        fill: str | None = None,
        width: int = 1,
    ) -> None:
        self.draw.ellipse((x1, y1 + self.offset_y, x2, y2 + self.offset_y), outline=outline, fill=fill, width=width)

    def rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        outline: str | None = INK_COLOR,
        fill: str | None = None,
        width: int = 1,
    ) -> None:
        self.draw.rectangle((x1, y1 + self.offset_y, x2, y2 + self.offset_y), outline=outline, fill=fill, width=width)

    def text(self, x: float, y: float, text: str, *, size: int = 16, bold: bool = False, color: str = INK_COLOR) -> None:
        self.draw.text((x, y + self.offset_y), text, fill=color, font=_load_font(size, bold=bold))

    def polyline(self, points: Sequence[tuple[float, float]], *, width: int = 1, color: str = INK_COLOR) -> None:
        if len(points) < 2:
            return
        adjusted = [(x, y + self.offset_y) for x, y in points]
        self.draw.line(adjusted, fill=color, width=width)


class _PdfRenderer:
    def __init__(self, pdf_canvas: Any, width: float, height: float) -> None:
        self.canvas = pdf_canvas
        self.width = width
        self.height = height

    def line(self, x1: float, y1: float, x2: float, y2: float, *, width: int = 1, color: str = INK_COLOR) -> None:
        self.canvas.setLineWidth(width)
        self._set_stroke(color)
        self.canvas.line(x1, self.height - y1, x2, self.height - y2)

    def ellipse(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        outline: str = INK_COLOR,
        fill: str | None = None,
        width: int = 1,
    ) -> None:
        self.canvas.setLineWidth(width)
        self._set_stroke(outline)
        if fill is not None:
            self._set_fill(fill)
        self.canvas.ellipse(x1, self.height - y2, x2, self.height - y1, stroke=1, fill=1 if fill is not None else 0)

    def rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        outline: str | None = INK_COLOR,
        fill: str | None = None,
        width: int = 1,
    ) -> None:
        self.canvas.setLineWidth(width)
        if outline is not None:
            self._set_stroke(outline)
        if fill is not None:
            self._set_fill(fill)
        self.canvas.rect(x1, self.height - y2, x2 - x1, y2 - y1, stroke=1 if outline is not None else 0, fill=1 if fill is not None else 0)

    def text(self, x: float, y: float, text: str, *, size: int = 16, bold: bool = False, color: str = INK_COLOR) -> None:
        self._set_fill(color)
        self.canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.canvas.drawString(x, self.height - y - size, text)

    def polyline(self, points: Sequence[tuple[float, float]], *, width: int = 1, color: str = INK_COLOR) -> None:
        if len(points) < 2:
            return
        self.canvas.setLineWidth(width)
        self._set_stroke(color)
        for start, end in zip(points, points[1:]):
            self.canvas.line(start[0], self.height - start[1], end[0], self.height - end[1])

    def _set_stroke(self, color: str) -> None:
        red, green, blue = _hex_to_rgb(color)
        self.canvas.setStrokeColorRGB(red, green, blue)

    def _set_fill(self, color: str) -> None:
        red, green, blue = _hex_to_rgb(color)
        self.canvas.setFillColorRGB(red, green, blue)

def _render_notation_page(renderer: Any, score: Dict[str, Any], page: Dict[str, Any], with_annotations: bool, *, show_page_frame: bool) -> None:
    if show_page_frame:
        renderer.rectangle(26, 20, page["width"] - 26, page["height"] - 22, outline="#d6cec2", fill=PAPER_COLOR, width=2)

    title_y = 56.0
    renderer.text(72.0, title_y, str(page["title"]), size=26, bold=True)
    renderer.text(72.0, title_y + 34.0, str(page["subtitle"]), size=12, color=MUTED_COLOR)
    renderer.line(72.0, title_y + 64.0, page["width"] - 72.0, title_y + 64.0, width=2, color=ACCENT_COLOR)
    renderer.text(page["width"] - 132.0, title_y + 8.0, f"Page {page['page_no']}", size=11, color=MUTED_COLOR)

    for system in page["systems"]:
        _render_system(renderer, score, system, with_annotations)



def _render_system(renderer: Any, score: Dict[str, Any], system: Dict[str, Any], with_annotations: bool) -> None:
    staff_top = float(system["staff_top"])
    staff_bottom = float(system["staff_bottom"])
    staff_spacing = float(system["staff_spacing"])
    left = float(system["left"])
    right = float(system["right"])
    left_indent = float(system["left_indent"])
    system_start = left + left_indent

    if with_annotations:
        measure_range = f"mm. {system['measures'][0]['measure_no']}-{system['measures'][-1]['measure_no']}"
        renderer.text(left, system["top"] + 2.0, measure_range, size=10, color=MUTED_COLOR)

    for line_index in range(5):
        y = staff_top + (line_index * staff_spacing)
        renderer.line(system_start, y, right, y, width=1, color=INK_COLOR)

    renderer.line(system_start, staff_top, system_start, staff_bottom, width=2, color=INK_COLOR)
    renderer.line(right, staff_top, right, staff_bottom, width=2, color=INK_COLOR)

    if system.get("show_signature"):
        _render_signature_block(renderer, score, left, staff_top, staff_spacing)

    for measure in system["measures"]:
        _render_measure(renderer, measure, staff_top, staff_bottom, staff_spacing, with_annotations)

    for tie in system.get("ties", []):
        _render_tie(renderer, tie)



def _render_signature_block(renderer: Any, score: Dict[str, Any], left: float, staff_top: float, staff_spacing: float) -> None:
    renderer.text(left + 4.0, staff_top - staff_spacing * 1.55, "G", size=int(staff_spacing * 4.2), bold=True)
    numerator, denominator = parse_time_signature(str(score.get("time_signature", "4/4")))
    renderer.text(left + 42.0, staff_top + staff_spacing * 0.1, str(numerator), size=int(staff_spacing * 1.65), bold=True)
    renderer.text(left + 42.0, staff_top + staff_spacing * 1.95, str(denominator), size=int(staff_spacing * 1.65), bold=True)
    renderer.text(left + 2.0, staff_top - staff_spacing * 3.0, f"Tempo {score['tempo']}", size=10, color=MUTED_COLOR)
    renderer.text(left + 2.0, staff_top + staff_spacing * 5.2, f"Key {score['key_signature']}", size=10, color=MUTED_COLOR)



def _render_measure(
    renderer: Any,
    measure: Dict[str, Any],
    staff_top: float,
    staff_bottom: float,
    staff_spacing: float,
    with_annotations: bool,
) -> None:
    start_x = float(measure["start_x"])
    end_x = float(measure["end_x"])
    renderer.line(start_x, staff_top, start_x, staff_bottom, width=1, color=INK_COLOR)
    renderer.line(end_x, staff_top, end_x, staff_bottom, width=2, color=INK_COLOR)

    if with_annotations:
        renderer.text(start_x + 4.0, staff_top - 16.0, str(measure["measure_no"]), size=9, color=MUTED_COLOR)

    for note in measure["notes"]:
        _render_note(renderer, note, staff_top, staff_bottom, staff_spacing, with_annotations)

    _render_beam_groups(renderer, measure.get("beam_groups", []), staff_spacing)



def _render_beam_groups(renderer: Any, beam_groups: Sequence[Dict[str, Any]], staff_spacing: float) -> None:
    beam_width = max(4, int(round(staff_spacing * 0.42)))
    for group in beam_groups:
        for segment in group.get("segments", []):
            renderer.line(segment["x1"], segment["y1"], segment["x2"], segment["y2"], width=beam_width, color=INK_COLOR)



def _render_note(
    renderer: Any,
    note: Dict[str, Any],
    staff_top: float,
    staff_bottom: float,
    staff_spacing: float,
    with_annotations: bool,
) -> None:
    x = float(note["x"])
    y = float(note["y"])
    head_width = float(note["note_head_width"])
    head_height = float(note["note_head_height"])
    style = note["style"]

    if note.get("is_rest"):
        _render_rest(renderer, note, staff_top, staff_bottom, staff_spacing)
        if with_annotations:
            renderer.text(x - 10.0, staff_bottom + 18.0, str(note["duration"]), size=8, color=MUTED_COLOR)
        return

    for ledger_step in note.get("ledger_steps", []):
        ledger_y = staff_bottom - (float(ledger_step) * (staff_spacing / 2.0))
        renderer.line(x - head_width * 0.9, ledger_y, x + head_width * 0.9, ledger_y, width=1, color=INK_COLOR)

    if note.get("accidental"):
        renderer.text(x - head_width * 1.5, y - head_height, str(note["accidental"]), size=int(staff_spacing * 1.05), bold=True)

    fill = INK_COLOR if style["filled"] else PAPER_COLOR
    renderer.ellipse(
        x - head_width / 2.0,
        y - head_height / 2.0,
        x + head_width / 2.0,
        y + head_height / 2.0,
        outline=INK_COLOR,
        fill=fill,
        width=2,
    )

    if style["stem"]:
        stem_up = bool(note.get("beam_direction_up", style["stem_up"]))
        stem_x = float(note.get("stem_x", x + head_width * 0.46 if stem_up else x - head_width * 0.46))
        stem_end_y = float(note.get("stem_end_y", y - staff_spacing * 3.7 if stem_up else y + staff_spacing * 3.7))
        renderer.line(stem_x, stem_end_y, stem_x, y, width=2, color=INK_COLOR)
        extra_flags = int(note.get("beam_extra_flags", style["flags"]))
        if extra_flags > 0:
            _render_flags(renderer, stem_x, stem_end_y, stem_up, extra_flags, staff_spacing)

    if style["dots"]:
        dot_x = x + head_width * 0.95
        dot_y = y - 2.0
        for dot_index in range(style["dots"]):
            renderer.ellipse(
                dot_x + dot_index * 5.0,
                dot_y,
                dot_x + 3.0 + dot_index * 5.0,
                dot_y + 3.0,
                outline=INK_COLOR,
                fill=INK_COLOR,
                width=1,
            )

    if with_annotations:
        renderer.text(x - head_width, staff_bottom + 16.0, _note_annotation(str(note["pitch"])), size=8, color=MUTED_COLOR)



def _render_flags(renderer: Any, stem_x: float, stem_edge_y: float, stem_up: bool, flag_count: int, staff_spacing: float) -> None:
    direction = 1.0 if stem_up else -1.0
    for flag_index in range(flag_count):
        start_y = stem_edge_y + (flag_index * staff_spacing * 0.74 * direction)
        points = [
            (stem_x, start_y),
            (stem_x + staff_spacing * 0.7, start_y + staff_spacing * 0.45 * direction),
            (stem_x + staff_spacing * 1.25, start_y + staff_spacing * 1.05 * direction),
        ]
        renderer.polyline(points, width=2, color=INK_COLOR)



def _render_rest(renderer: Any, note: Dict[str, Any], staff_top: float, staff_bottom: float, staff_spacing: float) -> None:
    x = float(note["x"])
    style = note["style"]
    variant = style["rest_variant"]

    if variant == "whole":
        y = staff_top + staff_spacing * 2.0
        renderer.rectangle(x - 10.0, y - 2.0, x + 10.0, y + 6.0, outline=INK_COLOR, fill=INK_COLOR, width=1)
        return
    if variant == "half":
        y = staff_top + staff_spacing * 1.0
        renderer.rectangle(x - 10.0, y - 6.0, x + 10.0, y + 2.0, outline=INK_COLOR, fill=INK_COLOR, width=1)
        return

    mid_y = staff_top + staff_spacing * 2.0
    if variant == "quarter":
        renderer.polyline(
            [
                (x + 4.0, mid_y - 23.0),
                (x - 5.0, mid_y - 10.0),
                (x + 4.0, mid_y + 1.0),
                (x - 3.0, mid_y + 13.0),
                (x + 5.0, mid_y + 26.0),
            ],
            width=2,
            color=INK_COLOR,
        )
        return

    renderer.ellipse(x - 1.0, mid_y - 24.0, x + 7.0, mid_y - 16.0, outline=INK_COLOR, fill=INK_COLOR, width=1)
    renderer.line(x + 3.0, mid_y - 20.0, x + 3.0, mid_y + 10.0, width=2, color=INK_COLOR)
    renderer.polyline([(x + 3.0, mid_y - 3.0), (x + 11.0, mid_y + 4.0), (x + 4.0, mid_y + 13.0)], width=2, color=INK_COLOR)
    if variant == "sixteenth":
        renderer.polyline([(x + 3.0, mid_y + 6.0), (x + 11.0, mid_y + 14.0), (x + 4.0, mid_y + 22.0)], width=2, color=INK_COLOR)



def _render_tie(renderer: Any, tie: Dict[str, float]) -> None:
    control_y = max(tie["start_y"], tie["end_y"]) + 10.0
    points = _sample_quadratic_curve(
        (tie["start_x"], tie["start_y"]),
        ((tie["start_x"] + tie["end_x"]) / 2.0, control_y),
        (tie["end_x"], tie["end_y"]),
        samples=12,
    )
    renderer.polyline(points, width=2, color=INK_COLOR)



def _sample_quadratic_curve(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    *,
    samples: int,
) -> List[tuple[float, float]]:
    points: List[tuple[float, float]] = []
    for index in range(samples + 1):
        t = index / max(samples, 1)
        x = ((1 - t) ** 2 * start[0]) + (2 * (1 - t) * t * control[0]) + ((t ** 2) * end[0])
        y = ((1 - t) ** 2 * start[1]) + (2 * (1 - t) * t * control[1]) + ((t ** 2) * end[1])
        points.append((x, y))
    return points

def _resolve_note_style(beats: float, is_rest: bool) -> Dict[str, Any]:
    dots = 1 if _is_dotted_duration(beats) else 0
    if beats >= 3.5:
        return {"filled": False, "stem": False, "stem_up": True, "flags": 0, "dots": dots, "rest_variant": "whole" if is_rest else None}
    if beats >= 1.75:
        return {"filled": False, "stem": True, "stem_up": True, "flags": 0, "dots": dots, "rest_variant": "half" if is_rest else None}
    if beats >= 0.75:
        return {"filled": True, "stem": True, "stem_up": True, "flags": 0, "dots": dots, "rest_variant": "quarter" if is_rest else None}
    if beats >= 0.375:
        return {"filled": True, "stem": True, "stem_up": True, "flags": 1, "dots": dots, "rest_variant": "eighth" if is_rest else None}
    return {"filled": True, "stem": True, "stem_up": True, "flags": 2, "dots": dots, "rest_variant": "sixteenth" if is_rest else None}



def _is_dotted_duration(beats: float) -> bool:
    dotted_values = (0.75, 1.5, 3.0)
    return any(abs(beats - value) <= 0.08 for value in dotted_values)



def _pitch_to_staff_step(pitch: str) -> int:
    note_name, octave = _split_pitch(pitch)
    letter = note_name[:1] or "E"
    return (octave * 7 + DIATONIC_STEPS.get(letter, DIATONIC_STEPS["E"])) - (4 * 7 + DIATONIC_STEPS["E"])



def _ledger_steps(staff_step: float) -> List[int]:
    if staff_step < 0:
        return list(range(-2, int(staff_step) - 1, -2))
    if staff_step > 8:
        upper_bound = int(staff_step)
        if upper_bound % 2 == 1:
            upper_bound -= 1
        return list(range(10, upper_bound + 1, 2))
    return []



def _split_pitch(pitch: str) -> tuple[str, int]:
    if pitch == "Rest":
        return "E", 4
    index = len(pitch)
    while index > 0 and pitch[index - 1].isdigit():
        index -= 1
    note_name = pitch[:index] or "E"
    octave = int(pitch[index:] or "4")
    return note_name, octave



def _extract_accidental(pitch: str) -> str | None:
    note_name, _ = _split_pitch(pitch)
    if "#" in note_name:
        return "#"
    if "b" in note_name:
        return "b"
    return None



def _note_annotation(pitch: str) -> str:
    if pitch == "Rest":
        return "rest"
    return pitch



def _render_note_label(note: Dict[str, Any]) -> str:
    pitch = "Rest" if note.get("is_rest") else str(note.get("pitch", "Rest"))
    return f"{pitch}({note.get('duration', note.get('beats', '?'))})"



def _chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]



def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) / 255.0 for index in (0, 2, 4))



def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()



def _denominator_power(denominator: int) -> int:
    power = 0
    value = max(denominator, 1)
    while value > 1:
        value //= 2
        power += 1
    return power



def _seconds_to_ticks(seconds: float, tempo: int) -> int:
    beat_seconds = 60.0 / max(tempo, 1)
    return int(round((seconds / beat_seconds) * TICKS_PER_QUARTER))



def _pitch_to_midi_number(pitch: str) -> int:
    if pitch == "Rest":
        return 0

    note_name, octave = _split_pitch(pitch)
    if note_name not in NOTE_NAMES:
        raise ValueError(f"invalid pitch: {pitch}")
    return 12 * (octave + 1) + NOTE_NAMES[note_name]



def _encode_variable_length(value: int) -> bytes:
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))
