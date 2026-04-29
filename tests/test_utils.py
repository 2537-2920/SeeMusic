import json
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image

from backend.config.settings import settings
import backend.export.traditional_export as traditional_export
from backend.core.dizi.notation import generate_dizi_score
from backend.core.guzheng.notation import generate_guzheng_score
from backend.core.pitch.pitch_comparison import load_pitch_sequence_json
from backend.core.pitch.pitch_sequence_utils import compress_pitch_sequence_to_note_events, expand_note_events_to_pitch_sequence
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.export.export_utils import (
    _flatten_image_to_white_rgb,
    _compact_redundant_measure_attributes,
    build_export_files,
    build_score_export_payload,
    write_score_export,
)
from backend.export.guitar_export import export_guitar_lead_sheet_pdf
from backend.export.traditional_export import TraditionalExportDependencyError, build_jianpu_source, export_traditional_score
from backend.utils.audio_logger import AUDIO_LOGS, build_audio_log_payload, record_audio_log
from backend.utils.data_visualizer import build_pitch_curve


def test_audio_logger_records_entries_in_memory():
    entry = record_audio_log({"file_name": "demo.wav", "sample_rate": 16000, "duration": 1.0})
    assert entry["log_id"].startswith("log_")
    assert len(AUDIO_LOGS) == 1


def test_audio_logger_builds_debug_metadata_and_persists(tmp_path: Path, monkeypatch):
    log_file = tmp_path / "audio_logs.jsonl"
    monkeypatch.setattr("backend.utils.audio_logger.DEFAULT_AUDIO_LOG_FILE", log_file)

    payload = build_audio_log_payload(
        file_name="demo.wav",
        audio_bytes=b"\x00" * 32000,
        sample_rate=16000,
        analysis_id="an_demo",
        source="test",
        stage="unit",
        params={"algorithm": "yin"},
    )
    entry = record_audio_log(payload)

    assert entry["analysis_id"] == "an_demo"
    assert entry["sample_rate"] == 16000
    assert entry["duration"] == 1.0
    assert entry["byte_size"] == 32000
    assert entry["source"] == "test"
    assert entry["stage"] == "unit"
    assert log_file.exists()
    persisted = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert persisted[-1]["log_id"] == entry["log_id"]


def test_build_pitch_curve_computes_deviation_values():
    chart = build_pitch_curve(
        [{"time": 0.0, "frequency": 440.0}, {"time": 0.5, "frequency": 442.0}],
        [{"time": 0.0, "frequency": 438.0}, {"time": 0.5, "frequency": 444.0}],
    )
    assert chart["x_axis"] == [0.0, 0.5]
    assert chart["deviation_curve"] == [-2.0, 2.0]
    assert chart["summary"]["matched_points"] == 2


def test_build_pitch_curve_aligns_misaligned_sequences():
    chart = build_pitch_curve(
        [{"time": 0.0, "frequency": 440.0}, {"time": 0.5, "frequency": 450.0}, {"time": 1.0, "frequency": 460.0}],
        [{"time": 0.25, "frequency": 445.0}, {"time": 0.75, "frequency": 455.0}, {"time": 1.25, "frequency": 465.0}],
    )

    assert chart["x_axis"] == [0.25, 0.75]
    assert chart["reference_curve"] == [445.0, 455.0]
    assert chart["user_curve"] == [445.0, 455.0]
    assert chart["summary"]["accuracy"] == 100.0


def test_load_pitch_sequence_json_supports_nested_api_payload(tmp_path: Path):
    payload_path = tmp_path / "pitch.json"
    payload_path.write_text(
        json.dumps(
            {
                "data": {
                    "pitch_sequence": [
                        {"time": 0.0, "frequency": 440.0, "confidence": 0.9},
                        {"time": 0.5, "frequency": 442.0, "confidence": 0.8},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = load_pitch_sequence_json(str(payload_path))

    assert result[0]["time"] == 0.0
    assert result[0]["frequency"] == 440.0
    assert result[1]["confidence"] == 0.8


def test_compress_pitch_sequence_to_note_events_merges_adjacent_frames():
    note_events = compress_pitch_sequence_to_note_events(
        [
            {"time": 0.0, "frequency": 440.0, "duration": 0.01, "note": "A4", "voiced": True},
            {"time": 0.01, "frequency": 442.0, "duration": 0.01, "note": "A4", "voiced": True},
            {"time": 0.02, "frequency": 0.0, "duration": 0.01, "note": "Rest", "voiced": False},
            {"time": 0.05, "frequency": 493.88, "duration": 0.01, "note": "B4", "voiced": True},
        ],
        hop_ms=10,
    )

    assert note_events == [
        {"start": 0.0, "end": 0.02, "note": "A4", "frequency_avg": 441.0},
        {"start": 0.05, "end": 0.06, "note": "B4", "frequency_avg": 493.88},
    ]


def test_expand_note_events_to_pitch_sequence_rebuilds_compatible_frames():
    sequence = expand_note_events_to_pitch_sequence(
        [{"start": 0.0, "end": 0.025, "note": "A4", "frequency_avg": 440.0}],
        hop_ms=10,
    )

    assert [point["time"] for point in sequence] == [0.0, 0.01, 0.02]
    assert sequence[-1]["duration"] == 0.005
    assert all(point["note"] == "A4" for point in sequence)


def test_build_export_files_returns_downloadable_entries():
    files = build_export_files("resource_001", ["pdf", "png"])
    assert len(files) == 2
    assert files[0]["download_url"].endswith(".pdf")


def test_build_score_export_payload_supports_visual_and_midi_formats():
    score = build_score_from_pitch_sequence([{"time": 0.0, "frequency": 440.0, "duration": 0.5}])
    midi_payload = build_score_export_payload(score, "midi")
    pdf_payload = build_score_export_payload(score, "pdf", page_size="A4", with_annotations=True)
    assert midi_payload["manifest"]["kind"] == "midi"
    assert pdf_payload["manifest"]["kind"] == "pdf"
    assert pdf_payload["manifest"]["page_count"] >= 1
    assert pdf_payload["manifest"]["pages"]


def test_write_score_export_persists_real_files():
    score = build_score_from_pitch_sequence([{"time": 0.0, "frequency": 440.0, "duration": 0.5}])

    midi_payload = write_score_export(score, "midi", settings.storage_dir)
    png_payload = write_score_export(score, "png", settings.storage_dir)
    pdf_payload = write_score_export(score, "pdf", settings.storage_dir)

    for payload in (midi_payload, png_payload, pdf_payload):
        file_path = Path(payload["file_path"])
        assert file_path.exists()
        assert file_path.stat().st_size > 0
        assert payload["download_url"].startswith("/storage/exports/")


def test_flatten_image_to_white_rgb_replaces_transparent_background():
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    image.putpixel((0, 0), (0, 0, 0, 255))

    flattened = _flatten_image_to_white_rgb(image)

    assert flattened.mode == "RGB"
    assert flattened.getpixel((1, 1)) == (255, 255, 255)
    assert flattened.getpixel((0, 0)) == (0, 0, 0)


def test_build_jianpu_source_outputs_header_and_bar_lines():
    result = generate_guzheng_score(
        key="G",
        tempo=96,
        time_signature="4/4",
        style="traditional",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 1.0, "pitch": "B4"},
        ],
        title="古筝导出测试",
    )

    source = build_jianpu_source(result, instrument_type="guzheng", layout_mode="preview", annotation_layer="all")

    assert "title=古筝导出测试" in source
    assert "1=G" in source
    assert "4/4" in source
    assert "4=96" in source
    assert "LP:" in source
    assert "|" in source


def test_build_jianpu_source_applies_annotation_layer_marks():
    result = generate_dizi_score(
        key="G",
        tempo=92,
        time_signature="4/4",
        flute_type="G",
        style="traditional",
        melody=[{"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"}],
        title="笛子标注测试",
    )

    source = build_jianpu_source(result, instrument_type="dizi", layout_mode="preview", annotation_layer="all")

    assert '^"' in source or '_"' in source


def test_apply_traditional_symbol_markup_replaces_guzheng_techniques_with_small_symbols():
    lilypond_text = (
        'c4 ^"上滑" d4 ^"下滑" e4 ^"按" f4 ^"摇" g4 _"11弦"\n'
    )

    result = traditional_export._apply_traditional_symbol_markup(
        lilypond_text,
        instrument_type="guzheng",
    )

    assert '^"上滑"' not in result
    assert '^"下滑"' not in result
    assert '^"按"' not in result
    assert '^"摇"' not in result
    assert 'fontsize #-3 "↗"' in result
    assert 'fontsize #-3 "↘"' in result
    assert 'fontsize #-3 "∽"' in result
    assert 'fontsize #-3 \\concat { "/" "/" "/" }' in result
    assert '_"11弦"' in result


def test_build_jianpu_source_pads_gaps_and_clamps_measure_overflow():
    result = {
        "title": "小节修正测试",
        "key": "G",
        "tempo": 88,
        "time_signature": "4/4",
        "jianpu_ir": {
            "measures": [
                {
                    "measure_no": 1,
                    "beats": 4.0,
                    "notes": [
                        {
                            "degree_display": "1",
                            "start_beat": 1.0,
                            "beats": 1.0,
                            "display_beats": 1.0,
                            "is_rest": False,
                            "octave_marks": {"above": 0, "below": 0},
                        },
                        {
                            "degree_display": "2",
                            "start_beat": 2.5,
                            "beats": 2.0,
                            "display_beats": 2.0,
                            "is_rest": False,
                            "octave_marks": {"above": 0, "below": 0},
                        },
                    ],
                }
            ]
        },
        "pentatonic_summary": {"direct_open_notes": 1, "press_note_candidates": 0},
    }

    source = build_jianpu_source(result, instrument_type="guzheng", layout_mode="preview", annotation_layer="basic")

    assert "q0" in source
    assert "1 q0 2 - q0 |" in source
    assert "2 - -" not in source


def test_export_traditional_score_writes_jianpu_source(tmp_path: Path):
    result = generate_dizi_score(
        key="G",
        tempo=92,
        time_signature="4/4",
        flute_type="G",
        style="traditional",
        melody=[{"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"}],
        title="笛子导出测试",
    )

    payload = export_traditional_score(
        result,
        instrument_type="dizi",
        export_format="jianpu",
        storage_dir=tmp_path,
        file_stem="dizi_unit",
    )

    file_path = Path(payload["file_path"])
    assert file_path.exists()
    assert payload["file_name"].endswith(".jianpu")
    assert "title=笛子导出测试" in file_path.read_text(encoding="utf-8")


def test_export_traditional_score_requires_jianpu_ly_for_lilypond(tmp_path: Path):
    result = generate_guzheng_score(
        key="G",
        tempo=96,
        time_signature="4/4",
        style="traditional",
        melody=[{"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"}],
        title="依赖检查",
    )
    original_resolver = traditional_export._resolve_jianpu_ly_command
    traditional_export._resolve_jianpu_ly_command = lambda: None

    try:
        export_traditional_score(
            result,
            instrument_type="guzheng",
            export_format="ly",
            storage_dir=tmp_path,
            file_stem="guzheng_need_dep",
        )
    except TraditionalExportDependencyError as exc:
        assert "jianpu-ly" in str(exc)
    else:
        raise AssertionError("Expected missing jianpu-ly dependency to raise TraditionalExportDependencyError")
    finally:
        traditional_export._resolve_jianpu_ly_command = original_resolver


def test_export_traditional_score_can_mock_lilypond_pipeline(tmp_path: Path, monkeypatch):
    result = generate_dizi_score(
        key="G",
        tempo=92,
        time_signature="4/4",
        flute_type="G",
        style="traditional",
        melody=[{"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"}],
        title="笛子 PDF 测试",
    )

    monkeypatch.setattr(traditional_export, "_resolve_jianpu_ly_command", lambda: "/usr/bin/jianpu-ly")
    monkeypatch.setattr(traditional_export, "_resolve_lilypond_command", lambda: "/usr/bin/lilypond")

    class _Result:
        def __init__(self, *, stdout: str = "", stderr: str = "", returncode: int = 0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(args, capture_output=False, text=False, cwd=None, check=False):
        command = Path(str(args[0])).name
        if command == "jianpu-ly":
            return _Result(stdout="\\version \"2.24.0\"\n{ c'4 }\n")
        if command == "lilypond":
            Path(cwd or ".").joinpath("compiled.pdf").write_bytes(b"%PDF-1.4\n%%fake")
            return _Result()
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(traditional_export.subprocess, "run", fake_run)

    payload = export_traditional_score(
        result,
        instrument_type="dizi",
        export_format="pdf",
        storage_dir=tmp_path,
        file_stem="dizi_pdf_mock",
    )

    assert payload["content_type"] == "application/pdf"
    assert Path(payload["file_path"]).read_bytes().startswith(b"%PDF-1.4")


def test_export_traditional_score_can_mock_svg_pipeline(tmp_path: Path, monkeypatch):
    result = generate_guzheng_score(
        key="G",
        tempo=88,
        time_signature="4/4",
        style="traditional",
        melody=[{"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"}],
        title="古筝 SVG 测试",
    )

    monkeypatch.setattr(traditional_export, "_resolve_jianpu_ly_command", lambda: "/usr/bin/jianpu-ly")
    monkeypatch.setattr(traditional_export, "_resolve_lilypond_command", lambda: "/usr/bin/lilypond")

    class _Result:
        def __init__(self, *, stdout: str = "", stderr: str = "", returncode: int = 0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(args, capture_output=False, text=False, cwd=None, check=False):
        command = Path(str(args[0])).name
        if command == "jianpu-ly":
            return _Result(stdout="\\version \"2.24.0\"\n{ c'4 }\n")
        if command == "lilypond":
            Path(cwd or ".").joinpath("compiled.svg").write_text("<svg viewBox='0 0 100 200'></svg>", encoding="utf-8")
            return _Result()
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(traditional_export.subprocess, "run", fake_run)

    payload = export_traditional_score(
        result,
        instrument_type="guzheng",
        export_format="svg",
        storage_dir=tmp_path,
        file_stem="guzheng_svg_mock",
    )

    assert payload["format"] == "svg"
    assert payload["content_type"] == "image/svg+xml"
    assert payload["preview_pages"]
    assert Path(payload["preview_pages"][0]["file_path"]).exists()


def test_export_traditional_score_writes_symbol_markup_into_guzheng_lilypond(tmp_path: Path, monkeypatch):
    result = generate_guzheng_score(
        key="G",
        tempo=88,
        time_signature="4/4",
        style="traditional",
        melody=[
            {"measure_no": 1, "start_beat": 1.0, "beats": 2.0, "pitch": "G4"},
            {"measure_no": 1, "start_beat": 3.0, "beats": 1.0, "pitch": "A4"},
        ],
        title="古筝技法符号测试",
    )

    monkeypatch.setattr(traditional_export, "_resolve_jianpu_ly_command", lambda: "/usr/bin/jianpu-ly")

    class _Result:
        def __init__(self, *, stdout: str = "", stderr: str = "", returncode: int = 0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(args, capture_output=False, text=False, cwd=None, check=False):
        command = Path(str(args[0])).name
        if command == "jianpu-ly":
            return _Result(stdout='\\version "2.24.0"\n{ c4 ^"摇" d4 ^"上滑" e4 ^"下滑" f4 ^"按" }\n')
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(traditional_export.subprocess, "run", fake_run)

    payload = export_traditional_score(
        result,
        instrument_type="guzheng",
        export_format="ly",
        storage_dir=tmp_path,
        file_stem="guzheng_symbol_markup",
    )

    content = Path(payload["file_path"]).read_text(encoding="utf-8")
    assert 'fontsize #-3 "↗"' in content
    assert 'fontsize #-3 "↘"' in content
    assert 'fontsize #-3 "∽"' in content
    assert 'fontsize #-3 \\concat { "/" "/" "/" }' in content


def test_export_guitar_lead_sheet_pdf_writes_printable_file(tmp_path: Path):
    result = {
        "title": "吉他导出测试",
        "subtitle": "Generated Lead Sheet",
        "key": "C",
        "tempo": 96,
        "time_signature": "4/4",
        "style": "folk",
        "capo_suggestion": {"capo": 2, "transposed_key": "A"},
        "strumming_pattern": {
            "display_pattern": "↓ · ↓ ↑ · ↑ ↓ ↑",
            "counting": "1 & 2 & 3 & 4 &",
            "practice_tip": "先把 1、3 拍扫稳。",
        },
        "display_sections": [
            {
                "section_title": "主歌",
                "measure_start": 1,
                "measure_end": 2,
                "display_lines": [
                    {
                        "line_label": "第 1 行",
                        "measures": [
                            {"measure_no": 1, "chords": [{"symbol": "C"}]},
                            {"measure_no": 2, "chords": [{"symbol": "G"}]},
                        ],
                    }
                ],
            }
        ],
        "chord_diagrams": [
            {"symbol": "C", "fingering": "x32010", "difficulty": "easy"},
            {"symbol": "G", "fingering": "320003", "difficulty": "easy"},
        ],
    }

    payload = export_guitar_lead_sheet_pdf(
        result,
        storage_dir=tmp_path,
        file_stem="guitar_pdf_test",
        layout_mode="print",
    )

    assert payload["content_type"] == "application/pdf"
    assert payload["file_name"].endswith(".pdf")
    assert Path(payload["file_path"]).read_bytes().startswith(b"%PDF")


def test_compact_redundant_measure_attributes_removes_repeated_visual_attributes():
    musicxml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>8</divisions>
        <key><fifths>1</fifths><mode>major</mode></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <staves>2</staves>
        <clef number="1"><sign>G</sign><line>2</line></clef>
        <clef number="2"><sign>F</sign><line>4</line></clef>
      </attributes>
      <note><rest/><duration>32</duration><voice>1</voice><type>whole</type></note>
    </measure>
    <measure number="2">
      <attributes>
        <divisions>8</divisions>
        <key><fifths>1</fifths><mode>major</mode></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <staves>2</staves>
        <clef number="1"><sign>G</sign><line>2</line></clef>
        <clef number="2"><sign>F</sign><line>4</line></clef>
      </attributes>
      <note><rest/><duration>32</duration><voice>1</voice><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""

    compacted = _compact_redundant_measure_attributes(musicxml)
    root = ET.fromstring(compacted.encode("utf-8"))
    measures = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "measure"]

    assert measures
    assert any(child.tag.rsplit("}", 1)[-1] == "attributes" for child in measures[0])
    assert not any(child.tag.rsplit("}", 1)[-1] == "attributes" for child in measures[1])


def test_build_score_from_note_events_supports_direct_event_input():
    score = build_score_from_pitch_sequence(
        [
            {"start": 0.0, "end": 0.5, "note": "A4", "frequency_avg": 440.0},
            {"start": 1.0, "end": 1.5, "note": "B4", "frequency_avg": 493.88},
        ],
        tempo=120,
    )

    assert score["musicxml"].startswith("<?xml")
    assert "<rest" in score["musicxml"]
    assert "<step>A</step>" in score["musicxml"]
    assert "<step>B</step>" in score["musicxml"]
