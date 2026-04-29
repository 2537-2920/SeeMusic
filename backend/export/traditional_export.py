"""Traditional jianpu export helpers backed by jianpu-ly and LilyPond."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
import re
import xml.etree.ElementTree as ET

SUPPORTED_TRADITIONAL_EXPORT_FORMATS = {"jianpu", "ly", "pdf", "svg"}
SEGMENT_VALUES = (4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25)
SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")
# Symbol-level markup is shared across both instruments because users may add
# the same technique to either (e.g. trill works on dizi AND guzheng). The
# instrument-specific dispatch below picks which subset gets applied.
COMMON_TECHNIQUE_SYMBOL_MARKUP = {
    # 颤音：通用斜体 tr，对应前端 "tr" 角标
    '^"颤"': r'^\markup { \center-align \italic \fontsize #-3 "tr" }',
    # 波音：mordent 形 𝆑，对应前端 "𝆑" 角标
    '^"波"': r'^\markup { \center-align \fontsize #-3 "𝆑" }',
    # 滑音：箭头，与前端 "↗" 一致
    '^"滑"': r'^\markup { \center-align \fontsize #-3 "↗" }',
    # 泛音：圆圈，与前端 "○" 一致
    '^"○"': r'^\markup { \center-align \fontsize #-3 "○" }',
    # 断奏 / 打音：staccato 点
    '^"断"': r'^\markup { \center-align \fontsize #-3 "·" }',
    # 重音 / 叠音：accent
    '^"重"': r'^\markup { \center-align \fontsize #-3 ">" }',
    # 换气点：通用换气逗号
    '^"换"': r'^\markup { \center-align \fontsize #-3 "," }',
    # 倚音：小字号 "倚"
    '^"倚"': r'^\markup { \center-align \italic \fontsize #-4 "倚" }',
}

GUZHENG_TECHNIQUE_SYMBOL_MARKUP = {
    **COMMON_TECHNIQUE_SYMBOL_MARKUP,
    # 上下滑音：箭头线（接近通用记谱里 portamento/glissando 的指向）
    '^"上滑"': r'^\markup { \center-align \fontsize #-3 "↗" }',
    '^"下滑"': r'^\markup { \center-align \fontsize #-3 "↘" }',
    # 按音：波浪线（与前端 ∽ 标记一致；上游 token 已直接发 ∽）
    '^"∽"': r'^\markup { \center-align \fontsize #-3 "∽" }',
    # 向后兼容：历史产物可能仍输出 ^"按"。
    '^"按"': r'^\markup { \center-align \fontsize #-3 "∽" }',
    # 摇指（heuristic 推导出的）：三斜线，与前端 "⫻" 角标对齐
    '^"摇"': r'^\markup { \center-align \fontsize #-3 \concat { "/" "/" "/" } }',
}

# 笛子专属技法符号
DIZI_TECHNIQUE_SYMBOL_MARKUP = dict(COMMON_TECHNIQUE_SYMBOL_MARKUP)


class TraditionalExportError(RuntimeError):
    """Raised when a traditional export request cannot be completed."""


class TraditionalExportDependencyError(TraditionalExportError):
    """Raised when required external tools are unavailable."""


class TraditionalExportCompileError(TraditionalExportError):
    """Raised when jianpu-ly or LilyPond compilation fails."""


def _safe_file_stem(value: str | None, default: str) -> str:
    raw = str(value or "").strip()
    if raw:
        return raw
    return default


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
        raise TraditionalExportError("export file path is outside the storage directory") from exc
    return candidate


def _download_url_for(path: Path, storage_dir: Path | None = None) -> str:
    root = _storage_root(storage_dir)
    try:
        relative_path = path.resolve().relative_to(root)
    except ValueError as exc:
        raise TraditionalExportError("export file path is outside the storage directory") from exc
    return "/storage/" + relative_path.as_posix()


def _escape_jianpu_text(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"').strip()


def _technique_token(note: dict[str, Any], instrument_type: str) -> str:
    tags = [str(item or "").strip() for item in list(note.get("technique_tags") or []) if str(item or "").strip()]

    # User-asserted techniques (from MusicXML <notations>) are checked first.
    # The frontend manual-edit workbench writes these tags via _extract_user_techniques
    # in backend/core/guitar/lead_sheet.py and they survive the
    # melody-materialization pipeline thanks to the user_techniques carry-over
    # in guzheng/dizi notation modules. This is what makes manual edits visible
    # in the final PDF output.
    user_priority = (
        ("user_trill", "颤"),
        ("user_tremolo", "摇"),
        ("user_mordent", "波"),
        ("user_glissando", "滑"),
        ("user_harmonic", "○"),
        ("user_staccato", "断"),
        ("user_accent", "重"),
    )
    for label, short in user_priority:
        if label in tags:
            return short

    if instrument_type == "guzheng":
        for label, short in (
            ("摇指候选", "摇"),
            ("上滑音候选", "上滑"),
            ("下滑音候选", "下滑"),
            ("按音候选", "∽"),
        ):
            if label in tags:
                return short
    else:
        for label, short in (
            ("换气点", "换"),
            ("滑音候选", "滑"),
            ("倚音候选", "倚"),
            ("颤音/长音保持候选", "颤"),
        ):
            if label in tags:
                return short
    return str(note.get("annotation_text") or "").strip()


def _note_annotation_tokens(
    note: dict[str, Any],
    *,
    instrument_type: str,
    annotation_layer: str,
) -> list[str]:
    if bool(note.get("is_rest")):
        return []

    layer = str(annotation_layer or "all").strip().lower()
    fingering_text = str(note.get("fingering_text") or "").strip()
    technique_text = _technique_token(note, instrument_type)
    tokens: list[str] = []

    if layer in {"technique", "all"} and technique_text:
        tokens.append(f'^"{_escape_jianpu_text(technique_text)}"')
    if layer in {"fingering", "all"} and fingering_text:
        tokens.append(f'_"{_escape_jianpu_text(fingering_text)}"')
    return tokens


def _render_degree_token(note: dict[str, Any]) -> str:
    raw = str(note.get("degree_display") or "0").strip() or "0"
    if raw == "0":
        return "0"

    accidental = ""
    digit = raw
    if raw[:1] in {"#", "b"}:
        accidental = raw[:1]
        digit = raw[1:] or raw

    octave_marks = note.get("octave_marks") or {}
    above = int(octave_marks.get("above") or 0)
    below = int(octave_marks.get("below") or 0)
    suffix = "'" * max(above, 0) + "," * max(below, 0)
    return f"{accidental}{digit}{suffix}"


def _segment_token(degree_token: str, beats: float) -> list[str]:
    if beats >= 4.0 - 1e-6:
        return [degree_token, "-", "-", "-"]
    if beats >= 3.0 - 1e-6:
        return [degree_token, "-", "-"]
    if beats >= 2.0 - 1e-6:
        return [degree_token, "-"]
    if beats >= 1.5 - 1e-6:
        return [f"{degree_token}."]
    if beats >= 1.0 - 1e-6:
        return [degree_token]
    if beats >= 0.75 - 1e-6:
        return [f"q{degree_token}."]
    if beats >= 0.5 - 1e-6:
        return [f"q{degree_token}"]
    return [f"s{degree_token}"]


def _decompose_duration(beats: float) -> list[float]:
    remaining = round(max(float(beats or 0.0), 0.25) * 4) / 4.0
    segments: list[float] = []
    for value in SEGMENT_VALUES:
        while remaining >= value - 1e-6:
            segments.append(value)
            remaining = round((remaining - value) * 4) / 4.0
    if remaining > 1e-6:
        segments.append(max(0.25, remaining))
    return segments or [1.0]


def _quantize_export_beats(beats: float) -> float:
    return round(max(float(beats or 0.0), 0.0) * 4) / 4.0


def _rest_note(beats: float) -> dict[str, Any]:
    return {
        "degree_display": "0",
        "beats": beats,
        "display_beats": beats,
        "is_rest": True,
        "octave_marks": {"above": 0, "below": 0},
    }


def _note_tokens(
    note: dict[str, Any],
    *,
    instrument_type: str,
    annotation_layer: str,
) -> list[str]:
    base = _render_degree_token(note)
    segments = _decompose_duration(float(note.get("display_beats") or note.get("beats") or 1.0))
    tokens: list[str] = []
    annotation_tokens = _note_annotation_tokens(
        note,
        instrument_type=instrument_type,
        annotation_layer=annotation_layer,
    )
    for index, segment in enumerate(segments):
        segment_tokens = _segment_token(base, segment)
        if index:
            tokens.append("~")
        if index == 0 and segment_tokens:
            tokens.append(segment_tokens[0])
            tokens.extend(annotation_tokens)
            tokens.extend(segment_tokens[1:])
        else:
            tokens.extend(segment_tokens)
    return tokens


def _normalize_measure_notes(measure: dict[str, Any]) -> list[dict[str, Any]]:
    total_beats = _quantize_export_beats(float(measure.get("beats") or measure.get("total_beats") or 4.0))
    notes = sorted(
        [dict(item) for item in list(measure.get("notes") or [])],
        key=lambda item: (float(item.get("start_beat") or 1.0), str(item.get("note_id") or "")),
    )
    if total_beats <= 0:
        return notes

    cursor = 1.0
    normalized: list[dict[str, Any]] = []

    for raw_note in notes:
        start_beat = max(_quantize_export_beats(float(raw_note.get("start_beat") or 1.0)), 1.0)
        duration_beats = _quantize_export_beats(float(raw_note.get("display_beats") or raw_note.get("beats") or 0.0))
        if duration_beats <= 0:
            continue

        measure_end = total_beats + 1.0
        if start_beat >= measure_end - 1e-6:
            continue

        if start_beat > cursor + 1e-6:
            gap_beats = _quantize_export_beats(start_beat - cursor)
            if gap_beats > 0:
                normalized.append(_rest_note(gap_beats))
                cursor = round(cursor + gap_beats, 3)

        effective_start = max(start_beat, cursor)
        overlap_trim = _quantize_export_beats(effective_start - start_beat)
        if overlap_trim >= duration_beats - 1e-6:
            continue

        usable_beats = _quantize_export_beats(duration_beats - overlap_trim)
        remaining_in_measure = _quantize_export_beats(measure_end - effective_start)
        segment_beats = min(usable_beats, remaining_in_measure)
        if segment_beats <= 0:
            continue

        note = dict(raw_note)
        note["start_beat"] = effective_start
        note["beats"] = segment_beats
        note["display_beats"] = segment_beats
        normalized.append(note)
        cursor = round(effective_start + segment_beats, 3)
        if cursor >= measure_end - 1e-6:
            cursor = measure_end
            break

    tail_beats = _quantize_export_beats((total_beats + 1.0) - cursor)
    if tail_beats > 0:
        normalized.append(_rest_note(tail_beats))

    return normalized


def _measure_tokens(
    measure: dict[str, Any],
    *,
    instrument_type: str,
    annotation_layer: str,
) -> list[str]:
    measure_tokens: list[str] = []
    for note in _normalize_measure_notes(measure):
        measure_tokens.extend(
            _note_tokens(
                note,
                instrument_type=instrument_type,
                annotation_layer=annotation_layer,
            )
        )
    if not measure_tokens:
        return ["0"]
    return measure_tokens


def _apply_traditional_symbol_markup(lilypond_text: str, *, instrument_type: str) -> str:
    updated = str(lilypond_text or "")
    if instrument_type == "guzheng":
        for source, replacement in GUZHENG_TECHNIQUE_SYMBOL_MARKUP.items():
            updated = updated.replace(source, replacement)
    elif instrument_type == "dizi":
        for source, replacement in DIZI_TECHNIQUE_SYMBOL_MARKUP.items():
            updated = updated.replace(source, replacement)
    return updated


def _build_annotation_comments(result: dict[str, Any], instrument_type: str) -> list[str]:
    comments = ["% Generated by SeeMusic traditional export bridge"]
    if instrument_type == "guzheng":
        pentatonic = result.get("pentatonic_summary") or {}
        comments.append(
            "% Guzheng annotations: "
            f"direct_open={int(pentatonic.get('direct_open_notes') or 0)}, "
            f"press_candidates={int(pentatonic.get('press_note_candidates') or 0)}"
        )
    else:
        playability = result.get("playability_summary") or {}
        comments.append(
            "% Dizi annotations: "
            f"half_hole={int(playability.get('half_hole_candidates') or 0)}, "
            f"special={int(playability.get('special_fingering_candidates') or 0)}, "
            f"out_of_range={int(playability.get('out_of_range_notes') or 0)}"
        )
    return comments


def _layout_directives(layout_mode: str) -> list[str]:
    resolved = str(layout_mode or "preview").strip().lower()
    directives = [
        "LP:",
        "#(set-default-paper-size \"a4\")",
        "\\paper {",
        "  indent = 0\\mm",
        "  top-margin = 10\\mm",
        "  bottom-margin = 10\\mm",
        "  left-margin = 12\\mm",
        "  right-margin = 12\\mm",
        f"  print-page-number = {'##t' if resolved == 'print' else '##f'}",
        "}",
        ":LP",
    ]
    if resolved == "preview":
        directives.insert(0, "RaggedLast")
    return directives


def build_jianpu_source(
    result: dict[str, Any],
    *,
    instrument_type: str,
    layout_mode: str = "preview",
    annotation_layer: str = "all",
) -> str:
    title = str(result.get("title") or ("Untitled Guzheng Chart" if instrument_type == "guzheng" else "Untitled Dizi Chart"))
    key_text = str(result.get("key") or "C")
    jianpu_key = f"1={key_text[:-1] if key_text.endswith('m') else key_text}"
    time_signature = str(result.get("time_signature") or "4/4")
    tempo = int(result.get("tempo") or 120)
    measures = list((result.get("jianpu_ir") or {}).get("measures") or result.get("measures") or [])
    instrument_line = "instrument=Guzheng" if instrument_type == "guzheng" else "instrument=Flute"

    lines = [
        * _build_annotation_comments(result, instrument_type),
        f"% layout_mode={layout_mode} annotation_layer={annotation_layer}",
        f"title={title}",
        instrument_line,
        "NoBarNums",
        "NoIndent",
        * _layout_directives(layout_mode),
        jianpu_key,
        time_signature,
        f"4={tempo}",
        "",
    ]

    for measure in measures:
        measure_line = " ".join(
            _measure_tokens(
                measure,
                instrument_type=instrument_type,
                annotation_layer=annotation_layer,
            )
        )
        lines.append(f"{measure_line} |")

    lines.append("")
    return "\n".join(lines)


def _resolve_jianpu_ly_command() -> str | None:
    for command_name in ("jianpu-ly", "jianpu-ly.py", "jianpu_ly"):
        resolved = shutil.which(command_name)
        if resolved:
            return resolved

    for module_name in ("jianpu_ly",):
        if importlib.util.find_spec(module_name):
            return f"{sys.executable} -m {module_name}"
    return None


def _resolve_lilypond_command() -> str | None:
    return shutil.which("lilypond")


def _command_args(command: str) -> list[str]:
    return str(command).split()


def _compile_to_lilypond(jianpu_source: str, workdir: Path, source_name: str) -> tuple[str, Path]:
    jianpu_command = _resolve_jianpu_ly_command()
    if not jianpu_command:
        raise TraditionalExportDependencyError(
            "当前环境未安装 jianpu-ly，暂时只能导出 .jianpu 源。请先安装 jianpu-ly 后再导出 LilyPond 或 PDF。"
        )

    input_path = workdir / f"{source_name}.jianpu"
    input_path.write_text(jianpu_source, encoding="utf-8")
    completed = subprocess.run(
        [*_command_args(jianpu_command), str(input_path)],
        capture_output=True,
        text=True,
        cwd=str(workdir),
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        detail = (completed.stderr or completed.stdout or "jianpu-ly did not produce LilyPond output").strip()
        raise TraditionalExportCompileError(f"jianpu-ly 转换失败：{detail}")

    lilypond_text = completed.stdout
    ly_path = workdir / f"{source_name}.ly"
    ly_path.write_text(lilypond_text, encoding="utf-8")
    return lilypond_text, ly_path


def _compile_pdf_from_lilypond(ly_path: Path, workdir: Path, output_stem: str) -> Path:
    lilypond_command = _resolve_lilypond_command()
    if not lilypond_command:
        raise TraditionalExportDependencyError(
            "当前环境未安装 LilyPond，暂时只能导出源码。请先安装 LilyPond 后再导出 PDF。"
        )

    completed = subprocess.run(
        [lilypond_command, "-fpdf", "-o", output_stem, str(ly_path)],
        capture_output=True,
        text=True,
        cwd=str(workdir),
        check=False,
    )
    output_path = workdir / f"{output_stem}.pdf"
    if completed.returncode != 0 or not output_path.exists():
        detail = (completed.stderr or completed.stdout or "LilyPond did not produce a PDF file").strip()
        raise TraditionalExportCompileError(f"LilyPond 编译失败：{detail}")
    return output_path


def _natural_sort_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _svg_dimensions(svg_markup: str) -> tuple[int, int]:
    root = ET.fromstring(svg_markup.encode("utf-8"))
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = view_box.split()
        if len(parts) == 4:
            return int(float(parts[2])), int(float(parts[3]))
    width = root.attrib.get("width")
    height = root.attrib.get("height")
    return int(float(width or 2100)), int(float(height or 2970))


def _compile_svg_from_lilypond(ly_path: Path, workdir: Path, output_stem: str) -> list[Path]:
    lilypond_command = _resolve_lilypond_command()
    if not lilypond_command:
        raise TraditionalExportDependencyError(
            "当前环境未安装 LilyPond，暂时无法生成统一排版预览。请先安装 LilyPond 后再查看 SVG 或导出 PDF。"
        )

    completed = subprocess.run(
        [lilypond_command, "-fsvg", "-dno-point-and-click", "-o", output_stem, str(ly_path)],
        capture_output=True,
        text=True,
        cwd=str(workdir),
        check=False,
    )
    svg_paths = sorted(workdir.glob(f"{output_stem}*.svg"), key=lambda path: _natural_sort_key(path.name))
    if completed.returncode != 0 or not svg_paths:
        detail = (completed.stderr or completed.stdout or "LilyPond did not produce SVG output").strip()
        raise TraditionalExportCompileError(f"LilyPond SVG 编译失败：{detail}")
    return svg_paths


def export_traditional_score(
    result: dict[str, Any],
    *,
    instrument_type: str,
    export_format: str,
    storage_dir: Path,
    file_stem: str | None = None,
    layout_mode: str = "preview",
    annotation_layer: str = "all",
) -> dict[str, Any]:
    normalized_format = str(export_format or "jianpu").strip().lower()
    if normalized_format not in SUPPORTED_TRADITIONAL_EXPORT_FORMATS:
        raise TraditionalExportError(f"unsupported traditional export format: {normalized_format}")

    safe_stem = _safe_file_stem(
        file_stem,
        default=f"{instrument_type}_{str(result.get('title') or 'jianpu').strip().replace(' ', '_')}",
    )
    jianpu_source = build_jianpu_source(
        result,
        instrument_type=instrument_type,
        layout_mode=layout_mode,
        annotation_layer=annotation_layer,
    )
    source_digest = hashlib.sha1(
        f"{instrument_type}|{layout_mode}|{annotation_layer}|{normalized_format}|{jianpu_source}".encode("utf-8")
    ).hexdigest()[:10]
    versioned_stem = f"{safe_stem}_{source_digest}"
    target_path = _safe_export_path(versioned_stem, normalized_format, storage_dir)

    payload: dict[str, Any] = {
        "instrument_type": instrument_type,
        "format": normalized_format,
        "file_name": target_path.name,
        "file_path": str(target_path),
        "download_url": _download_url_for(target_path, storage_dir),
        "render_source": "jianpu_ly",
        "layout_mode": layout_mode,
        "annotation_layer": annotation_layer,
        "title": result.get("title"),
        "dependencies": {
            "jianpu_ly_available": bool(_resolve_jianpu_ly_command()),
            "lilypond_available": bool(_resolve_lilypond_command()),
        },
        "manifest": {
            "kind": normalized_format,
            "page_count": 0,
            "pages": [],
        },
    }

    if normalized_format == "jianpu":
        target_path.write_text(jianpu_source, encoding="utf-8")
        payload["content_type"] = "text/plain; charset=utf-8"
        payload["manifest"]["source_format"] = "jianpu-ly"
        return payload

    with tempfile.TemporaryDirectory(prefix="traditional_export_") as temp_dir:
        workdir = Path(temp_dir)
        lilypond_text, ly_path = _compile_to_lilypond(jianpu_source, workdir, source_name="score")
        lilypond_text = _apply_traditional_symbol_markup(lilypond_text, instrument_type=instrument_type)
        ly_path.write_text(lilypond_text, encoding="utf-8")
        if normalized_format == "ly":
            target_path.write_text(lilypond_text, encoding="utf-8")
            payload["content_type"] = "text/plain; charset=utf-8"
            payload["manifest"]["source_format"] = "lilypond"
            return payload
        if normalized_format == "svg":
            svg_paths = _compile_svg_from_lilypond(ly_path, workdir, output_stem="compiled")
            preview_pages: list[dict[str, Any]] = []
            for page_index, svg_path in enumerate(svg_paths, start=1):
                page_target = _safe_export_path(f"{versioned_stem}_page_{page_index}", "svg", storage_dir)
                svg_markup = svg_path.read_text(encoding="utf-8")
                page_target.write_text(svg_markup, encoding="utf-8")
                width, height = _svg_dimensions(svg_markup)
                preview_pages.append(
                    {
                        "page_number": page_index,
                        "file_name": page_target.name,
                        "file_path": str(page_target),
                        "download_url": _download_url_for(page_target, storage_dir),
                        "width": width,
                        "height": height,
                    }
                )

            first_page = preview_pages[0]
            payload["file_name"] = first_page["file_name"]
            payload["file_path"] = first_page["file_path"]
            payload["download_url"] = first_page["download_url"]
            payload["content_type"] = "image/svg+xml"
            payload["preview_pages"] = preview_pages
            payload["manifest"]["kind"] = "svg"
            payload["manifest"]["page_count"] = len(preview_pages)
            payload["manifest"]["pages"] = [
                {
                    "page_number": page["page_number"],
                    "width": page["width"],
                    "height": page["height"],
                    "download_url": page["download_url"],
                }
                for page in preview_pages
            ]
            return payload

        pdf_path = _compile_pdf_from_lilypond(ly_path, workdir, output_stem="compiled")
        target_path.write_bytes(pdf_path.read_bytes())
        payload["content_type"] = "application/pdf"
        payload["manifest"]["kind"] = "pdf"
        return payload
