from __future__ import annotations

from pathlib import Path

from backend.core.score.whisperx_lyrics import (
    normalize_whisperx_result_to_lyrics_payload,
    select_whisperx_audio_source,
    transcribe_audio_with_whisperx,
)


def test_select_whisperx_audio_source_prefers_vocal_track(tmp_path: Path):
    vocal_path = tmp_path / "vocal.wav"
    vocal_path.write_bytes(b"vocal-bytes")
    other_path = tmp_path / "other.wav"
    other_path.write_bytes(b"other-bytes")

    selected = select_whisperx_audio_source(
        file_name="song.mp3",
        audio_bytes=b"mix-bytes",
        separation_result={
            "tracks": [
                {"name": "other", "file_name": "other.wav", "file_path": str(other_path)},
                {"name": "vocal", "file_name": "vocal.wav", "file_path": str(vocal_path)},
            ]
        },
        melody_track={"name": "other", "file_name": "other.wav"},
    )

    assert selected["source"] == "vocal_track"
    assert selected["audio_bytes"] == b"vocal-bytes"
    assert selected["track_name"] == "vocal"


def test_select_whisperx_audio_source_falls_back_to_selected_melody_track(tmp_path: Path):
    piano_path = tmp_path / "piano.wav"
    piano_path.write_bytes(b"piano-bytes")

    selected = select_whisperx_audio_source(
        file_name="song.mp3",
        audio_bytes=b"mix-bytes",
        separation_result={"tracks": [{"name": "piano", "file_name": "piano.wav", "file_path": str(piano_path)}]},
        melody_track={"name": "piano", "file_name": "piano.wav"},
    )

    assert selected["source"] == "melody_track"
    assert selected["audio_bytes"] == b"piano-bytes"


def test_normalize_whisperx_result_to_lyrics_payload_prefers_timed_tokens_for_chinese():
    payload = normalize_whisperx_result_to_lyrics_payload(
        {
            "language": "zh",
            "segments": [
                {
                    "start": 0.0,
                    "text": "你好世界",
                    "words": [
                        {"word": "你", "start": 0.0},
                        {"word": "好", "start": 0.5},
                        {"word": "世", "start": 1.0},
                        {"word": "界", "start": 1.5},
                    ],
                }
            ],
        }
    )

    assert payload["status"] == "imported"
    assert payload["source"] == "whisperx_asr"
    assert payload["timing_kind"] == "token"
    assert payload["language"] == "zh"
    assert payload["lines"][0]["tokens"][2] == {"text": "世", "time": 1.0}


def test_normalize_whisperx_result_to_lyrics_payload_falls_back_to_timed_lines():
    payload = normalize_whisperx_result_to_lyrics_payload(
        {
            "language": "en",
            "segments": [
                {"start": 0.0, "text": "hello world", "words": []},
                {"start": 2.0, "text": "stay with me", "words": []},
            ],
        },
        warnings=["alignment fallback"],
    )

    assert payload["status"] == "imported"
    assert payload["timing_kind"] == "line"
    assert payload["has_timestamps"] is True
    assert payload["warnings"] == ["alignment fallback"]
    assert [line["text"] for line in payload["lines"]] == ["hello world", "stay with me"]


def test_transcribe_audio_with_whisperx_retries_for_cjk_context(monkeypatch, tmp_path: Path):
    temp_audio = tmp_path / "song.wav"
    temp_audio.write_bytes(b"demo")
    calls: list[str | None] = []

    class _FakeModel:
        def transcribe(self, audio, batch_size: int = 1, language: str | None = None):
            del audio, batch_size
            calls.append(language)
            if language == "zh":
                return {"language": "zh", "segments": [{"text": "你好世界"}]}
            return {"language": "en", "segments": [{"text": "hello world"}]}

    class _FakeWhisperX:
        @staticmethod
        def load_audio(path: str):
            assert path == str(temp_audio)
            return "audio"

        @staticmethod
        def load_model(model_size: str, device: str, compute_type: str = "int8"):
            assert model_size
            assert device
            assert compute_type
            return _FakeModel()

    monkeypatch.setattr("backend.core.score.whisperx_lyrics._load_whisperx", lambda: _FakeWhisperX)
    monkeypatch.setattr(
        "backend.core.score.whisperx_lyrics._write_temp_audio_file",
        lambda audio_bytes, file_name: str(temp_audio),
    )

    result = transcribe_audio_with_whisperx(
        audio_bytes=b"audio",
        file_name="童年.mp3",
    )

    assert calls == [None, "zh"]
    assert result["transcription"]["language"] == "zh"
    assert result["retry_language_used"] == "zh"
    assert result["warnings"]
