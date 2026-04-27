"""Lyrics import and alignment helpers for piano score generation."""

from __future__ import annotations

import io
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.core.score.note_mapping import beats_per_measure, beats_to_seconds

_LRC_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def _missing_payload(*, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "missing",
        "source": "none",
        "has_timestamps": False,
        "timing_kind": "none",
        "lines": [],
        "line_count": 0,
        "warnings": list(warnings or []),
        "language": None,
    }


def _load_mutagen_id3():
    from mutagen.id3 import ID3, ID3NoHeaderError

    return ID3, ID3NoHeaderError


def _read_id3_tags(audio_bytes: bytes) -> Any | None:
    try:
        ID3, ID3NoHeaderError = _load_mutagen_id3()
    except ModuleNotFoundError:
        return None

    buffer = io.BytesIO(audio_bytes)
    try:
        try:
            return ID3(fileobj=buffer)
        except TypeError:
            buffer.seek(0)
            return ID3(buffer)
    except ID3NoHeaderError:
        return None


def _decode_text_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def _is_punctuation(char: str) -> bool:
    return bool(char) and unicodedata.category(char).startswith("P")


def _join_tokens(tokens: list[str], joiner: str) -> str:
    if not tokens:
        return ""
    if joiner:
        return joiner.join(token for token in tokens if token)
    return "".join(token for token in tokens if token)


def _guess_joiner(tokens: list[str]) -> str:
    meaningful = [token for token in tokens if token]
    if not meaningful:
        return ""
    if all(len(token) == 1 and (_CJK_RE.search(token) or _is_punctuation(token)) for token in meaningful):
        return ""
    return " "


def _tokenize_lyric_text(text: str) -> tuple[list[str], str]:
    normalized = str(text or "").strip()
    if not normalized:
        return [], ""
    if re.search(r"\s", normalized):
        tokens = [segment for segment in normalized.split() if segment]
        return tokens, " "
    if _CJK_RE.search(normalized):
        tokens: list[str] = []
        for char in normalized:
            if char.isspace():
                continue
            if _is_punctuation(char) and tokens:
                tokens[-1] += char
                continue
            if not _is_punctuation(char):
                tokens.append(char)
        return tokens, ""
    return [normalized], " "


def _build_line_payload(*, time: float | None, tokens: list[dict[str, Any]]) -> dict[str, Any]:
    token_texts = [str(token.get("text") or "").strip() for token in tokens if str(token.get("text") or "").strip()]
    joiner = _guess_joiner(token_texts)
    return {
        "time": time,
        "text": _join_tokens(token_texts, joiner),
        "tokens": [
            {
                "text": str(token.get("text") or "").strip(),
                "time": float(token["time"]) if token.get("time") is not None else None,
            }
            for token in tokens
            if str(token.get("text") or "").strip()
        ],
    }


def _sylt_timestamp_seconds(value: Any, timestamp_format: int) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp_format == 2:
        return round(numeric / 1000.0, 3)
    if timestamp_format == 1:
        return None
    if numeric >= 1000:
        return round(numeric / 1000.0, 3)
    return round(numeric, 3)


def _parse_sylt_frame(frame: Any, warnings: list[str]) -> dict[str, Any] | None:
    timestamp_format = int(getattr(frame, "format", 0) or 0)
    if timestamp_format == 1:
        warnings.append("检测到 ID3 SYLT 使用 MPEG frame 时间戳，当前版本暂不支持该格式。")
        return None

    token_entries: list[dict[str, Any]] = []
    for raw_item in list(getattr(frame, "text", []) or []):
        if not isinstance(raw_item, tuple) or len(raw_item) < 2:
            continue
        raw_text = str(raw_item[0] or "").replace("\r", "\n")
        timestamp = _sylt_timestamp_seconds(raw_item[1], timestamp_format)
        if timestamp is None:
            continue
        token_entries.append({"text": raw_text, "time": timestamp})

    if not token_entries:
        return None

    lines: list[dict[str, Any]] = []
    current_tokens: list[dict[str, Any]] = []
    current_time: float | None = None

    def flush_current_line() -> None:
        nonlocal current_tokens, current_time
        if not current_tokens:
            current_time = None
            return
        lines.append(_build_line_payload(time=current_time, tokens=current_tokens))
        current_tokens = []
        current_time = None

    for entry in token_entries:
        parts = str(entry["text"]).split("\n")
        for index, part in enumerate(parts):
            clean = part.strip()
            if clean:
                if current_time is None:
                    current_time = float(entry["time"])
                current_tokens.append({"text": clean, "time": float(entry["time"])})
            if index < len(parts) - 1:
                flush_current_line()

    flush_current_line()
    if not lines:
        return None

    return {
        "status": "imported",
        "source": "id3_sylt",
        "has_timestamps": True,
        "timing_kind": "token",
        "lines": lines,
        "line_count": len(lines),
        "warnings": warnings,
    }


def _parse_uslt_frames(frames: list[Any], warnings: list[str]) -> dict[str, Any] | None:
    for frame in frames:
        raw_text = getattr(frame, "text", "")
        if isinstance(raw_text, list):
            raw_text = "\n".join(str(item) for item in raw_text)
        text = str(raw_text or "").strip()
        if not text:
            continue
        lines = [
            {"time": None, "text": stripped, "tokens": []}
            for stripped in (line.strip() for line in text.replace("\r", "\n").split("\n"))
            if stripped
        ]
        if lines:
            return {
                "status": "imported",
                "source": "id3_uslt",
                "has_timestamps": False,
                "timing_kind": "none",
                "lines": lines,
                "line_count": len(lines),
                "warnings": warnings,
            }
    return None


def _parse_lrc_text(text: str, warnings: list[str]) -> dict[str, Any] | None:
    timed_lines: list[dict[str, Any]] = []
    plain_lines: list[str] = []

    for raw_line in text.replace("\r", "\n").split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue

        matches = list(_LRC_TIMESTAMP_RE.finditer(stripped))
        if matches:
            lyric_text = _LRC_TIMESTAMP_RE.sub("", stripped).strip()
            if not lyric_text:
                continue
            for match in matches:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                fraction = match.group(3) or ""
                fraction_value = 0.0
                if fraction:
                    scale = 10 ** len(fraction)
                    fraction_value = int(fraction) / scale
                timestamp = round(minutes * 60 + seconds + fraction_value, 3)
                timed_lines.append({"time": timestamp, "text": lyric_text, "tokens": []})
            continue

        if stripped.startswith("[") and "]" in stripped:
            continue
        plain_lines.append(stripped)

    if timed_lines:
        timed_lines.sort(key=lambda item: float(item.get("time") or 0.0))
        return {
            "status": "imported",
            "source": "lrc",
            "has_timestamps": True,
            "timing_kind": "line",
            "lines": timed_lines,
            "line_count": len(timed_lines),
            "warnings": warnings,
        }

    if plain_lines:
        return {
            "status": "imported",
            "source": "lrc",
            "has_timestamps": False,
            "timing_kind": "none",
            "lines": [{"time": None, "text": line, "tokens": []} for line in plain_lines],
            "line_count": len(plain_lines),
            "warnings": warnings,
        }

    return None


def import_lyrics_payload(
    *,
    file_name: str,
    audio_bytes: bytes,
    lyrics_file_name: str | None = None,
    lyrics_file_bytes: bytes | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    suffix = Path(file_name or "").suffix.lower()
    tags = _read_id3_tags(audio_bytes) if suffix == ".mp3" else None

    if suffix == ".mp3" and tags is None:
        try:
            _load_mutagen_id3()
        except ModuleNotFoundError:
            warnings.append("当前环境未安装 mutagen，已跳过 MP3 内嵌歌词读取。")

    if tags is not None:
        sylt_payload = _parse_sylt_frame(next(iter(tags.getall("SYLT") or []), None), warnings) if tags.getall("SYLT") else None
        if sylt_payload is not None:
            return sylt_payload

    if lyrics_file_bytes is not None:
        if lyrics_file_bytes.strip():
            lrc_payload = _parse_lrc_text(_decode_text_bytes(lyrics_file_bytes), warnings)
            if lrc_payload is not None:
                return lrc_payload
            warnings.append(f"未能从歌词文件 {lyrics_file_name or 'lyrics_file'} 解析出可用内容。")
        else:
            warnings.append(f"歌词文件 {lyrics_file_name or 'lyrics_file'} 为空，已忽略。")

    if tags is not None:
        uslt_payload = _parse_uslt_frames(list(tags.getall("USLT") or []), warnings)
        if uslt_payload is not None:
            return uslt_payload

    return _missing_payload(warnings=warnings)


def _derive_note_time(
    *,
    measure_no: int,
    start_beat: float,
    tempo: int,
    time_signature: str,
) -> float:
    total_beats = beats_per_measure(time_signature)
    absolute_beats = (max(int(measure_no), 1) - 1) * total_beats + max(float(start_beat) - 1.0, 0.0)
    return round(beats_to_seconds(absolute_beats, tempo), 3)


def _clear_note_lyrics(measures: list[dict[str, Any]]) -> None:
    for measure in measures:
        for note_list_key in ("notes", "right_hand_notes", "left_hand_notes"):
            for note in list(measure.get(note_list_key) or []):
                note.pop("lyric", None)


def _candidate_lyric_notes(
    measures: list[dict[str, Any]],
    *,
    tempo: int,
    time_signature: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    measure_groups: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for measure_index, measure in enumerate(measures, start=1):
        measure_no = int(measure.get("measure_no") or measure_index)
        if measure.get("right_hand_notes") or measure.get("left_hand_notes"):
            note_list = list(measure.get("right_hand_notes") or [])
        else:
            note_list = list(measure.get("notes") or [])

        group_notes: list[dict[str, Any]] = []
        for note in note_list:
            if bool(note.get("is_rest")) or str(note.get("pitch") or "Rest") == "Rest":
                continue
            if bool(note.get("tied_from_previous")):
                continue
            note_time = float(
                note.get("time")
                if note.get("time") is not None
                else _derive_note_time(
                    measure_no=measure_no,
                    start_beat=float(note.get("start_beat") or 1.0),
                    tempo=tempo,
                    time_signature=time_signature,
                )
            )
            candidate = {
                "measure_no": measure_no,
                "time": round(note_time, 3),
                "note": note,
            }
            group_notes.append(candidate)
            candidates.append(candidate)

        if group_notes:
            measure_groups.append({"measure_no": measure_no, "notes": group_notes})

    return candidates, measure_groups


def _apply_note_lyric(note: dict[str, Any], text: str, syllabic: str) -> None:
    clean = str(text or "").strip()
    if not clean:
        return
    note["lyric"] = {"text": clean, "syllabic": syllabic}


def _assign_tokens_to_notes(tokens: list[str], note_refs: list[dict[str, Any]], *, joiner: str) -> int:
    if not tokens or not note_refs:
        return 0

    note_texts: list[str] = []
    note_count = min(len(tokens), len(note_refs))
    for index in range(note_count):
        token_slice = [tokens[index]] if index < note_count - 1 else tokens[index:]
        note_texts.append(_join_tokens(token_slice, joiner))

    if len(note_texts) == 1:
        _apply_note_lyric(note_refs[0]["note"], note_texts[0], "single")
        return 1

    for index, text in enumerate(note_texts):
        if index == 0:
            syllabic = "begin"
        elif index == len(note_texts) - 1:
            syllabic = "end"
        else:
            syllabic = "middle"
        _apply_note_lyric(note_refs[index]["note"], text, syllabic)
    return len(note_texts)


def _find_nearest_note_index(candidates: list[dict[str, Any]], start_index: int, target_time: float) -> int | None:
    if start_index >= len(candidates):
        return None

    best_index = start_index
    best_distance = abs(float(candidates[start_index]["time"]) - target_time)
    for index in range(start_index + 1, len(candidates)):
        distance = abs(float(candidates[index]["time"]) - target_time)
        if distance <= best_distance + 1e-9:
            best_index = index
            best_distance = distance
            continue
        if float(candidates[index]["time"]) > target_time:
            break
    return best_index


def _append_line_to_existing_note(note: dict[str, Any], text: str) -> None:
    clean = str(text or "").strip()
    if not clean:
        return
    existing = note.get("lyric")
    if not isinstance(existing, dict) or not str(existing.get("text") or "").strip():
        note["lyric"] = {"text": clean, "syllabic": "single"}
        return
    existing_text = str(existing.get("text") or "").strip()
    existing["text"] = f"{existing_text} / {clean}"
    existing["syllabic"] = "single"


def align_lyrics_to_measures(
    measures: list[dict[str, Any]],
    lyrics_payload: dict[str, Any] | None,
    *,
    tempo: int,
    time_signature: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_payload = deepcopy(lyrics_payload or _missing_payload())
    aligned_measures = deepcopy(measures or [])
    _clear_note_lyrics(aligned_measures)

    base_result = {
        "status": str(normalized_payload.get("status") or "missing"),
        "source": str(normalized_payload.get("source") or "none"),
        "has_timestamps": bool(normalized_payload.get("has_timestamps", False)),
        "alignment_mode": "none",
        "line_count": int(normalized_payload.get("line_count") or len(normalized_payload.get("lines") or [])),
        "note_count_with_lyrics": 0,
        "warnings": list(normalized_payload.get("warnings") or []),
        "language": normalized_payload.get("language"),
    }

    if base_result["status"] != "imported":
        return aligned_measures, base_result

    candidates, measure_groups = _candidate_lyric_notes(
        aligned_measures,
        tempo=tempo,
        time_signature=time_signature,
    )
    if not candidates:
        base_result["warnings"].append("当前乐谱未找到可挂歌词的右手旋律音符。")
        return aligned_measures, base_result

    lines = [line for line in list(normalized_payload.get("lines") or []) if str(line.get("text") or "").strip()]
    if not lines:
        base_result["status"] = "missing"
        base_result["source"] = "none"
        return aligned_measures, base_result

    timing_kind = str(normalized_payload.get("timing_kind") or "none")

    if timing_kind == "token":
        base_result["alignment_mode"] = "timestamped_tokens"
        cursor = 0
        assigned_notes = 0
        for line in lines:
            line_tokens = [dict(token) for token in list(line.get("tokens") or []) if str(token.get("text") or "").strip()]
            if not line_tokens:
                continue
            assigned_refs: list[dict[str, Any]] = []
            overflow_tokens: list[str] = []
            joiner = _guess_joiner([str(token.get("text") or "").strip() for token in line_tokens])
            for token in line_tokens:
                token_text = str(token.get("text") or "").strip()
                token_time = token.get("time")
                if not token_text:
                    continue
                if token_time is None:
                    overflow_tokens.append(token_text)
                    continue
                candidate_index = _find_nearest_note_index(candidates, cursor, float(token_time))
                if candidate_index is None:
                    overflow_tokens.append(token_text)
                    continue
                assigned_refs.append(candidates[candidate_index])
                cursor = candidate_index + 1
            if not assigned_refs:
                continue
            if overflow_tokens:
                line_tokens = [
                    str(token.get("text") or "").strip()
                    for token in line_tokens
                    if str(token.get("text") or "").strip()
                ]
                assigned_notes += _assign_tokens_to_notes(line_tokens, assigned_refs, joiner=joiner)
                continue
            assigned_notes += _assign_tokens_to_notes(
                [str(token.get("text") or "").strip() for token in line_tokens],
                assigned_refs,
                joiner=joiner,
            )
        base_result["note_count_with_lyrics"] = assigned_notes
        return aligned_measures, base_result

    if timing_kind == "line":
        base_result["alignment_mode"] = "timestamped_lines"
        assigned_notes = 0
        cursor = 0
        for index, line in enumerate(lines):
            line_text = str(line.get("text") or "").strip()
            if not line_text:
                continue
            start_time = float(line.get("time") or 0.0)
            next_time = None
            for following in lines[index + 1 :]:
                if following.get("time") is not None:
                    next_time = float(following["time"])
                    break

            eligible_refs: list[dict[str, Any]] = []
            last_index_in_slice: int | None = None
            for candidate_index in range(cursor, len(candidates)):
                note_time = float(candidates[candidate_index]["time"])
                if note_time + 1e-6 < start_time:
                    continue
                if next_time is not None and note_time >= next_time - 1e-6:
                    break
                eligible_refs.append(candidates[candidate_index])
                last_index_in_slice = candidate_index

            if not eligible_refs and cursor < len(candidates):
                eligible_refs = [candidates[cursor]]
                last_index_in_slice = cursor

            if not eligible_refs:
                continue

            tokens, joiner = _tokenize_lyric_text(line_text)
            if not tokens:
                continue
            assigned_notes += _assign_tokens_to_notes(tokens, eligible_refs, joiner=joiner)
            cursor = (last_index_in_slice + 1) if last_index_in_slice is not None else cursor

        base_result["note_count_with_lyrics"] = assigned_notes
        return aligned_measures, base_result

    base_result["alignment_mode"] = "measure_fallback"
    assigned_notes = 0
    if not measure_groups:
        base_result["warnings"].append("当前乐谱未找到可挂歌词的小节旋律。")
        return aligned_measures, base_result

    for index, line in enumerate(lines):
        line_text = str(line.get("text") or "").strip()
        if not line_text:
            continue
        target_group = measure_groups[min(index, len(measure_groups) - 1)]
        target_note = target_group["notes"][0]["note"]
        if index >= len(measure_groups):
            _append_line_to_existing_note(target_note, line_text)
            continue
        _apply_note_lyric(target_note, line_text, "single")
        assigned_notes += 1

    base_result["note_count_with_lyrics"] = assigned_notes
    return aligned_measures, base_result
