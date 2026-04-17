"""Report export helpers."""

from __future__ import annotations

import io
import struct
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from backend.export.export_utils import build_export_files
from backend.services import analysis_service

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover - runtime optional fallback
    A4 = None
    canvas = None


USE_DB: bool = False
_session_factory = None
REPORT_EXPORTS: dict[str, dict[str, Any]] = {}
SUPPORTED_FORMATS = {"pdf", "png", "midi"}


def set_db_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


@contextmanager
def _session_scope() -> Iterator[Any]:
    if _session_factory is None:
        raise RuntimeError("DB mode enabled but no session factory configured")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_report_exports() -> None:
    REPORT_EXPORTS.clear()


def _normalize_formats(formats: list[str] | None) -> list[str]:
    requested = formats or ["pdf"]
    normalized: list[str] = []
    for item in requested:
        fmt = str(item or "").strip().lower()
        if not fmt:
            continue
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"unsupported report export format: {fmt}")
        if fmt not in normalized:
            normalized.append(fmt)
    return normalized or ["pdf"]


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_analysis_result_data(analysis_id: str | None) -> dict[str, Any]:
    if not analysis_id:
        return {}

    if not USE_DB:
        in_memory = analysis_service.ANALYSIS_RESULTS.get(analysis_id) or {}
        result_data = in_memory.get("result_data")
        return deepcopy(result_data) if isinstance(result_data, dict) else {}

    from backend.db.models import AudioAnalysis

    with _session_scope() as session:
        row = session.execute(select(AudioAnalysis).where(AudioAnalysis.analysis_id == analysis_id)).scalar_one_or_none()
        if row is None:
            return {}
        result_data = row.result_data if isinstance(row.result_data, dict) else {}
        return deepcopy(result_data)


def _format_percent(value: float | None) -> str:
    if value is None:
        return "--"
    if value <= 1:
        value = value * 100.0
    return f"{round(value)}%"


def _coerce_score(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(100.0, value))


def _build_report_context(report_id: str, payload: dict, result_data: dict[str, Any]) -> dict[str, Any]:
    rhythm_report = result_data.get("rhythm_report") if isinstance(result_data.get("rhythm_report"), dict) else {}
    pitch_comparison = result_data.get("pitch_comparison") if isinstance(result_data.get("pitch_comparison"), dict) else {}
    pitch_summary = pitch_comparison.get("summary") if isinstance(pitch_comparison.get("summary"), dict) else {}

    rhythm_score = _coerce_score(_to_float(payload.get("rhythm_score")) or _to_float(rhythm_report.get("score")))
    pitch_score = _coerce_score(_to_float(payload.get("pitch_score")) or _to_float(pitch_summary.get("accuracy")))
    total_score = _coerce_score(_to_float(payload.get("total_score")) or _to_float(result_data.get("overall_score")))
    if total_score is None and rhythm_score is not None and pitch_score is not None:
        total_score = round((rhythm_score * 0.5) + (pitch_score * 0.5), 2)

    return {
        "report_id": report_id,
        "analysis_id": payload.get("analysis_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "include_charts": bool(payload.get("include_charts", True)),
        "scores": {
            "total_score": total_score,
            "rhythm_score": rhythm_score,
            "pitch_score": pitch_score,
        },
        "rhythm": {
            "timing_accuracy": _to_float(rhythm_report.get("timing_accuracy")),
            "coverage_ratio": _to_float(rhythm_report.get("coverage_ratio")),
            "consistency_ratio": _to_float(rhythm_report.get("consistency_ratio")),
            "mean_deviation_ms": _to_float(rhythm_report.get("mean_deviation_ms")),
            "reference_bpm": _to_float(rhythm_report.get("reference_bpm")),
            "user_bpm": _to_float(rhythm_report.get("user_bpm")),
            "missing_beats": int(rhythm_report.get("missing_beats", 0) or 0),
            "extra_beats": int(rhythm_report.get("extra_beats", 0) or 0),
        },
        "pitch": {
            "average_deviation_cents": _to_float(pitch_summary.get("average_deviation_cents")),
            "within_25_cents_ratio": _to_float(pitch_summary.get("within_25_cents_ratio")),
            "within_50_cents_ratio": _to_float(pitch_summary.get("within_50_cents_ratio")),
            "x_axis": pitch_comparison.get("x_axis") if isinstance(pitch_comparison.get("x_axis"), list) else [],
            "reference_curve": pitch_comparison.get("reference_curve")
            if isinstance(pitch_comparison.get("reference_curve"), list)
            else [],
            "user_curve": pitch_comparison.get("user_curve") if isinstance(pitch_comparison.get("user_curve"), list) else [],
        },
    }


def _encode_variable_length(value: int) -> bytes:
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))


def _build_report_midi_bytes(context: dict[str, Any]) -> bytes:
    total_score = context["scores"].get("total_score")
    velocity = int(max(30, min(110, round((total_score or 60.0) * 1.1))))
    track = bytearray()
    track.extend(_encode_variable_length(0))
    track.extend(b"\xFF\x51\x03\x07\xA1\x20")  # 120 BPM
    track.extend(_encode_variable_length(0))
    track.extend(bytes([0x90, 60, velocity]))
    track.extend(_encode_variable_length(480))
    track.extend(bytes([0x80, 60, 0]))
    track.extend(_encode_variable_length(0))
    track.extend(b"\xFF\x2F\x00")
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_fallback_pdf_bytes(context: dict[str, Any]) -> bytes:
    lines = _report_lines(context, include_chart_hint=True)
    content_lines = ["BT", "/F1 12 Tf", "50 800 Td", "14 TL"]
    for line in lines:
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii") + stream + b"\nendstream endobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer << /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(pdf)


def _report_lines(context: dict[str, Any], include_chart_hint: bool) -> list[str]:
    scores = context["scores"]
    rhythm = context["rhythm"]
    pitch = context["pitch"]
    return [
        "SeeMusic Singing Evaluation Report",
        f"Report ID: {context['report_id']}",
        f"Analysis ID: {context.get('analysis_id') or '--'}",
        f"Generated At (UTC): {context['generated_at']}",
        "",
        f"Overall Score: {round(scores['total_score']) if scores['total_score'] is not None else '--'}",
        f"Rhythm Score: {round(scores['rhythm_score']) if scores['rhythm_score'] is not None else '--'}",
        f"Pitch Score: {round(scores['pitch_score']) if scores['pitch_score'] is not None else '--'}",
        "",
        f"Timing Accuracy: {_format_percent(rhythm['timing_accuracy'])}",
        f"Coverage: {_format_percent(rhythm['coverage_ratio'])}",
        f"Consistency: {_format_percent(rhythm['consistency_ratio'])}",
        f"Mean Deviation: {round(rhythm['mean_deviation_ms']) if rhythm['mean_deviation_ms'] is not None else '--'} ms",
        f"Reference BPM: {round(rhythm['reference_bpm']) if rhythm['reference_bpm'] is not None else '--'}",
        f"User BPM: {round(rhythm['user_bpm']) if rhythm['user_bpm'] is not None else '--'}",
        f"Missing/Extra Beats: {rhythm['missing_beats']} / {rhythm['extra_beats']}",
        "",
        f"Pitch Avg Deviation: {round(pitch['average_deviation_cents']) if pitch['average_deviation_cents'] is not None else '--'} cents",
        f"Within +/-25 cents: {_format_percent(pitch['within_25_cents_ratio'])}",
        f"Within +/-50 cents: {_format_percent(pitch['within_50_cents_ratio'])}",
        f"Chart Included: {'Yes' if include_chart_hint else 'No'}",
    ]


def _draw_pitch_chart_reportlab(pdf: Any, context: dict[str, Any], x: float, y: float, width: float, height: float) -> None:
    x_axis = context["pitch"]["x_axis"]
    ref_curve = context["pitch"]["reference_curve"]
    user_curve = context["pitch"]["user_curve"]
    if not x_axis or not ref_curve or not user_curve:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(x, y + height - 14, "Pitch chart unavailable")
        return

    sample_count = min(len(x_axis), len(ref_curve), len(user_curve))
    if sample_count < 2:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(x, y + height - 14, "Pitch chart unavailable")
        return

    pairs: list[tuple[float, float, float]] = []
    for idx in range(sample_count):
        tx = x_axis[idx]
        rf = ref_curve[idx]
        uf = user_curve[idx]
        if not isinstance(tx, (int, float)):
            continue
        if not isinstance(rf, (int, float)) or not isinstance(uf, (int, float)):
            continue
        if rf <= 0 and uf <= 0:
            continue
        pairs.append((float(tx), max(float(rf), 0.0), max(float(uf), 0.0)))

    if len(pairs) < 2:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(x, y + height - 14, "Pitch chart unavailable")
        return

    t_min = pairs[0][0]
    t_max = pairs[-1][0]
    if t_max <= t_min:
        t_max = t_min + 1.0
    freqs = [item[1] for item in pairs if item[1] > 0] + [item[2] for item in pairs if item[2] > 0]
    f_min = min(freqs) if freqs else 0.0
    f_max = max(freqs) if freqs else 1.0
    if f_max <= f_min:
        f_max = f_min + 1.0

    pdf.setLineWidth(1)
    pdf.setStrokeColorRGB(0.84, 0.86, 0.88)
    pdf.rect(x, y, width, height, stroke=1, fill=0)

    def map_x(t: float) -> float:
        return x + ((t - t_min) / (t_max - t_min)) * width

    def map_y(f: float) -> float:
        return y + ((f - f_min) / (f_max - f_min)) * height

    pdf.setStrokeColorRGB(0.27, 0.48, 0.62)  # reference
    started = False
    last_x = 0.0
    last_y = 0.0
    for t, rf, _ in pairs:
        if rf <= 0:
            started = False
            continue
        px = map_x(t)
        py = map_y(rf)
        if started:
            pdf.line(last_x, last_y, px, py)
        last_x = px
        last_y = py
        started = True

    pdf.setStrokeColorRGB(0.90, 0.42, 0.28)  # user
    started = False
    for t, _, uf in pairs:
        if uf <= 0:
            started = False
            continue
        px = map_x(t)
        py = map_y(uf)
        if started:
            pdf.line(last_x, last_y, px, py)
        last_x = px
        last_y = py
        started = True

    pdf.setFillColorRGB(0.15, 0.2, 0.24)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(x, y + height + 6, "Pitch Curve (Reference=Blue, User=Orange)")


def _build_report_pdf_bytes(context: dict[str, Any]) -> bytes:
    if canvas is None or A4 is None:
        return _build_fallback_pdf_bytes(context)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"SeeMusic_Report_{context['report_id']}")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(48, height - 56, "SeeMusic Singing Evaluation Report")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(48, height - 80, f"Report ID: {context['report_id']}")
    pdf.drawString(48, height - 96, f"Analysis ID: {context.get('analysis_id') or '--'}")
    pdf.drawString(48, height - 112, f"Generated At (UTC): {context['generated_at']}")

    scores = context["scores"]
    rhythm = context["rhythm"]
    pitch = context["pitch"]

    y = height - 150
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(48, y, "Scores")
    y -= 22
    pdf.setFont("Helvetica", 12)
    pdf.drawString(56, y, f"Overall Score: {round(scores['total_score']) if scores['total_score'] is not None else '--'}")
    y -= 16
    pdf.drawString(56, y, f"Rhythm Score: {round(scores['rhythm_score']) if scores['rhythm_score'] is not None else '--'}")
    y -= 16
    pdf.drawString(56, y, f"Pitch Score: {round(scores['pitch_score']) if scores['pitch_score'] is not None else '--'}")

    y -= 28
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(48, y, "Rhythm Metrics")
    y -= 22
    pdf.setFont("Helvetica", 11)
    pdf.drawString(56, y, f"Timing Accuracy: {_format_percent(rhythm['timing_accuracy'])}")
    y -= 15
    pdf.drawString(56, y, f"Coverage: {_format_percent(rhythm['coverage_ratio'])}")
    y -= 15
    pdf.drawString(56, y, f"Consistency: {_format_percent(rhythm['consistency_ratio'])}")
    y -= 15
    pdf.drawString(
        56,
        y,
        f"Mean Deviation: {round(rhythm['mean_deviation_ms']) if rhythm['mean_deviation_ms'] is not None else '--'} ms",
    )
    y -= 15
    pdf.drawString(
        56,
        y,
        f"Reference BPM / User BPM: {round(rhythm['reference_bpm']) if rhythm['reference_bpm'] is not None else '--'} / "
        f"{round(rhythm['user_bpm']) if rhythm['user_bpm'] is not None else '--'}",
    )
    y -= 15
    pdf.drawString(56, y, f"Missing Beats / Extra Beats: {rhythm['missing_beats']} / {rhythm['extra_beats']}")

    y -= 28
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(48, y, "Pitch Metrics")
    y -= 22
    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        56,
        y,
        f"Average Deviation: {round(pitch['average_deviation_cents']) if pitch['average_deviation_cents'] is not None else '--'} cents",
    )
    y -= 15
    pdf.drawString(56, y, f"Within +/-25 cents: {_format_percent(pitch['within_25_cents_ratio'])}")
    y -= 15
    pdf.drawString(56, y, f"Within +/-50 cents: {_format_percent(pitch['within_50_cents_ratio'])}")

    if context["include_charts"]:
        _draw_pitch_chart_reportlab(pdf, context, x=48, y=60, width=500, height=150)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _draw_pitch_chart_pillow(draw: ImageDraw.ImageDraw, context: dict[str, Any], box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    width = max(right - left, 1)
    height = max(bottom - top, 1)
    draw.rectangle(box, outline="#d1d5db", width=2)

    x_axis = context["pitch"]["x_axis"]
    ref_curve = context["pitch"]["reference_curve"]
    user_curve = context["pitch"]["user_curve"]
    sample_count = min(len(x_axis), len(ref_curve), len(user_curve))
    if sample_count < 2:
        draw.text((left + 12, top + 10), "Pitch chart unavailable", fill="#6b7280", font=_load_font(20, False))
        return

    points: list[tuple[float, float, float]] = []
    for idx in range(sample_count):
        tx = x_axis[idx]
        rf = ref_curve[idx]
        uf = user_curve[idx]
        if not isinstance(tx, (int, float)):
            continue
        if not isinstance(rf, (int, float)) or not isinstance(uf, (int, float)):
            continue
        if rf <= 0 and uf <= 0:
            continue
        points.append((float(tx), max(float(rf), 0.0), max(float(uf), 0.0)))

    if len(points) < 2:
        draw.text((left + 12, top + 10), "Pitch chart unavailable", fill="#6b7280", font=_load_font(20, False))
        return

    t_min = points[0][0]
    t_max = points[-1][0]
    if t_max <= t_min:
        t_max = t_min + 1.0
    freqs = [item[1] for item in points if item[1] > 0] + [item[2] for item in points if item[2] > 0]
    f_min = min(freqs) if freqs else 0.0
    f_max = max(freqs) if freqs else 1.0
    if f_max <= f_min:
        f_max = f_min + 1.0

    def map_x(t: float) -> float:
        return left + ((t - t_min) / (t_max - t_min)) * width

    def map_y(f: float) -> float:
        return bottom - ((f - f_min) / (f_max - f_min)) * height

    ref_pts = [(map_x(t), map_y(rf)) for t, rf, _ in points if rf > 0]
    user_pts = [(map_x(t), map_y(uf)) for t, _, uf in points if uf > 0]
    if len(ref_pts) > 1:
        draw.line(ref_pts, fill="#457b9d", width=3)
    if len(user_pts) > 1:
        draw.line(user_pts, fill="#e76f51", width=2)


def _load_font(size: int, bold: bool) -> ImageFont.ImageFont:
    candidates = (
        ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]
        if bold
        else ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
    )
    for item in candidates:
        try:
            return ImageFont.truetype(item, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _build_report_png_bytes(context: dict[str, Any]) -> bytes:
    image = Image.new("RGB", (1240, 1754), "#f7f8fa")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(48, True)
    section_font = _load_font(32, True)
    body_font = _load_font(24, False)

    draw.text((64, 50), "SeeMusic Singing Evaluation Report", fill="#1f2937", font=title_font)
    draw.text((64, 120), f"Report ID: {context['report_id']}", fill="#374151", font=body_font)
    draw.text((64, 156), f"Analysis ID: {context.get('analysis_id') or '--'}", fill="#374151", font=body_font)
    draw.text((64, 192), f"Generated At (UTC): {context['generated_at']}", fill="#374151", font=body_font)

    scores = context["scores"]
    rhythm = context["rhythm"]
    pitch = context["pitch"]

    y = 250
    draw.text((64, y), "Scores", fill="#111827", font=section_font)
    y += 54
    draw.text((80, y), f"Overall Score: {round(scores['total_score']) if scores['total_score'] is not None else '--'}", fill="#1f2937", font=body_font)
    y += 34
    draw.text((80, y), f"Rhythm Score: {round(scores['rhythm_score']) if scores['rhythm_score'] is not None else '--'}", fill="#1f2937", font=body_font)
    y += 34
    draw.text((80, y), f"Pitch Score: {round(scores['pitch_score']) if scores['pitch_score'] is not None else '--'}", fill="#1f2937", font=body_font)

    y += 60
    draw.text((64, y), "Rhythm Metrics", fill="#111827", font=section_font)
    y += 54
    rhythm_lines = [
        f"Timing Accuracy: {_format_percent(rhythm['timing_accuracy'])}",
        f"Coverage: {_format_percent(rhythm['coverage_ratio'])}",
        f"Consistency: {_format_percent(rhythm['consistency_ratio'])}",
        f"Mean Deviation: {round(rhythm['mean_deviation_ms']) if rhythm['mean_deviation_ms'] is not None else '--'} ms",
        f"Reference BPM / User BPM: {round(rhythm['reference_bpm']) if rhythm['reference_bpm'] is not None else '--'} / {round(rhythm['user_bpm']) if rhythm['user_bpm'] is not None else '--'}",
        f"Missing Beats / Extra Beats: {rhythm['missing_beats']} / {rhythm['extra_beats']}",
    ]
    for line in rhythm_lines:
        draw.text((80, y), line, fill="#1f2937", font=body_font)
        y += 34

    y += 26
    draw.text((64, y), "Pitch Metrics", fill="#111827", font=section_font)
    y += 54
    pitch_lines = [
        f"Average Deviation: {round(pitch['average_deviation_cents']) if pitch['average_deviation_cents'] is not None else '--'} cents",
        f"Within +/-25 cents: {_format_percent(pitch['within_25_cents_ratio'])}",
        f"Within +/-50 cents: {_format_percent(pitch['within_50_cents_ratio'])}",
    ]
    for line in pitch_lines:
        draw.text((80, y), line, fill="#1f2937", font=body_font)
        y += 34

    if context["include_charts"]:
        draw.text((64, y + 30), "Pitch Curve (Reference=Blue, User=Orange)", fill="#374151", font=body_font)
        _draw_pitch_chart_pillow(draw, context, (64, y + 74, 1170, y + 420))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _write_report_file(file_record: dict[str, Any], context: dict[str, Any]) -> None:
    export_path = Path(str(file_record["file_path"]))
    export_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = str(file_record.get("format", "")).lower()

    if fmt == "pdf":
        export_path.write_bytes(_build_report_pdf_bytes(context))
    elif fmt == "png":
        export_path.write_bytes(_build_report_png_bytes(context))
    elif fmt == "midi":
        export_path.write_bytes(_build_report_midi_bytes(context))
    else:
        raise ValueError(f"unsupported report export format: {fmt}")


def export_report(payload: dict) -> dict:
    report_id = f"r_{uuid4().hex[:8]}"
    formats = _normalize_formats(payload.get("formats"))
    files = build_export_files(report_id, formats)
    result_data = _load_analysis_result_data(payload.get("analysis_id"))
    context = _build_report_context(report_id, payload, result_data)
    for file_record in files:
        _write_report_file(file_record, context)

    result = {
        "report_id": report_id,
        "analysis_id": payload.get("analysis_id"),
        "files": files,
        "include_charts": payload.get("include_charts", True),
        "summary": {
            "total_score": context["scores"]["total_score"],
            "rhythm_score": context["scores"]["rhythm_score"],
            "pitch_score": context["scores"]["pitch_score"],
        },
        "generated_at": context["generated_at"],
    }

    if not USE_DB:
        REPORT_EXPORTS[report_id] = deepcopy(result)
        return result

    from backend.db.models import Project, Report

    analysis_id = payload.get("analysis_id")
    with _session_scope() as session:
        project = None
        if analysis_id:
            project = session.execute(select(Project).where(Project.analysis_id == analysis_id)).scalar_one_or_none()
        report = Report(
            report_id=report_id,
            project_id=int(project.id) if project is not None else None,
            analysis_id=analysis_id,
            pitch_score=context["scores"]["pitch_score"],
            rhythm_score=context["scores"]["rhythm_score"],
            total_score=context["scores"]["total_score"],
            error_points=payload.get("error_points"),
            export_url=files[0]["download_url"] if files else None,
            metadata_={
                "formats": formats,
                "files": files,
                "include_charts": bool(payload.get("include_charts", True)),
                "generated_at": context["generated_at"],
            },
        )
        session.add(report)

    return result
