from __future__ import annotations

from backend.core.score.lyrics_import import align_lyrics_to_measures, import_lyrics_payload


class _FakeTags:
    def __init__(self, mapping):
        self._mapping = mapping

    def getall(self, key: str):
        return list(self._mapping.get(key, []))


class _FakeSYLT:
    def __init__(self, text, format: int = 2):
        self.text = text
        self.format = format


class _FakeUSLT:
    def __init__(self, text: str):
        self.text = text


def test_import_lyrics_payload_prefers_id3_sylt_over_lrc_and_uslt(monkeypatch):
    fake_tags = _FakeTags(
        {
            "SYLT": [_FakeSYLT([("你", 0), ("好", 500), ("世", 1000), ("界", 1500)])],
            "USLT": [_FakeUSLT("后备歌词")],
        }
    )
    monkeypatch.setattr("backend.core.score.lyrics_import._read_id3_tags", lambda _: fake_tags)

    payload = import_lyrics_payload(
        file_name="song.mp3",
        audio_bytes=b"fake-mp3",
        lyrics_file_name="song.lrc",
        lyrics_file_bytes=b"[00:00.00]fallback line",
    )

    assert payload["status"] == "imported"
    assert payload["source"] == "id3_sylt"
    assert payload["has_timestamps"] is True
    assert payload["timing_kind"] == "token"
    assert payload["line_count"] == 1
    assert payload["lines"][0]["text"] == "你好世界"


def test_import_lyrics_payload_uses_lrc_before_uslt(monkeypatch):
    fake_tags = _FakeTags({"USLT": [_FakeUSLT("内嵌普通歌词")]})
    monkeypatch.setattr("backend.core.score.lyrics_import._read_id3_tags", lambda _: fake_tags)

    payload = import_lyrics_payload(
        file_name="song.mp3",
        audio_bytes=b"fake-mp3",
        lyrics_file_name="song.lrc",
        lyrics_file_bytes="[00:00.00]第一句\n[00:02.00]第二句".encode("utf-8"),
    )

    assert payload["status"] == "imported"
    assert payload["source"] == "lrc"
    assert payload["has_timestamps"] is True
    assert payload["timing_kind"] == "line"
    assert payload["line_count"] == 2
    assert [line["text"] for line in payload["lines"]] == ["第一句", "第二句"]


def test_import_lyrics_payload_falls_back_to_uslt(monkeypatch):
    fake_tags = _FakeTags({"USLT": [_FakeUSLT("第一句\n第二句")]})
    monkeypatch.setattr("backend.core.score.lyrics_import._read_id3_tags", lambda _: fake_tags)

    payload = import_lyrics_payload(
        file_name="song.mp3",
        audio_bytes=b"fake-mp3",
    )

    assert payload["status"] == "imported"
    assert payload["source"] == "id3_uslt"
    assert payload["has_timestamps"] is False
    assert payload["timing_kind"] == "none"
    assert payload["line_count"] == 2


def test_align_lyrics_to_measures_skips_rests_and_tied_continuations():
    measures = [
        {
            "measure_no": 1,
            "right_hand_notes": [
                {"note_id": "n1", "pitch": "C4", "time": 0.0, "beats": 1.0, "start_beat": 1.0, "is_rest": False},
                {"note_id": "n2", "pitch": "Rest", "time": 0.5, "beats": 1.0, "start_beat": 2.0, "is_rest": True},
                {"note_id": "n3", "pitch": "D4", "time": 1.0, "beats": 1.0, "start_beat": 3.0, "is_rest": False, "tied_from_previous": True},
                {"note_id": "n4", "pitch": "E4", "time": 1.5, "beats": 1.0, "start_beat": 4.0, "is_rest": False},
            ],
            "left_hand_notes": [
                {"note_id": "l1", "pitch": "C3", "time": 0.0, "beats": 4.0, "start_beat": 1.0, "is_rest": False},
            ],
        }
    ]
    lyrics_payload = {
        "status": "imported",
        "source": "id3_sylt",
        "has_timestamps": True,
        "timing_kind": "token",
        "lines": [
            {
                "time": 0.0,
                "text": "你好啊",
                "tokens": [
                    {"text": "你", "time": 0.0},
                    {"text": "好", "time": 1.0},
                    {"text": "啊", "time": 1.6},
                ],
            }
        ],
        "line_count": 1,
        "warnings": [],
    }

    aligned_measures, result = align_lyrics_to_measures(
        measures,
        lyrics_payload,
        tempo=120,
        time_signature="4/4",
    )

    right_hand_notes = aligned_measures[0]["right_hand_notes"]
    assert right_hand_notes[0]["lyric"]["text"] == "你"
    assert right_hand_notes[0]["lyric"]["syllabic"] == "begin"
    assert "lyric" not in right_hand_notes[1]
    assert "lyric" not in right_hand_notes[2]
    assert right_hand_notes[3]["lyric"]["text"] == "好啊"
    assert right_hand_notes[3]["lyric"]["syllabic"] == "end"
    assert "lyric" not in aligned_measures[0]["left_hand_notes"][0]
    assert result["alignment_mode"] == "timestamped_tokens"
    assert result["note_count_with_lyrics"] == 2


def test_align_lyrics_to_measures_falls_back_to_first_note_per_measure():
    measures = [
        {
            "measure_no": 1,
            "right_hand_notes": [
                {"note_id": "n1", "pitch": "C4", "time": 0.0, "beats": 1.0, "start_beat": 1.0, "is_rest": False},
            ],
        },
        {
            "measure_no": 2,
            "right_hand_notes": [
                {"note_id": "n2", "pitch": "D4", "time": 2.0, "beats": 1.0, "start_beat": 1.0, "is_rest": False},
            ],
        },
    ]
    lyrics_payload = {
        "status": "imported",
        "source": "id3_uslt",
        "has_timestamps": False,
        "timing_kind": "none",
        "lines": [
            {"time": None, "text": "第一句", "tokens": []},
            {"time": None, "text": "第二句", "tokens": []},
            {"time": None, "text": "第三句", "tokens": []},
        ],
        "line_count": 3,
        "warnings": [],
    }

    aligned_measures, result = align_lyrics_to_measures(
        measures,
        lyrics_payload,
        tempo=120,
        time_signature="4/4",
    )

    assert aligned_measures[0]["right_hand_notes"][0]["lyric"]["text"] == "第一句"
    assert aligned_measures[1]["right_hand_notes"][0]["lyric"]["text"] == "第二句 / 第三句"
    assert result["alignment_mode"] == "measure_fallback"
    assert result["note_count_with_lyrics"] == 2
