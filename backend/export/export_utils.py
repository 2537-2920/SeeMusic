"""Verovio-backed score export helpers."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any
import re
import xml.etree.ElementTree as ET

try:
    import cairosvg
except (ImportError, OSError):
    cairosvg = None
    print("Warning: cairosvg not found or DLL missing. PDF/SVG export will not work.")
from PIL import Image
import verovio

from backend.config.settings import settings


SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")
EXPORT_SUBDIR = "exports"
PAGE_GAP = 32
PAGE_SIZE_OPTIONS = {
    "A4": {"pageWidth": 2100, "pageHeight": 2970},
    "LETTER": {"pageWidth": 2160, "pageHeight": 2790},
}
COMPACT_EXPORT_OPTIONS = {
    "scale": 82,
    "pageMarginLeft": 80,
    "pageMarginRight": 80,
    "pageMarginTop": 72,
    "pageMarginBottom": 84,
    "spacingSystem": 10,
    "spacingStaff": 10,
    "systemMaxPerPage": 8,
}


class ExportPathError(ValueError):
    """Raised when an export path cannot be safely placed in storage."""


class ExportFileNotFoundError(FileNotFoundError):
    """Raised when a requested export file is missing or outside storage."""


def _configure_verovio_toolkit(toolkit: verovio.toolkit) -> verovio.toolkit:
    package_dir = Path(verovio.__file__).resolve().parent
    resource_dir = package_dir / "data"
    if resource_dir.exists():
        toolkit.setResourcePath(str(resource_dir))
    return toolkit


def _safe_name(value: str, default: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", str(value or default)).strip("._")
    return cleaned or default


def _storage_root(storage_dir: Path | None = None) -> Path:
    root = (storage_dir or settings.storage_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_export_path(resource_id: str, export_format: str, storage_dir: Path | None = None) -> Path:
    root = _storage_root(storage_dir)
    export_dir = (root / EXPORT_SUBDIR).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)

    safe_resource_id = _safe_name(resource_id, "resource")
    safe_format = _safe_name(export_format, "bin").lower()
    candidate = (export_dir / f"{safe_resource_id}.{safe_format}").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ExportPathError("export file path is outside the storage directory") from exc
    return candidate


def _download_url_for(path: Path, storage_dir: Path | None = None) -> str:
    root = _storage_root(storage_dir)
    try:
        relative_path = path.resolve().relative_to(root)
    except ValueError as exc:
        raise ExportFileNotFoundError("export file path is outside the storage directory") from exc
    return "/storage/" + relative_path.as_posix()


def build_export_files(resource_id: str, formats: list[str]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for fmt in formats:
        export_path = _safe_export_path(resource_id, fmt)
        files.append(
            {
                "format": fmt,
                "file_name": export_path.name,
                "file_path": str(export_path),
                "download_url": _download_url_for(export_path),
                "expires_in": 3600,
            }
        )
    return files


def _toolkit_for_export(page_size: str) -> verovio.toolkit:
    toolkit = _configure_verovio_toolkit(verovio.toolkit())
    page_settings = PAGE_SIZE_OPTIONS.get(str(page_size or "A4").upper(), PAGE_SIZE_OPTIONS["A4"])
    toolkit.setOptions(
        {
            "breaks": "auto",
            "pageWidth": int(page_settings["pageWidth"]),
            "pageHeight": int(page_settings["pageHeight"]),
            "scale": int(COMPACT_EXPORT_OPTIONS["scale"]),
            "adjustPageWidth": False,
            "adjustPageHeight": False,
            "svgViewBox": True,
            "pageMarginLeft": int(COMPACT_EXPORT_OPTIONS["pageMarginLeft"]),
            "pageMarginRight": int(COMPACT_EXPORT_OPTIONS["pageMarginRight"]),
            "pageMarginTop": int(COMPACT_EXPORT_OPTIONS["pageMarginTop"]),
            "pageMarginBottom": int(COMPACT_EXPORT_OPTIONS["pageMarginBottom"]),
            "spacingSystem": int(COMPACT_EXPORT_OPTIONS["spacingSystem"]),
            "spacingStaff": int(COMPACT_EXPORT_OPTIONS["spacingStaff"]),
            "systemMaxPerPage": int(COMPACT_EXPORT_OPTIONS["systemMaxPerPage"]),
            "header": "none",
            "footer": "none",
        }
    )
    return toolkit


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _iter_named_children(parent: ET.Element, tag_name: str) -> list[ET.Element]:
    return [child for child in list(parent) if _local_name(child.tag) == tag_name]


def _serialize_child(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode")


def _compact_redundant_measure_attributes(musicxml: str) -> str:
    root = ET.fromstring(str(musicxml or "").encode("utf-8"))
    measures = [element for element in root.iter() if _local_name(element.tag) == "measure"]
    if len(measures) < 2:
        return musicxml

    first_attributes = next((child for child in list(measures[0]) if _local_name(child.tag) == "attributes"), None)
    if first_attributes is None:
        return musicxml

    visual_tags = ("divisions", "key", "time", "staves", "clef", "part-symbol")
    reference_signature = {
        tag: [_serialize_child(child) for child in _iter_named_children(first_attributes, tag)]
        for tag in visual_tags
    }
    allowed_visual_tags = set(visual_tags)

    for measure in measures[1:]:
        attributes = next((child for child in list(measure) if _local_name(child.tag) == "attributes"), None)
        if attributes is None:
            continue
        children = list(attributes)
        if not children:
            attributes.clear()
            measure.remove(attributes)
            continue
        if any(_local_name(child.tag) not in allowed_visual_tags for child in children):
            continue

        current_signature = {
            tag: [_serialize_child(child) for child in _iter_named_children(attributes, tag)]
            for tag in visual_tags
        }
        if current_signature == reference_signature:
            measure.remove(attributes)

    try:
        ET.indent(root, space="  ")
    except AttributeError:  # pragma: no cover
        pass
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _render_svg_pages(score: dict[str, Any], page_size: str) -> list[str]:
    musicxml = _compact_redundant_measure_attributes(str(score.get("musicxml") or ""))
    toolkit = _toolkit_for_export(page_size)
    if not toolkit.loadData(musicxml):
        raise ValueError("MusicXML could not be loaded by Verovio for export")
    return [toolkit.renderToSVG(page_number) for page_number in range(1, int(toolkit.getPageCount() or 0) + 1)] or [toolkit.renderToSVG(1)]


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


def _render_png_pages(score: dict[str, Any], page_size: str) -> list[Image.Image]:
    if cairosvg is None:
        raise RuntimeError("cairosvg is not available. Please install it and its system dependencies (like Cairo) to export as PNG/PDF.")
    images: list[Image.Image] = []
    for svg_markup in _render_svg_pages(score, page_size):
        png_bytes = cairosvg.svg2png(bytestring=svg_markup.encode("utf-8"))
        image = Image.open(BytesIO(png_bytes))
        image.load()
        images.append(image.convert("RGBA"))
    return images


def _flatten_image_to_white_rgb(image: Image.Image) -> Image.Image:
    rgba_image = image.convert("RGBA")
    white_background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
    white_background.alpha_composite(rgba_image)
    return white_background.convert("RGB")


def _merge_png_pages(images: list[Image.Image]) -> bytes:
    if not images:
        raise ValueError("no score pages available for PNG export")
    if len(images) == 1:
        buffer = BytesIO()
        images[0].save(buffer, format="PNG")
        return buffer.getvalue()

    width = max(image.width for image in images)
    height = sum(image.height for image in images) + PAGE_GAP * (len(images) - 1)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))

    cursor_y = 0
    for image in images:
        offset_x = max((width - image.width) // 2, 0)
        canvas.alpha_composite(image, (offset_x, cursor_y))
        cursor_y += image.height + PAGE_GAP

    buffer = BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _merge_pdf_pages(images: list[Image.Image]) -> bytes:
    if not images:
        raise ValueError("no score pages available for PDF export")
    converted = [_flatten_image_to_white_rgb(image) for image in images]
    buffer = BytesIO()
    converted[0].save(buffer, format="PDF", save_all=True, append_images=converted[1:])
    return buffer.getvalue()


def _merge_svg_pages(svg_pages: list[str]) -> str:
    if len(svg_pages) == 1:
        return svg_pages[0]

    page_roots = [ET.fromstring(svg.encode("utf-8")) for svg in svg_pages]
    page_sizes = [_svg_dimensions(svg) for svg in svg_pages]
    width = max(page_width for page_width, _ in page_sizes)
    height = sum(page_height for _, page_height in page_sizes) + PAGE_GAP * (len(page_sizes) - 1)

    merged_root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "viewBox": f"0 0 {width} {height}",
            "version": "1.1",
        },
    )
    defs = ET.SubElement(merged_root, "defs")

    cursor_y = 0
    for index, page_root in enumerate(page_roots, start=1):
        page_width, page_height = page_sizes[index - 1]
        for child in list(page_root):
            if child.tag.endswith("defs"):
                for defs_child in list(child):
                    defs.append(defs_child)

        group = ET.SubElement(merged_root, "g", {"id": f"page-{index}", "transform": f"translate(0 {cursor_y})"})
        for child in list(page_root):
            if child.tag.endswith("defs"):
                continue
            group.append(child)
        cursor_y += page_height + PAGE_GAP

    return ET.tostring(merged_root, encoding="unicode", xml_declaration=True)


def _midi_bytes(score: dict[str, Any], page_size: str) -> bytes:
    toolkit = _toolkit_for_export(page_size)
    if not toolkit.loadData(str(score.get("musicxml") or "")):
        raise ValueError("MusicXML could not be loaded by Verovio for MIDI export")
    return base64.b64decode(toolkit.renderToMIDI())


def _manifest_from_pages(svg_pages: list[str], *, export_format: str, page_size: str, with_annotations: bool) -> dict[str, Any]:
    page_descriptors = []
    for index, svg_markup in enumerate(svg_pages, start=1):
        width, height = _svg_dimensions(svg_markup)
        page_descriptors.append({"page_number": index, "width": width, "height": height})
    return {
        "kind": export_format,
        "page_size": page_size,
        "with_annotations": bool(with_annotations),
        "page_count": len(page_descriptors),
        "pages": page_descriptors,
    }


def build_score_export_payload(
    score: dict[str, Any],
    export_format: str,
    page_size: str = "A4",
    with_annotations: bool = True,
    file_stem: str | None = None,
) -> dict[str, Any]:
    if export_format == "midi":
        manifest = {
            "kind": "midi",
            "page_size": page_size,
            "with_annotations": bool(with_annotations),
            "page_count": 0,
            "pages": [],
        }
    else:
        manifest = _manifest_from_pages(
            _render_svg_pages(score, page_size),
            export_format=export_format,
            page_size=page_size,
            with_annotations=with_annotations,
        )

    export_path = _safe_export_path(file_stem or score["score_id"], export_format)
    return {
        "score_id": score["score_id"],
        "format": export_format,
        "file_name": export_path.name,
        "file_path": str(export_path),
        "download_url": _download_url_for(export_path),
        "manifest": manifest,
    }


def write_score_export(
    score: dict[str, Any],
    export_format: str,
    storage_dir: Path,
    page_size: str = "A4",
    with_annotations: bool = True,
    file_stem: str | None = None,
) -> dict[str, Any]:
    file_path = _safe_export_path(file_stem or score["score_id"], export_format, storage_dir)
    payload = build_score_export_payload(
        score,
        export_format=export_format,
        page_size=page_size,
        with_annotations=with_annotations,
        file_stem=file_stem,
    )

    if export_format == "midi":
        file_bytes = _midi_bytes(score, page_size)
    elif export_format == "png":
        file_bytes = _merge_png_pages(_render_png_pages(score, page_size))
    elif export_format == "pdf":
        file_bytes = _merge_pdf_pages(_render_png_pages(score, page_size))
    elif export_format == "svg":
        file_bytes = _merge_svg_pages(_render_svg_pages(score, page_size)).encode("utf-8")
    else:
        raise ValueError(f"unsupported export format: {export_format}")

    file_path.write_bytes(file_bytes)
    payload["download_url"] = _download_url_for(file_path, storage_dir)
    payload["file_path"] = str(file_path)
    payload["file_name"] = file_path.name
    return payload
