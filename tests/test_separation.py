"""Tests for multi-track audio separation functionality."""

from __future__ import annotations

import tempfile
import io
import ssl
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf
import pytest

from backend.core.separation.multi_track_separation import (
    AudioSeparator,
    separate_tracks,
    get_separator,
    STEM_NAMES,
)


@pytest.fixture
def temp_audio_bytes():
    """Generate temporary audio bytes for testing."""
    sr = 44100
    duration = 3  # 3 seconds
    t = np.linspace(0, duration, sr * duration)
    # Generate a simple sine wave
    y = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    # Convert to WAV bytes
    import io
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format='WAV')
    return buffer.getvalue()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestAudioSeparator:
    """Test cases for AudioSeparator class."""

    def test_separator_initialization(self, temp_dir):
        """Test AudioSeparator initialization."""
        separator = AudioSeparator(temp_dir)
        assert separator.output_dir == temp_dir
        assert separator.separator_id is not None

    def test_separator_singleton_pattern(self):
        """Test that get_separator returns same instance."""
        sep1 = get_separator()
        sep2 = get_separator()
        assert sep1 is sep2

    def test_load_audio_with_valid_bytes(self, temp_audio_bytes):
        """Test loading audio from bytes."""
        separator = AudioSeparator()
        y, sr = separator._load_audio(temp_audio_bytes, sr=44100)
        
        assert isinstance(y, np.ndarray)
        assert sr == 44100
        assert y.shape[0] > 0

    def test_separate_two_stems(self, temp_audio_bytes, temp_dir):
        """Test basic 2-stem separation."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )
        
        assert result["task_id"].startswith("sep_")
        assert result["status"] == "completed"
        assert result["model"] == "demucs"
        assert "backend_used" in result
        assert "fallback_used" in result
        assert "warnings" in result
        assert result["stems"] == 2
        assert len(result["tracks"]) == 2
        
        # Check track metadata
        for track in result["tracks"]:
            assert "name" in track
            assert "file_name" in track
            assert "download_url" in track
            assert "duration" in track
            assert track["name"] in STEM_NAMES[2]

    def test_separate_four_stems(self, temp_audio_bytes, temp_dir):
        """Test 4-stem separation."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=4,
            audio_bytes=temp_audio_bytes,
        )
        
        assert len(result["tracks"]) == 4
        assert result["stems"] == 4
        
        stem_names = [t["name"] for t in result["tracks"]]
        assert "vocal" in stem_names
        assert "drums" in stem_names
        assert "bass" in stem_names

    def test_separate_six_stems(self, temp_audio_bytes, temp_dir):
        """Test 6-stem separation."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=6,
            audio_bytes=temp_audio_bytes,
        )
        
        assert len(result["tracks"]) == 6
        stem_names = [t["name"] for t in result["tracks"]]
        assert "vocal" in stem_names
        assert "guitar" in stem_names
        assert "piano" in stem_names

    def test_separate_invalid_stems(self, temp_audio_bytes, temp_dir):
        """Test separation with invalid stem count."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=7,  # Invalid
            audio_bytes=temp_audio_bytes,
        )
        
        # Should default to max valid stems (6)
        assert result["stems"] == 6

    def test_separate_with_empty_audio_bytes(self, temp_dir):
        """Test separation with empty audio bytes."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=b"",
        )
        
        assert result["status"] == "failed"
        assert "error" in result

    def test_separation_preserves_duration(self, temp_audio_bytes, temp_dir):
        """Test that separated tracks have correct duration."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )
        
        # All tracks should have similar duration
        durations = [t["duration"] for t in result["tracks"]]
        assert len(set(f"{d:.1f}" for d in durations)) == 1  # All same (within 0.1s)

    def test_separation_creates_files(self, temp_audio_bytes, temp_dir):
        """Test that separated tracks are saved to disk."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )
        
        for track in result["tracks"]:
            file_path = Path(track["file_path"])
            assert file_path.exists()
            assert file_path.stat().st_size > 0
            assert file_path.suffix == ".wav"

    def test_get_separation_status(self, temp_dir):
        """Test getting separation task status."""
        separator = AudioSeparator(temp_dir)
        status = separator.get_separation_status("sep_test_123")
        
        assert status["task_id"] == "sep_test_123"
        assert status["status"] == "completed"
        assert "message" in status


class TestSeparateTracksFunction:
    """Test cases for the public separate_tracks function."""

    def test_separate_tracks_basic(self, temp_audio_bytes):
        """Test basic separate_tracks function."""
        result = separate_tracks(
            file_name="song.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )
        
        assert result["task_id"].startswith("sep_")
        assert result["status"] == "completed"
        assert len(result["tracks"]) == 2

    def test_separate_tracks_with_custom_sample_rate(self, temp_audio_bytes):
        """Test separate_tracks with custom sample rate."""
        result = separate_tracks(
            file_name="song.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
            sample_rate=48000,
        )
        
        assert result["sample_rate"] == 48000

    def test_separate_tracks_all_stem_counts(self, temp_audio_bytes):
        """Test separate_tracks with different stem counts."""
        for stems in [2, 4, 5, 6]:
            result = separate_tracks(
                file_name="song.wav",
                stems=stems,
                audio_bytes=temp_audio_bytes,
            )
            
            assert result["stems"] == stems
            assert len(result["tracks"]) == stems

    def test_separate_tracks_track_names_are_valid(self, temp_audio_bytes):
        """Test that all returned track names are valid."""
        result = separate_tracks(
            file_name="song.wav",
            stems=4,
            audio_bytes=temp_audio_bytes,
        )
        
        valid_names = {"vocal", "drums", "bass", "guitar", "piano", "accompaniment", "other"}
        for track in result["tracks"]:
            assert track["name"] in valid_names

    def test_separate_tracks_track_download_urls(self, temp_audio_bytes):
        """Test that download URLs are properly formatted."""
        result = separate_tracks(
            file_name="song.wav",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )
        
        for track in result["tracks"]:
            assert track["download_url"].startswith("/api/v1/audio/download/")
            assert track["download_url"].endswith(".wav")

    def test_separate_tracks_includes_metadata(self, temp_audio_bytes):
        """Test that result includes complete metadata."""
        result = separate_tracks(
            file_name="song.wav",
            model="demucs",
            stems=4,
            audio_bytes=temp_audio_bytes,
            sample_rate=44100,
        )
        
        assert result["source_file"] == "song.wav"
        assert result["model"] == "demucs"
        assert result["sample_rate"] == 44100
        assert "backend_used" in result
        assert "fallback_used" in result
        assert "warnings" in result
        assert "task_id" in result
        assert "status" in result


class TestAudioProcessing:
    """Test cases for audio processing details."""

    def test_simple_separation_two_stems(self, temp_audio_bytes):
        """Test _simple_separation method with 2 stems."""
        separator = AudioSeparator()
        y, sr = separator._load_audio(temp_audio_bytes)
        separated = separator._simple_separation(y, sr, stems=2)
        
        assert len(separated) <= 2
        for name, audio in separated.items():
            assert isinstance(audio, np.ndarray)
            assert audio.shape[0] > 0

    def test_simple_separation_four_stems(self, temp_audio_bytes):
        """Test _simple_separation method with 4 stems."""
        separator = AudioSeparator()
        y, sr = separator._load_audio(temp_audio_bytes)
        separated = separator._simple_separation(y, sr, stems=4)
        
        assert len(separated) <= 4
        assert any(name in separated for name in ["vocal", "drums"])

    def test_audio_normalization(self, temp_dir):
        """Test that audio normalization prevents clipping."""
        separator = AudioSeparator(temp_dir)
        
        # Create audio with values > 1.0
        loud_audio = np.ones(44100) * 2.0
        sr = 44100
        
        file_path = separator._save_track(loud_audio, sr, "test_id", "test", "orig.wav")
        
        # Load saved file and check it's normalized
        loaded, _ = librosa.load(file_path, sr=sr)
        assert np.max(np.abs(loaded)) <= 0.95

    def test_audio_normalization_happens_before_save(self, temp_audio_bytes, temp_dir, monkeypatch):
        """Test that separate() normalizes stems before calling _save_track."""
        separator = AudioSeparator(temp_dir)
        captured_peaks = {}

        def fake_simple_separation(y, sr, stems):
            return {
                "vocal": np.ones(2048, dtype=np.float32) * 2.0,
                "accompaniment": np.ones(2048, dtype=np.float32) * 1.4,
            }

        def fake_save_track(audio_data, sr, task_id, track_name, source_file):
            captured_peaks[track_name] = float(np.max(np.abs(audio_data)))
            return str(Path(temp_dir) / f"{task_id}_{track_name}.wav")

        monkeypatch.setattr(separator, "_simple_separation", fake_simple_separation)
        monkeypatch.setattr(separator, "_save_track", fake_save_track)

        result = separator.separate(
            file_name="test.wav",
            model="unknown_model",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )

        assert result["status"] == "completed"
        assert captured_peaks
        assert all(peak <= 0.95 for peak in captured_peaks.values())

    def test_separate_uses_demucs_backend_when_available(self, temp_audio_bytes, temp_dir, monkeypatch):
        """Test that successful Demucs execution is surfaced as the active backend."""
        separator = AudioSeparator(temp_dir)

        def fake_demucs(y, sr, stems):
            return {
                "vocal": np.ones(1024, dtype=np.float32) * 0.2,
                "accompaniment": np.ones(1024, dtype=np.float32) * 0.1,
            }

        def fail_simple(y, sr, stems):
            raise AssertionError("simple fallback should not run")

        monkeypatch.setattr(separator, "_run_demucs_separation", fake_demucs)
        monkeypatch.setattr(separator, "_simple_separation", fail_simple)

        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )

        assert result["status"] == "completed"
        assert result["backend_used"] == "demucs"
        assert result["fallback_used"] is False
        assert result["warnings"] == []
        assert len(result["tracks"]) == 2

    def test_separate_records_demucs_fallback(self, temp_audio_bytes, temp_dir, monkeypatch):
        """Test that Demucs failures are exposed instead of being silently masked."""
        separator = AudioSeparator(temp_dir)

        def fail_demucs(y, sr, stems):
            raise RuntimeError("mock demucs failure")

        def fake_simple(y, sr, stems):
            return {
                "vocal": np.ones(1024, dtype=np.float32) * 0.2,
                "accompaniment": np.ones(1024, dtype=np.float32) * 0.1,
            }

        monkeypatch.setattr(separator, "_run_demucs_separation", fail_demucs)
        monkeypatch.setattr(separator, "_simple_separation", fake_simple)

        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )

        assert result["status"] == "completed"
        assert result["backend_used"] == "simple"
        assert result["fallback_used"] is True
        assert result["warnings"]
        assert "mock demucs failure" in result["warnings"][0]

    def test_separate_normalizes_demucs_ssl_warning(self, temp_audio_bytes, temp_dir, monkeypatch):
        """Test that SSL certificate failures are surfaced as a readable fallback warning."""
        separator = AudioSeparator(temp_dir)

        def fail_demucs(y, sr, stems):
            raise ssl.SSLCertVerificationError(
                "certificate verify failed: unable to get local issuer certificate"
            )

        def fake_simple(y, sr, stems):
            return {
                "vocal": np.ones(1024, dtype=np.float32) * 0.2,
                "accompaniment": np.ones(1024, dtype=np.float32) * 0.1,
            }

        monkeypatch.setattr(separator, "_run_demucs_separation", fail_demucs)
        monkeypatch.setattr(separator, "_simple_separation", fake_simple)

        result = separator.separate(
            file_name="test.wav",
            model="demucs",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )

        assert result["status"] == "completed"
        assert result["backend_used"] == "simple"
        assert result["fallback_used"] is True
        assert result["warnings"]
        assert "SSL 证书校验失败" in result["warnings"][0]
        assert "内置简易分离" in result["warnings"][0]

    def test_save_track_accepts_channel_first_stereo(self, temp_dir):
        """Test that channel-first stereo arrays are transposed before saving."""
        separator = AudioSeparator(temp_dir)
        sr = 44100
        t = np.linspace(0, 1, sr, endpoint=False)
        stereo = np.stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 660 * t)])

        file_path = separator._save_track(stereo, sr, "test_id", "stereo", "orig.wav")

        loaded, loaded_sr = librosa.load(file_path, sr=sr, mono=False)
        assert loaded_sr == sr
        assert loaded.ndim == 2
        assert loaded.shape[0] == 2
        assert loaded.shape[1] == sr

    def test_audio_mono_conversion(self, temp_audio_bytes):
        """Test that stereo audio is converted to mono."""
        separator = AudioSeparator()
        
        # Create stereo audio
        sr = 44100
        t = np.linspace(0, 1, sr)
        stereo = np.stack([np.sin(2*np.pi*440*t), np.sin(2*np.pi*880*t)])
        
        import io
        buffer = io.BytesIO()
        sf.write(buffer, stereo.T, sr, format='WAV')
        stereo_bytes = buffer.getvalue()
        
        y, loaded_sr = separator._load_audio(stereo_bytes, sr=sr)
        assert loaded_sr == sr

    def test_vocal_enhancement_focuses_center_harmonic_band(self, temp_dir):
        """Test that vocal enhancement suppresses bass/percussive leakage and keeps melody energy."""
        separator = AudioSeparator(temp_dir)
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        vocal = 0.28 * np.sin(2 * np.pi * 440 * t)
        bass = 0.32 * np.sin(2 * np.pi * 55 * t)
        side = 0.18 * np.sin(2 * np.pi * 700 * t)
        clicks = np.zeros_like(t)
        clicks[::800] = 0.65
        stereo = np.stack([vocal + bass + side + clicks, vocal + bass - side + clicks], axis=0).astype(np.float32)

        centered = np.mean(stereo, axis=0)
        enhanced = separator._enhance_vocal_track(stereo, original_mix=stereo, sr=sr)

        def band_energy(signal: np.ndarray, low_hz: float, high_hz: float) -> float:
            spectrum = np.abs(np.fft.rfft(np.asarray(signal, dtype=np.float32)))
            freqs = np.fft.rfftfreq(len(signal), d=1.0 / sr)
            mask = (freqs >= low_hz) & (freqs < high_hz)
            return float(np.sum(spectrum[mask]))

        assert band_energy(enhanced, 35, 75) < band_energy(centered, 35, 75) * 0.6
        assert band_energy(enhanced, 3000, 6000) < band_energy(centered, 3000, 6000) * 0.3
        assert band_energy(enhanced, 380, 520) > band_energy(enhanced, 35, 75)

    def test_separate_tracks_includes_vocal_enhancement_metadata(self, temp_dir):
        """Test that vocal extraction metadata is surfaced for debugging."""
        separator = AudioSeparator(temp_dir)
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        vocal = 0.25 * np.sin(2 * np.pi * 440 * t)
        bass = 0.15 * np.sin(2 * np.pi * 65 * t)
        stereo = np.stack([vocal + bass, vocal + bass], axis=1).astype(np.float32)

        buffer = io.BytesIO()
        sf.write(buffer, stereo, sr, format="WAV")
        result = separator.separate(
            file_name="stereo.wav",
            model="unknown_model",
            stems=2,
            audio_bytes=buffer.getvalue(),
            sample_rate=sr,
        )

        vocal_track = next(track for track in result["tracks"] if track["name"] == "vocal")
        assert result["status"] == "completed"
        assert result["vocal_enhancement"]["band_pass_hz"] == [80, 2000]
        assert result["vocal_enhancement"]["hpss_harmonic_used"] is True
        assert vocal_track["enhancement"]["low_frequency_attenuation_below_hz"] == 150

    def test_demucs_cache_dir_honors_env_override(self, temp_dir, monkeypatch):
        """Test that DEMUCS_CACHE_DIR overrides the default cache path."""
        cache_dir = Path(temp_dir) / "custom-cache"
        monkeypatch.setenv("DEMUCS_CACHE_DIR", str(cache_dir))

        separator = AudioSeparator(temp_dir)
        resolved = separator._demucs_cache_dir()

        assert resolved == cache_dir
        assert resolved.exists()

    def test_resolve_local_demucs_repo_autocopies_yaml(self, temp_dir, monkeypatch):
        """Test that a local offline repo is made valid with the bundled YAML."""
        repo_dir = Path(temp_dir) / "demucs-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "955717e8-8726e21a.th").write_bytes(b"fake checkpoint")
        monkeypatch.setenv("DEMUCS_REPO_DIR", str(repo_dir))

        from demucs import pretrained

        separator = AudioSeparator(temp_dir)
        resolved = separator._resolve_local_demucs_repo("htdemucs")

        assert resolved == repo_dir
        assert (repo_dir / "htdemucs.yaml").exists()
        assert (repo_dir / "htdemucs.yaml").read_text() == (
            Path(pretrained.REMOTE_ROOT) / "htdemucs.yaml"
        ).read_text()

    def test_resolve_local_demucs_repo_requires_weights(self, temp_dir, monkeypatch):
        """Test that an empty local repo is ignored."""
        repo_dir = Path(temp_dir) / "demucs-repo"
        repo_dir.mkdir(parents=True)
        monkeypatch.setenv("DEMUCS_REPO_DIR", str(repo_dir))

        separator = AudioSeparator(temp_dir)

        assert separator._resolve_local_demucs_repo("htdemucs") is None


class TestErrorHandling:
    """Test cases for error handling."""

    def test_separation_with_corrupted_audio(self, temp_dir):
        """Test handling of corrupted audio data."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="corrupted.wav",
            stems=2,
            audio_bytes=b"not valid audio data",
        )
        
        assert result["status"] == "failed"
        assert "error" in result

    def test_invalid_model_parameter(self, temp_audio_bytes, temp_dir):
        """Test handling of invalid model parameter."""
        separator = AudioSeparator(temp_dir)
        result = separator.separate(
            file_name="test.wav",
            model="unknown_model",
            stems=2,
            audio_bytes=temp_audio_bytes,
        )
        
        # Should fallback to simple separation without error
        assert result["status"] == "completed"
        assert result["model"] == "unknown_model"


class TestStemConstants:
    """Test cases for stem configuration constants."""

    def test_stem_names_coverage(self):
        """Test that STEM_NAMES covers required stem counts."""
        assert 2 in STEM_NAMES
        assert 4 in STEM_NAMES
        assert 5 in STEM_NAMES
        assert 6 in STEM_NAMES

    def test_stem_names_correctness(self):
        """Test that STEM_NAMES has correct values."""
        assert STEM_NAMES[2] == ["vocal", "accompaniment"]
        assert "vocal" in STEM_NAMES[4]
        assert "drums" in STEM_NAMES[4]
        assert "bass" in STEM_NAMES[4]

    def test_all_stem_lengths_match_keys(self):
        """Test that all STEM_NAMES values have correct length."""
        for stems, names in STEM_NAMES.items():
            assert len(names) == stems
