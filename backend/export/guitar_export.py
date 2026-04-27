"""PDF export helpers for guitar lead-sheet results."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


class GuitarExportError(RuntimeError):
    """Raised when guitar lead-sheet export cannot be completed."""


class GuitarExportDependencyError(GuitarExportError):
    """Raised when PDF export dependencies are unavailable."""


def _safe_name(value: str, default: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", str(value or default)).strip("._")
    return cleaned or default


def _storage_root(storage_dir: Path | None = None) -> Path:
    if storage_dir is None:
        from backend.config.settings import settings as runtime_settings

        storage_dir = runtime_settings.storage_dir

    root = Path(storage_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_export_path(resource_id: str, export_format: str, storage_dir: Path | None = None) -> Path:
    root = _storage_root(storage_dir)
    export_dir = (root / "exports").resolve()
    export_dir.mkdir(parents=True, exist_ok=True)

    safe_resource_id = _safe_name(resource_id, "resource")
    safe_format = _safe_name(export_format, "bin").lower()
    candidate = (export_dir / f"{safe_resource_id}.{safe_format}").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GuitarExportError("export file path is outside the storage directory") from exc
    return candidate


def _download_url_for(path: Path, storage_dir: Path | None = None) -> str:
    root = _storage_root(storage_dir)
    try:
        relative_path = path.resolve().relative_to(root)
    except ValueError as exc:
        raise GuitarExportError("export file path is outside the storage directory") from exc
    return "/storage/" + relative_path.as_posix()


def _safe_paragraph_text(value: str | None) -> str:
    text = str(value or "").strip()
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _paragraph_placeholder(value: str | None) -> str:
    text = str(value or "").strip()
    return _safe_paragraph_text(text) if text else " "


def _build_chord_lyric_pairs(line: dict[str, Any]) -> list[dict[str, str]]:
    measures = list(line.get("measures") or [])
    all_chords: list[dict[str, Any]] = []
    for measure in measures:
        all_chords.extend(list(measure.get("chords") or []))

    lyric_text = str(line.get("lyric_text") or line.get("lyric") or line.get("lyric_placeholder") or "歌词待补").strip()
    lyric_segments = [segment for segment in lyric_text.split() if segment]

    if not all_chords and not lyric_segments:
        return []
    if not all_chords:
        return [{"chord": "", "lyric": segment} for segment in lyric_segments] or [{"chord": "", "lyric": lyric_text or "歌词待补"}]

    pairs: list[dict[str, str]] = []
    for index, chord in enumerate(all_chords):
        lyric = ""
        if index < len(lyric_segments):
            lyric = " ".join(lyric_segments[index:]) if index == len(all_chords) - 1 else lyric_segments[index]
        elif index == 0 and not lyric_segments:
            lyric = lyric_text or "歌词待补"
        pairs.append(
            {
                "chord": str(chord.get("symbol") or "").strip(),
                "lyric": lyric,
            }
        )
    return pairs


def _resolve_display_sections(result: dict[str, Any]) -> list[dict[str, Any]]:
    sections = list(result.get("display_sections") or result.get("sections") or [])
    if sections:
        return sections
    display_lines = list(result.get("display_lines") or [])
    if not display_lines:
        return []
    return [
        {
            "section_no": 1,
            "section_title": "主歌",
            "section_role": "verse",
            "measure_start": int(display_lines[0].get("measure_start") or 1),
            "measure_end": int(display_lines[-1].get("measure_end") or 1),
            "measure_count": sum(int(line.get("measure_count") or 0) for line in display_lines),
            "display_lines": display_lines,
        }
    ]


def export_guitar_lead_sheet_pdf(
    result: dict[str, Any],
    *,
    storage_dir: Path,
    file_stem: str | None = None,
    layout_mode: str = "print",
) -> dict[str, Any]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:  # pragma: no cover - dependency issue
        raise GuitarExportDependencyError("当前环境未安装 reportlab，暂时无法导出吉他 PDF。") from exc

    font_name = "STSong-Light"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    safe_stem = _safe_name(
        file_stem or f"guitar_{result.get('title') or 'lead_sheet'}_{layout_mode}",
        "guitar_lead_sheet",
    )
    target_path = _safe_export_path(safe_stem, "pdf", storage_dir)

    page_size = A4
    doc = SimpleDocTemplate(
        str(target_path),
        pagesize=page_size,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=str(result.get("title") or "Guitar Lead Sheet"),
        author="SeeMusic",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "GuitarTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#213547"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "GuitarSubtitle",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#5b6773"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "GuitarSection",
        parent=styles["Heading3"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#24445a"),
        spaceBefore=6,
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "GuitarMeta",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#34495e"),
    )
    chord_style = ParagraphStyle(
        "GuitarChord",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#14364b"),
        alignment=TA_LEFT,
    )
    lyric_style = ParagraphStyle(
        "GuitarLyric",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#2d3b45"),
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        "GuitarSmall",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8.4,
        leading=11,
        textColor=colors.HexColor("#5b6773"),
    )

    story: list[Any] = []
    story.append(Paragraph(_safe_paragraph_text(str(result.get("title") or "未命名吉他弹唱谱")), title_style))
    story.append(
        Paragraph(
            _safe_paragraph_text(str(result.get("artist") or result.get("subtitle") or "可弹、可唱、可打印的吉他弹唱谱")),
            subtitle_style,
        )
    )

    capo = result.get("capo_suggestion") or {}
    capo_text = f"Capo {capo['capo']}" if isinstance(capo.get("capo"), int) else "--"
    meta_rows = [
        [
            Paragraph(f"<b>调号</b>：{_safe_paragraph_text(str(result.get('key') or '--'))}", meta_style),
            Paragraph(f"<b>拍号</b>：{_safe_paragraph_text(str(result.get('time_signature') or '--'))}", meta_style),
            Paragraph(f"<b>速度</b>：{_safe_paragraph_text(str(result.get('tempo') or '--'))} BPM", meta_style),
        ],
        [
            Paragraph(f"<b>Capo</b>：{_safe_paragraph_text(capo_text)}", meta_style),
            Paragraph(f"<b>调位</b>：{_safe_paragraph_text(str(capo.get('transposed_key') or '--'))}", meta_style),
            Paragraph(f"<b>风格</b>：{_safe_paragraph_text(str(result.get('style') or '--'))}", meta_style),
        ],
    ]
    meta_table = Table(meta_rows, colWidths=[doc.width / 3.0] * 3)
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 6))

    strumming = result.get("strumming_pattern") or {}
    strumming_summary = [
        f"推荐扫弦：{str(strumming.get('display_pattern') or strumming.get('pattern') or '--')}",
        f"节奏口令：{str(strumming.get('counting') or '--')}",
    ]
    practice_tip = str(strumming.get("practice_tip") or strumming.get("description") or "").strip()
    if practice_tip:
        strumming_summary.append(f"提示：{practice_tip}")
    story.append(Paragraph(_safe_paragraph_text(" · ".join(strumming_summary)), small_style))
    story.append(Spacer(1, 8))

    sections = _resolve_display_sections(result)
    for section_index, section in enumerate(sections):
        section_title = str(section.get("section_title") or section.get("section_label") or f"段落 {section_index + 1}")
        section_range = f"第 {int(section.get('measure_start') or 1)}-{int(section.get('measure_end') or 1)} 小节"
        section_pattern = section.get("strumming") or {}
        section_copy = section_pattern.get("display_pattern") or section_pattern.get("pattern") or ""
        story.append(
            Paragraph(
                _safe_paragraph_text(f"{section_title}  ·  {section_range}{f'  ·  扫弦 {section_copy}' if section_copy else ''}"),
                section_style,
            )
        )

        lines = list(section.get("display_lines") or section.get("lines") or [])
        for line in lines:
            pairs = _build_chord_lyric_pairs(line)
            if not pairs:
                continue

            weights = [max(1.0, len(pair["chord"]) * 0.8, len(pair["lyric"]) * 0.7, 4.5) for pair in pairs]
            total_weight = sum(weights) or 1.0
            col_widths = [(weight / total_weight) * doc.width for weight in weights]
            cells = [
                [Paragraph(_paragraph_placeholder(pair["chord"]), chord_style) for pair in pairs],
                [Paragraph(_paragraph_placeholder(pair["lyric"]), lyric_style) for pair in pairs],
            ]
            line_table = Table(cells, colWidths=col_widths)
            line_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.25, colors.HexColor("#d9e2ea")),
                    ]
                )
            )
            story.append(KeepTogether([line_table, Spacer(1, 4)]))

        story.append(Spacer(1, 6))

    diagrams = list(result.get("chord_diagrams") or [])
    if diagrams:
        story.append(Paragraph("常用和弦", section_style))
        chord_rows = [
            [
                Paragraph("<b>和弦</b>", meta_style),
                Paragraph("<b>按法</b>", meta_style),
                Paragraph("<b>难度</b>", meta_style),
            ]
        ]
        for item in diagrams[:8]:
            chord_rows.append(
                [
                    Paragraph(_safe_paragraph_text(str(item.get("symbol") or "--")), meta_style),
                    Paragraph(_safe_paragraph_text(str(item.get("fingering") or item.get("template") or "--")), meta_style),
                    Paragraph(_safe_paragraph_text(str(item.get("difficulty") or "--")), meta_style),
                ]
            )
        chord_table = Table(chord_rows, colWidths=[doc.width * 0.18, doc.width * 0.52, doc.width * 0.18])
        chord_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ea")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(chord_table)

    def _draw_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#7b8794"))
        canvas.drawRightString(doc_obj.pagesize[0] - doc_obj.rightMargin, 8 * mm, f"第 {canvas.getPageNumber()} 页")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)

    return {
        "instrument_type": "guitar",
        "format": "pdf",
        "file_name": target_path.name,
        "file_path": str(target_path),
        "download_url": _download_url_for(target_path, storage_dir),
        "content_type": "application/pdf",
        "layout_mode": str(layout_mode or "print"),
        "title": result.get("title"),
        "manifest": {"kind": "pdf", "page_count": 0, "pages": []},
    }
