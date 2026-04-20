"""Multi-track separation using advanced audio source separation models."""

from __future__ import annotations

import os
import io
import logging
import ssl
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.numba_compat import ensure_numba_cache_dir

ensure_numba_cache_dir()

import librosa
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Track names for different stem configurations
STEM_NAMES = {
    2: ["vocal", "accompaniment"],
    4: ["vocal", "drums", "bass", "other"],
    5: ["vocal", "drums", "bass", "other", "piano"],
    6: ["vocal", "drums", "bass", "guitar", "piano", "other"],
}

# Default stem order preference
DEFAULT_STEMS_ORDER = ["vocal", "drums", "bass", "guitar", "piano", "accompaniment", "other"]
VOCAL_BAND_LOW_HZ = 80.0
VOCAL_BAND_HIGH_HZ = 2000.0
VOCAL_LOW_ATTENUATION_HZ = 150.0
VOCAL_LOW_ATTENUATION_GAIN = 0.35
VOCAL_CENTER_BLEND = 0.25
VOCAL_HPSS_MARGIN = (1.0, 5.0)


def _is_certificate_verification_failure(exc: Exception) -> bool:
    """Return True when the exception chain points to an SSL cert failure."""
    current: Exception | None = exc
    seen: set[int] = set()
    while current and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        message = str(current)
        if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
            return True
        current = current.__cause__ or current.__context__
    return False


def _format_demucs_fallback_warning(exc: Exception) -> str:
    """Provide a user-friendly warning when Demucs falls back to simple separation."""
    if _is_certificate_verification_failure(exc):
        return (
            "Demucs 模型下载时遇到本机 SSL 证书校验失败，已自动回退到内置简易分离。"
            "如需启用高质量 Demucs 分离，请修复系统证书链或预先准备本地模型。"
        )
    return f"Demucs 分离失败，已自动回退到内置简易分离：{exc}"


class AudioSeparator:
    """Multi-track audio separator using state-of-the-art models."""

    def __init__(self, output_dir: Optional[str] = None):
        """Initialize the audio separator.
        
        Args:
            output_dir: Directory to save separated tracks. Defaults to temp directory.
        """
        self.output_dir = output_dir or tempfile.gettempdir()
        self.separator_id = str(uuid4())[:8]

    def _load_audio(self, audio_bytes: bytes, sr: int = 44100) -> tuple[np.ndarray, int]:
        """Load audio from bytes."""
        try:
            # Write bytes to temporary file for audio loading
            import tempfile
            from pathlib import Path
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = f.name
                f.write(audio_bytes)
            
            try:
                y, sr = librosa.load(temp_path, sr=sr, mono=False)
                return y, sr
            finally:
                Path(temp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            raise

    def _simple_separation(
        self,
        y: np.ndarray,
        sr: int,
        stems: int = 2
    ) -> dict[str, np.ndarray]:
        """
        更科学的频带划分：使用梅尔频率或KMeans聚类进行分离，支持多声道。
        """
        import sklearn.cluster

        if stems == 2:
            mono_mix = self._mono_mix(y)
            vocal = self._enhance_vocal_track(y, original_mix=y, sr=sr)
            vocal_mono = self._mono_mix(vocal)
            accompaniment = mono_mix - vocal_mono
            return {
                "vocal": np.asarray(vocal_mono, dtype=np.float32),
                "accompaniment": np.asarray(accompaniment, dtype=np.float32),
            }

        # 保留多声道信息，y: (channels, samples) or (samples,)
        if y.ndim == 1:
            y = y[np.newaxis, :]  # (1, samples)

        # 对每个声道分别处理，最后合成
        n_channels = y.shape[0]
        separated = {name: [] for name in STEM_NAMES.get(stems, DEFAULT_STEMS_ORDER[:stems])}

        for ch in range(n_channels):
            y_ch = y[ch]
            D = librosa.stft(y_ch)
            n_freq_bins, n_frames = D.shape

            if stems == 2:
                # 梅尔频率特征聚类
                mel_spec = librosa.feature.melspectrogram(y=y_ch, sr=sr, n_mels=64)
                mel_flat = mel_spec.T
                kmeans = sklearn.cluster.KMeans(n_clusters=2, n_init=5, random_state=42)
                labels = kmeans.fit_predict(mel_flat)
                frame_labels = labels[np.arange(n_frames) % mel_spec.shape[1]]
                frame_masks = (np.arange(2)[:, None] == frame_labels[None, :]).astype(D.real.dtype)
                masks = np.broadcast_to(frame_masks[:, None, :], (2, n_freq_bins, n_frames))
                vocal = librosa.istft(D * masks[0], length=y_ch.shape[0])
                accomp = librosa.istft(D * masks[1], length=y_ch.shape[0])
                separated["vocal"].append(vocal)
                separated["accompaniment"].append(accomp)
            elif stems >= 4:
                # 梅尔频率聚类分组
                mel_spec = librosa.feature.melspectrogram(y=y_ch, sr=sr, n_mels=128)
                mel_flat = mel_spec.T
                n_clusters = min(stems, mel_spec.shape[0])
                kmeans = sklearn.cluster.KMeans(n_clusters=n_clusters, n_init=5, random_state=42)
                labels = kmeans.fit_predict(mel_flat)
                track_names = STEM_NAMES.get(stems, DEFAULT_STEMS_ORDER[:stems])
                frame_labels = labels[np.arange(n_frames) % mel_spec.shape[1]]
                frame_masks = (np.arange(n_clusters)[:, None] == frame_labels[None, :]).astype(D.real.dtype)
                masks = np.broadcast_to(
                    frame_masks[:, None, :],
                    (n_clusters, n_freq_bins, n_frames),
                )
                for idx, name in enumerate(track_names):
                    if idx < len(masks):
                        istfted = librosa.istft(D * masks[idx], length=y_ch.shape[0])
                        separated[name].append(istfted)

        # 合成多声道输出
        results = {}
        for name, tracks in separated.items():
            if tracks:
                # (channels, samples) -> (samples,) if 单声道
                arr = np.stack([t[:min(map(len, tracks))] for t in tracks], axis=0)
                if arr.shape[0] == 1:
                    arr = arr[0]
                results[name] = arr
        return results

    def _channel_first(self, audio_data: np.ndarray) -> np.ndarray:
        array = np.asarray(audio_data, dtype=np.float32)
        if array.ndim == 1:
            return array[np.newaxis, :]
        if array.ndim == 2 and array.shape[0] <= 8 and array.shape[1] > array.shape[0]:
            return array
        if array.ndim == 2:
            return array.T
        raise ValueError(f"unsupported audio shape for separation: {array.shape}")

    def _mono_mix(self, audio_data: np.ndarray) -> np.ndarray:
        channel_first = self._channel_first(audio_data)
        return np.mean(channel_first, axis=0, dtype=np.float32).astype(np.float32)

    def _center_channel(self, audio_data: np.ndarray) -> np.ndarray:
        channel_first = self._channel_first(audio_data)
        if channel_first.shape[0] >= 2:
            return np.mean(channel_first[:2], axis=0, dtype=np.float32).astype(np.float32)
        return channel_first[0].astype(np.float32)

    def _spectral_vocal_focus(self, signal: np.ndarray, sr: int) -> np.ndarray:
        signal = np.asarray(signal, dtype=np.float32).reshape(-1)
        if signal.size == 0:
            return signal
        n_fft = 2048 if signal.size >= 2048 else max(256, 2 ** int(np.floor(np.log2(max(signal.size, 256)))))
        hop_length = max(n_fft // 4, 64)
        spectrum = librosa.stft(signal, n_fft=n_fft, hop_length=hop_length)
        frequencies = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
        mask = np.ones_like(frequencies, dtype=np.float32)
        mask[frequencies < VOCAL_BAND_LOW_HZ] = 0.0
        mask[frequencies > VOCAL_BAND_HIGH_HZ] = 0.0
        low_band = (frequencies >= VOCAL_BAND_LOW_HZ) & (frequencies < VOCAL_LOW_ATTENUATION_HZ)
        mask[low_band] *= VOCAL_LOW_ATTENUATION_GAIN
        focused = librosa.istft(spectrum * mask[:, None], hop_length=hop_length, length=signal.shape[0])
        return np.asarray(focused, dtype=np.float32)

    def _harmonic_component(self, signal: np.ndarray) -> np.ndarray:
        signal = np.asarray(signal, dtype=np.float32).reshape(-1)
        if signal.size == 0:
            return signal
        try:
            harmonic, _ = librosa.effects.hpss(signal, margin=VOCAL_HPSS_MARGIN)
        except TypeError:
            harmonic, _ = librosa.effects.hpss(signal)
        return np.asarray(harmonic, dtype=np.float32)

    def _match_signal_length(self, signal: np.ndarray, target_length: int) -> np.ndarray:
        target = max(int(target_length or 0), 0)
        vector = np.asarray(signal, dtype=np.float32).reshape(-1)
        if target <= 0:
            return np.zeros(0, dtype=np.float32)
        if vector.shape[0] == target:
            return vector
        if vector.shape[0] > target:
            return vector[:target]
        padded = np.zeros(target, dtype=np.float32)
        padded[: vector.shape[0]] = vector
        return padded

    def _match_rms(self, signal: np.ndarray, reference: np.ndarray) -> np.ndarray:
        signal = np.asarray(signal, dtype=np.float32)
        reference = np.asarray(reference, dtype=np.float32)
        signal_rms = float(np.sqrt(np.mean(signal * signal))) if signal.size else 0.0
        reference_rms = float(np.sqrt(np.mean(reference * reference))) if reference.size else 0.0
        if signal_rms <= 1e-8 or reference_rms <= 1e-8:
            return signal
        return signal * min(reference_rms / signal_rms, 2.0)

    def _enhance_vocal_track(
        self,
        vocal_audio: np.ndarray,
        *,
        original_mix: np.ndarray | None,
        sr: int,
    ) -> np.ndarray:
        reference_mono = self._mono_mix(vocal_audio)
        if reference_mono.size == 0:
            return np.asarray(reference_mono, dtype=np.float32)

        focused_vocal = self._spectral_vocal_focus(
            self._harmonic_component(reference_mono),
            sr,
        )
        enhanced = focused_vocal

        if original_mix is not None:
            centered_mix = self._center_channel(original_mix)
            centered_candidate = self._spectral_vocal_focus(
                self._harmonic_component(centered_mix),
                sr,
            )
            centered_candidate = self._match_signal_length(centered_candidate, enhanced.shape[0])
            enhanced = (1.0 - VOCAL_CENTER_BLEND) * enhanced + VOCAL_CENTER_BLEND * centered_candidate

        enhanced = self._match_rms(enhanced, reference_mono)
        return np.asarray(enhanced, dtype=np.float32)

    def _vocal_enhancement_metadata(self, original_mix: np.ndarray) -> dict[str, object]:
        channel_first = self._channel_first(original_mix)
        return {
            "center_extract_used": bool(channel_first.shape[0] >= 2),
            "hpss_harmonic_used": True,
            "band_pass_hz": [int(VOCAL_BAND_LOW_HZ), int(VOCAL_BAND_HIGH_HZ)],
            "low_frequency_attenuation_below_hz": int(VOCAL_LOW_ATTENUATION_HZ),
            "low_frequency_gain": round(float(VOCAL_LOW_ATTENUATION_GAIN), 2),
        }

    def _normalize_audio(self, audio_data: np.ndarray, peak: float = 0.95) -> np.ndarray:
        """Normalize audio peak before writing to avoid clipping."""
        normalized = np.asarray(audio_data, dtype=np.float32)
        if normalized.size == 0:
            return normalized

        max_val = float(np.max(np.abs(normalized)))
        if max_val > peak and max_val > 0.0:
            normalized = normalized / max_val * peak
        return normalized

    def _demucs_cache_dir(self) -> Path:
        """Return a writable cache directory for Demucs and Torch artifacts."""
        override = os.getenv("DEMUCS_CACHE_DIR")
        cache_dir = Path(override) if override else Path(self.output_dir) / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _demucs_repo_dir(self) -> Path:
        """Return the preferred local Demucs repository path."""
        override = os.getenv("DEMUCS_REPO_DIR")
        return Path(override) if override else Path(self.output_dir) / "demucs-repo"

    def _demucs_model_name(self) -> str:
        """Return the Demucs model identifier to load."""
        return os.getenv("DEMUCS_MODEL_NAME", "htdemucs")

    def _resolve_local_demucs_repo(self, model_name: str) -> Optional[Path]:
        """Resolve a local Demucs repo for offline execution when available.

        A valid local repo contains:
        - `{model_name}.yaml`
        - one or more `.th` checkpoint files referenced by that yaml

        If the repo contains weights but not the yaml, copy the bundled yaml from
        the installed `demucs.remote` package assets.
        """
        repo_dir = self._demucs_repo_dir()
        if not repo_dir.exists() or not repo_dir.is_dir():
            return None

        weight_files = list(repo_dir.glob("*.th"))
        if not weight_files:
            return None

        yaml_path = repo_dir / f"{model_name}.yaml"
        if not yaml_path.exists():
            from demucs import pretrained

            bundled_yaml = Path(pretrained.REMOTE_ROOT) / f"{model_name}.yaml"
            if bundled_yaml.exists():
                shutil.copy2(bundled_yaml, yaml_path)

        if yaml_path.exists():
            return repo_dir
        return None

    def _adapt_demucs_output(
        self,
        sources: np.ndarray,
        source_names: list[str],
        stems: int,
    ) -> dict[str, np.ndarray]:
        """Map Demucs source names to the stem names exposed by this service."""
        normalized_sources: dict[str, np.ndarray] = {}
        for index, name in enumerate(source_names):
            normalized_name = "vocal" if name in {"vocals", "vocal"} else name
            normalized_sources[normalized_name] = np.asarray(sources[index], dtype=np.float32)

        vocal = normalized_sources.get("vocal")
        if vocal is None:
            raise ValueError("demucs output missing vocal stem")

        if stems == 2:
            accompaniment_parts = [
                audio for name, audio in normalized_sources.items() if name != "vocal"
            ]
            accompaniment = (
                np.sum(np.stack(accompaniment_parts, axis=0), axis=0)
                if accompaniment_parts
                else np.zeros_like(vocal)
            )
            return {"vocal": vocal, "accompaniment": accompaniment}

        if stems == 4:
            return {
                name: normalized_sources[name]
                for name in STEM_NAMES[4]
                if name in normalized_sources
            }

        raise ValueError(f"demucs does not natively support {stems} stems")

    def _run_demucs_separation(self, y: np.ndarray, sr: int, stems: int) -> dict[str, np.ndarray]:
        """Run Demucs separation using a writable cache directory."""
        from demucs.apply import apply_model
        from demucs.demucs import Demucs
        from demucs.hdemucs import HDemucs
        from demucs.htdemucs import HTDemucs
        from demucs.pretrained import get_model as demucs_get_model
        from demucs import states as demucs_states
        import torch

        cache_dir = self._demucs_cache_dir()
        model_name = self._demucs_model_name()
        local_repo = self._resolve_local_demucs_repo(model_name)
        os.environ["XDG_CACHE_HOME"] = str(cache_dir)
        os.environ["TORCH_HOME"] = str(cache_dir / "torch")

        with tempfile.TemporaryDirectory(dir=self.output_dir) as tmpdir:
            input_path = os.path.join(tmpdir, "input.wav")
            sf.write(input_path, y.T if y.ndim > 1 else y, sr)

            safe_globals = [HTDemucs, HDemucs, Demucs]
            original_torch_load = demucs_states.torch.load

            def _trusted_demucs_load(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return original_torch_load(*args, **kwargs)

            demucs_states.torch.load = _trusted_demucs_load
            try:
                with torch.serialization.safe_globals(safe_globals):
                    if local_repo is not None:
                        demucs_model = demucs_get_model(name=model_name, repo=local_repo)
                    else:
                        demucs_model = demucs_get_model(name=model_name)
            finally:
                demucs_states.torch.load = original_torch_load
            demucs_model.eval()
            device = "cuda" if torch.cuda.is_available() else "cpu"
            demucs_model.to(device)

            wav, _ = librosa.load(input_path, sr=sr, mono=False)
            if wav.ndim == 1:
                wav = wav[None, :]
            expected_channels = int(getattr(demucs_model, "audio_channels", wav.shape[0]))
            if wav.shape[0] == 1 and expected_channels == 2:
                wav = np.repeat(wav, 2, axis=0)
            elif wav.shape[0] > expected_channels:
                wav = wav[:expected_channels]
            elif wav.shape[0] < expected_channels:
                wav = np.tile(wav, (expected_channels, 1))[:expected_channels]
            waveform = torch.tensor(wav, dtype=torch.float32, device=device).unsqueeze(0)

            with torch.no_grad():
                sources = apply_model(demucs_model, waveform, split=True, overlap=0.25)

        return self._adapt_demucs_output(
            sources.squeeze(0).cpu().numpy(),
            list(demucs_model.sources),
            stems,
        )

    def separate(
        self,
        file_name: str,
        model: str = "demucs",
        stems: int = 2,
        audio_bytes: Optional[bytes] = None,
        sample_rate: int = 44100,
    ) -> dict:
        """Separate audio tracks into individual stems.
        
        Args:
            file_name: Original audio file name
            model: Model to use for separation ("demucs", "umx", "tasnet")
            stems: Number of stems to separate (2, 4, 5, or 6)
            audio_bytes: Audio data in bytes
            sample_rate: Sample rate for audio processing
            
        Returns:
            Dictionary with task_id, tracks list, and model information
        """
        task_id = f"sep_{self.separator_id}_{uuid4().hex[:8]}"
        
        try:
            # Validate stems parameter
            if stems not in STEM_NAMES:
                stems = min(stems, 6) or 2

            if not audio_bytes:
                raise ValueError("No audio data provided")

            y, sr = self._load_audio(audio_bytes, sr=sample_rate)
            logger.info(f"Loaded audio: shape={y.shape}, sr={sr}")
            backend_used = "simple"
            fallback_used = False
            warnings: list[str] = []

            if model.lower() == "demucs":
                try:
                    separated_tracks = self._run_demucs_separation(y, sr, stems)
                    backend_used = "demucs"
                except Exception as exc:
                    fallback_used = True
                    warnings.append(_format_demucs_fallback_warning(exc))
                    logger.warning(
                        "Demucs separation failed for stems=%s, falling back to simple separation: %s",
                        stems,
                        exc,
                    )
                    separated_tracks = self._simple_separation(y, sr, stems)
            else:
                separated_tracks = self._simple_separation(y, sr, stems)

            vocal_enhancement = None
            if "vocal" in separated_tracks and not (backend_used == "simple" and stems == 2):
                separated_tracks["vocal"] = self._enhance_vocal_track(
                    separated_tracks["vocal"],
                    original_mix=y,
                    sr=sr,
                )
                vocal_enhancement = self._vocal_enhancement_metadata(y)
            elif "vocal" in separated_tracks:
                vocal_enhancement = self._vocal_enhancement_metadata(y)

            # Save separated tracks and prepare output
            tracks = []
            track_names = STEM_NAMES.get(stems, DEFAULT_STEMS_ORDER[:stems])
            for name in track_names:
                if name in separated_tracks:
                    audio_data = self._normalize_audio(separated_tracks[name])
                    output_path = self._save_track(
                        audio_data,
                        sr,
                        task_id,
                        name,
                        file_name
                    )
                    tracks.append({
                        "name": name,
                        "file_name": f"{task_id}_{name}.wav",
                        "download_url": f"/api/v1/audio/download/{task_id}_{name}.wav",
                        "file_path": output_path,
                        "duration": (audio_data.shape[0] if audio_data.ndim == 1 else max(audio_data.shape)) / sr,
                        **({"enhancement": vocal_enhancement} if name == "vocal" and vocal_enhancement else {}),
                    })

            return {
                "task_id": task_id,
                "tracks": tracks,
                "model": model,
                "backend_used": backend_used,
                "fallback_used": fallback_used,
                "stems": stems,
                "source_file": file_name,
                "sample_rate": sr,
                "status": "completed",
                "warnings": warnings,
                **({"vocal_enhancement": vocal_enhancement} if vocal_enhancement else {}),
            }

        except Exception as e:
            logger.error(f"Separation failed: {e}")
            return {
                "task_id": task_id,
                "tracks": [],
                "model": model,
                "stems": stems,
                "status": "failed",
                "error": str(e),
            }

    def _save_track(
        self,
        audio_data: np.ndarray,
        sr: int,
        task_id: str,
        track_name: str,
        source_file: str
    ) -> str:
        """Save separated audio track to file.
        
        Args:
            audio_data: Audio waveform
            sr: Sample rate
            task_id: Task ID for naming
            track_name: Name of the track
            source_file: Original source file name
            
        Returns:
            Path to saved file
        """
        try:
            # Create output directory if needed
            output_dir = Path(self.output_dir) / "separated_tracks"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate output file path
            output_file = output_dir / f"{task_id}_{track_name}.wav"

            # Accept both channel-first and channel-last arrays.
            if audio_data.ndim == 2 and audio_data.shape[0] <= 8 and audio_data.shape[1] > audio_data.shape[0]:
                audio_data = audio_data.T

            # Keep a defensive normalization here for direct callers of _save_track.
            audio_data = self._normalize_audio(audio_data)

            # Save as WAV file
            sf.write(str(output_file), audio_data, sr)
            logger.info(f"Saved track: {output_file}")
            
            return str(output_file)
            
        except Exception as e:
            logger.error(f"Failed to save track: {e}")
            raise

    def get_separation_status(self, task_id: str) -> dict:
        """Get status of a separation task."""
        return {
            "task_id": task_id,
            "status": "completed",
            "message": "Separation task completed successfully",
        }


# Global separator instance
_separator = None


def get_separator(output_dir: Optional[str] = None) -> AudioSeparator:
    """Get or create the global audio separator instance."""
    global _separator
    if _separator is None:
        _separator = AudioSeparator(output_dir)
    return _separator


def separate_tracks(
    file_name: str,
    model: str = "demucs",
    stems: int = 2,
    audio_bytes: bytes | None = None,
    sample_rate: int = 44100,
) -> dict:
    """Separate audio tracks into individual stems.
    
    This function performs source separation on audio files, extracting
    individual instrument tracks from mixed audio.
    
    Args:
        file_name: Original audio file name
        model: Model to use for separation ("demucs" recommended)
        stems: Number of stems to separate (2, 4, 5, or 6)
        audio_bytes: Audio data in bytes
        sample_rate: Sample rate for audio processing (default: 44100)
        
    Returns:
        dict: Contains:
            - task_id: Unique identifier for the separation task
            - tracks: List of separated tracks with metadata
            - model: Model used
            - stems: Number of stems
            - status: Task status ("completed" or "failed")
            
    Example:
        >>> result = separate_tracks(
        ...     "song.wav",
        ...     model="demucs",
        ...     stems=4,
        ...     audio_bytes=audio_data
        ... )
        >>> for track in result["tracks"]:
        ...     print(f"{track['name']}: {track['download_url']}")
    """
    separator = get_separator()
    return separator.separate(file_name, model, stems, audio_bytes, sample_rate)
