import io

from backend.numba_compat import ensure_numba_cache_dir

ensure_numba_cache_dir()

import librosa
import numpy as np
import soundfile as sf
from scipy import signal
from typing import Tuple, List, Dict, Optional, Union, Any

from backend.core.pitch.audio_utils import load_audio_waveform

class AdvancedBeatDetector:
    """Stable beat detection for complex audio and multiple tempo styles.
    
    High-quality beat detection system using:
    - HPSS source separation for robustness
    - Multi-candidate BPM estimation via Tempogram analysis
    - Dynamic programming beat tracking with sensitivity control
    - Quality-based candidate selection
    
    Typical workflow:
    ```python
    detector = AdvancedBeatDetector()
    y = detector._load_audio('song.wav')
    tempo, beat_times, info = detector.get_beats(y, bpm_hint=120, sensitivity=0.7)
    ```
    
    Attributes:
        sr: Sample rate (Hz). Default 22050 Hz is standard for audio processing.
        hop_length: Frame step length (samples). Controls time resolution.
        trim_top_db: Silence threshold (dB). Removes quiet leading/trailing sections.
        bpm_bounds: Valid BPM range (min, max). Default (40, 240) covers most music.
    """

    def __init__(self, sr: int = 22050, hop_length: int = 512, trim_top_db: int = 20):
        """Initialize beat detector.
        
        Args:
            sr: Target sample rate (Hz). Default 22050 is standard.
            hop_length: Hop length for STFT (samples). Default 512 = ~23ms at 22050 Hz.
            trim_top_db: Silence trimming threshold (dB). Lower value trims more.
        """
        self.sr = sr
        self.hop_length = hop_length
        self.trim_top_db = trim_top_db
        self.bpm_bounds = (40, 240)  # Typical music tempo range

    def get_beats(
        self,
        y: np.ndarray,
        auto_bpm: bool = True,
        n_candidates: int = 4,
        bpm_hint: Optional[float] = None,
        sensitivity: float = 0.5,
    ) -> Tuple[float, List[float], Dict]:
        """Detect beats and return beat times, tempo info, and quality assessment.
        
        Performs multi-stage beat detection:
        1. Audio trimming and normalization
        2. HPSS source separation (harmonic/percussive)
        3. Onset strength envelope extraction
        4. Multi-candidate BPM estimation
        5. Optimal beat sequence selection
        
        Args:
            y: Audio waveform (mono, numpy array).
            auto_bpm: Whether to estimate BPM automatically.
            n_candidates: Number of BPM candidates to generate.
            bpm_hint: User-provided BPM hint (optional).
            sensitivity: Beat tracking sensitivity [0.0-1.0].
                  0.0 = loose tracking, 1.0 = strict tracking.
        
        Returns:
            Tuple of (tempo, beat_times_list, info_dict) where:
            - tempo: Detected tempo in BPM (float).
            - beat_times: List of beat timestamps in seconds.
            - info: Dict with BPM candidates, beat strengths, quality metrics.
        
        Examples:
            ```python
            # Example 1: Basic beat detection
            detector = AdvancedBeatDetector()
            y, sr = librosa.load('song.wav')
            tempo, beats, info = detector.get_beats(y)
            print(f"Detected BPM: {tempo:.1f}")
            print(f"Confidence: {info['beat_quality']['confidence']:.2%}")
            
            # Example 2: With BPM hint and strict sensitivity
            tempo, beats, info = detector.get_beats(
                y, bpm_hint=120.0, sensitivity=0.8, n_candidates=6
            )
            ```
        """
        y_trimmed, index = librosa.effects.trim(y, top_db=self.trim_top_db)
        start_time = index[0] / self.sr

        y_harmonic, y_percussive = librosa.effects.hpss(y_trimmed)
        onset_env = librosa.onset.onset_strength(
            y=y_percussive, sr=self.sr, hop_length=self.hop_length, aggregate=np.mean
        )
        onset_env = librosa.util.normalize(onset_env)

        bpm_candidates = []
        if bpm_hint:
            bpm_candidates.extend(self._build_hint_candidates(bpm_hint))

        if auto_bpm or not bpm_candidates:
            bpm_candidates.extend(
                self.estimate_tempo_candidates(onset_env, n_candidates=n_candidates)
            )

        bpm_candidates = self._dedupe_candidates(bpm_candidates)
        beat_tightness = self._tightness_for_sensitivity(sensitivity)

        tempo, beat_frames, selected_bpm, beat_quality = self._select_best_beat_sequence(
            onset_env, bpm_candidates, tightness=beat_tightness
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=self.sr) + start_time
        beat_strengths = self._compute_beat_strengths(onset_env, beat_frames)

        return float(tempo), beat_times.tolist(), {
            'primary_bpm': float(selected_bpm),
            'bpm_candidates': [float(bpm) for bpm in bpm_candidates],
            'beat_strengths': beat_strengths.tolist(),
            'beat_quality': beat_quality,
            'num_beats': len(beat_times),
            'trimmed_start': float(start_time),
            'sensitivity': float(sensitivity),
        }

    def estimate_tempo_candidates(
        self, onset_env: np.ndarray, n_candidates: int = 6
    ) -> List[float]:
        """Extract multiple tempo candidates from the tempogram.
        
        Generates a set of BPM hypotheses by analyzing the global
        tempogram (time-frequency representation of tempo).
        Includes octave-related candidates (BPM/2, BPM×2) to handle
        potential harmonic relationships.
        
        Args:
            onset_env: Normalized onset strength envelope.
            n_candidates: Number of top BPM candidates to return.
            
        Returns:
            List of BPM candidates (floats) sorted by strength.
        """
        tempogram = librosa.feature.tempogram(
            onset_envelope=onset_env, sr=self.sr, hop_length=self.hop_length
        )
        global_tempogram = np.mean(tempogram, axis=1)
        tempo_bins = librosa.tempo_frequencies(
            global_tempogram.shape[0], sr=self.sr, hop_length=self.hop_length
        )

        candidate_mask = np.logical_and(
            tempo_bins >= self.bpm_bounds[0], tempo_bins <= self.bpm_bounds[1]
        )
        filtered_bins = tempo_bins[candidate_mask]
        filtered_strength = global_tempogram[candidate_mask]

        if len(filtered_bins) == 0:
            return [70.0, 120.0]

        peak_idxs, _ = signal.find_peaks(filtered_strength, distance=2)
        if len(peak_idxs) == 0:
            peak_idxs = np.argsort(filtered_strength)[::-1][:n_candidates]
        else:
            peak_idxs = np.concatenate(
                [peak_idxs, np.argsort(filtered_strength)[::-1][:n_candidates]]
            )

        bpm_candidates: List[float] = []
        for idx in peak_idxs:
            bpm = float(filtered_bins[idx])
            if bpm not in bpm_candidates:
                bpm_candidates.append(bpm)
            if len(bpm_candidates) >= n_candidates:
                break

        if len(bpm_candidates) < n_candidates:
            extra_idxs = np.argsort(filtered_strength)[::-1]
            for idx in extra_idxs:
                bpm = float(filtered_bins[idx])
                if bpm not in bpm_candidates:
                    bpm_candidates.append(bpm)
                if len(bpm_candidates) >= n_candidates:
                    break

        # Add octave-related candidates for robustness
        octave_candidates: List[float] = []
        for bpm in list(bpm_candidates):
            for corrected in [bpm / 2.0, bpm * 2.0]:
                if (
                    self.bpm_bounds[0] <= corrected <= self.bpm_bounds[1]
                    and corrected not in bpm_candidates
                ):
                    octave_candidates.append(corrected)
        bpm_candidates.extend(octave_candidates)

        return bpm_candidates[:n_candidates]

    def _build_hint_candidates(self, bpm_hint: float) -> List[float]:
        """Build BPM candidates from user hint.
        
        Given a user-provided BPM, generates additional octave-related
        candidates (BPM/2, BPM×2) to improve robustness against
        off-by-octave errors.
        
        Args:
            bpm_hint: User-provided BPM value.
            
        Returns:
            List of BPM candidates within valid bounds.
        """
        hints = [float(bpm_hint)]
        if self.bpm_bounds[0] <= bpm_hint / 2.0 <= self.bpm_bounds[1]:
            hints.append(float(bpm_hint / 2.0))
        if self.bpm_bounds[0] <= bpm_hint * 2.0 <= self.bpm_bounds[1]:
            hints.append(float(bpm_hint * 2.0))
        return hints

    def _dedupe_candidates(self, candidates: List[float]) -> List[float]:
        """Remove duplicate BPM candidates within rounding tolerance.
        
        Eliminates near-duplicates by rounding to 1 decimal place,
        keeping the first occurrence of each unique value.
        
        Args:
            candidates: List of BPM candidates (may contain duplicates).
            
        Returns:
            List of unique BPM candidates.
        """
        seen = set()
        unique = []
        for bpm in candidates:
            rounded = round(bpm, 1)
            if rounded not in seen:
                seen.add(rounded)
                unique.append(bpm)
        return unique

    def _tightness_for_sensitivity(self, sensitivity: float) -> float:
        """Convert a [0, 1] sensitivity value into beat-track tightness.
        
        Maps user-facing sensitivity parameter to librosa's internal
        tightness parameter. Higher sensitivity = stricter beat tracking.
        
        Args:
            sensitivity: User sensitivity [0.0 (loose) to 1.0 (strict)].
            
        Returns:
            Tightness parameter for beat_track (40-160 range).
        """
        sensitivity = max(0.0, min(1.0, sensitivity))
        return 40.0 + (1.0 - sensitivity) * 120.0

    def _load_audio(self, audio_path: str, audio_bytes: Optional[bytes] = None) -> np.ndarray:
        """Load audio from file path or bytes buffer.
        
        Automatically resamples to target sample rate if different.
        Converts to mono if necessary.
        
        Args:
            audio_path: Path to audio file (ignored if audio_bytes provided).
            audio_bytes: Optional bytes buffer containing audio data.
            
        Returns:
            Mono audio waveform at target sample rate.
        """
        if audio_bytes is not None:
            y, sr = load_audio_waveform(
                audio_bytes,
                file_name=audio_path,
                sample_rate=None,
                mono=True,
            )
        else:
            y, sr = librosa.load(audio_path, sr=None, mono=True)

        if sr != self.sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=self.sr)
        return y

    def _select_best_beat_sequence(
        self,
        onset_env: np.ndarray,
        bpm_candidates: List[float],
        tightness: float = 100.0,
    ) -> Tuple[float, np.ndarray, float, Dict]:
        """Select the best beat sequence from tempo candidates.
        
        Evaluates each BPM candidate and selects the one with the highest
        combined score across confidence, regularity, and strength metrics.
        
        Algorithm:
        1. For each BPM candidate, perform beat tracking
        2. Assess quality (regularity, strength, confidence)
        3. Compute weighted score
        4. Return best-scoring sequence
        
        Args:
            onset_env: Normalized onset strength envelope.
            bpm_candidates: List of BPM hypotheses to evaluate.
            tightness: Beat tracking tightness parameter (40-160).
            
        Returns:
            Tuple of (best_tempo, beat_frames, selected_bpm, quality_dict).
        """
        best_score = -1.0
        best_tempo = 0.0
        best_frames = np.array([], dtype=int)
        best_bpm = bpm_candidates[0] if bpm_candidates else 70.0
        best_quality = {
            'confidence': 0.0,
            'regularity': 0.0,
            'strength': 0.0,
            'mean_interval_ms': 0.0,
        }

        # Evaluate each candidate
        for candidate in bpm_candidates:
            try:
                tempo, beat_frames = self._track_beats_for_candidate(
                    onset_env, candidate, tightness=tightness
                )
            except Exception:
                continue

            # Require minimum beats for valid sequence
            if len(beat_frames) < 3:
                continue

            # Assess quality
            beat_times = librosa.frames_to_time(beat_frames, sr=self.sr)
            strengths = self._compute_beat_strengths(onset_env, beat_frames)
            quality = self._assess_beat_quality(beat_times, strengths)
            
            # Weighted score (confidence heavy, regularity secondary, strength tertiary)
            score = (
                quality['confidence'] * 0.55
                + quality['regularity'] * 0.30
                + quality['strength'] * 0.15
            )

            if score > best_score:
                best_score = score
                best_tempo = float(tempo)
                best_frames = beat_frames
                best_bpm = float(candidate)
                best_quality = quality

        # Fallback: if no candidate succeeded, use first BPM candidate
        if best_score < 0 and bpm_candidates:
            try:
                tempo, beat_frames = self._track_beats_for_candidate(
                    onset_env, bpm_candidates[0], tightness=tightness
                )
                beat_times = librosa.frames_to_time(beat_frames, sr=self.sr)
                strengths = self._compute_beat_strengths(onset_env, beat_frames)
                best_quality = self._assess_beat_quality(beat_times, strengths)
                best_tempo = float(tempo)
                best_frames = beat_frames
            except Exception:
                pass

        return best_tempo, best_frames, best_bpm, best_quality

    def _track_beats_for_candidate(
        self,
        onset_env: np.ndarray,
        candidate_bpm: float,
        tightness: float = 100.0,
    ) -> Tuple[float, np.ndarray]:
        """Track beats for one BPM hypothesis without relying on librosa.beat."""
        if len(onset_env) == 0:
            return 0.0, np.array([], dtype=int)

        candidate_bpm = float(candidate_bpm) if candidate_bpm else 0.0
        if candidate_bpm <= 0:
            candidate_bpm = 120.0

        interval_frames = max(
            int(round((60.0 / candidate_bpm) * self.sr / self.hop_length)),
            1,
        )
        min_distance = max(int(interval_frames * 0.6), 1)
        tolerance_ratio = max(0.1, 0.4 - min(max(tightness, 40.0), 160.0) / 160.0 * 0.25)
        tolerance = max(int(interval_frames * tolerance_ratio), 1)
        prominence = max(float(np.std(onset_env)) * 0.3, 0.01)

        peak_frames, _ = signal.find_peaks(
            onset_env,
            distance=min_distance,
            prominence=prominence,
        )

        if len(peak_frames) >= 2:
            selected = [int(peak_frames[0])]
            for frame in peak_frames[1:]:
                expected = selected[-1] + interval_frames
                if frame - selected[-1] < max(min_distance // 2, 1):
                    continue
                if abs(frame - expected) <= tolerance or frame - selected[-1] >= min_distance:
                    selected.append(int(frame))
            beat_frames = np.asarray(selected, dtype=int)
        else:
            beat_frames = np.array([], dtype=int)

        if len(beat_frames) < 2:
            beat_frames = np.arange(0, len(onset_env), interval_frames, dtype=int)

        if len(beat_frames) >= 2:
            median_interval = max(float(np.median(np.diff(beat_frames))), 1.0)
            tempo = 60.0 * self.sr / (median_interval * self.hop_length)
        elif len(beat_frames) == 1:
            tempo = candidate_bpm
        else:
            tempo = 0.0

        return float(tempo), beat_frames

    def _compute_beat_strengths(
        self, onset_env: np.ndarray, beat_frames: np.ndarray
    ) -> np.ndarray:
        """Compute beat strength for each beat frame.
        
        Extracts the maximum onset strength in a window around each
        detected beat frame to measure beat prominence.
        
        Args:
            onset_env: Normalized onset strength envelope.
            beat_frames: Frame indices of detected beats.
            
        Returns:
            Array of strength values (0-1) for each beat.
        """
        strengths = []
        window = 8  # Frames
        for frame in beat_frames:
            start = max(0, frame - window)
            end = min(len(onset_env), frame + window + 1)
            strengths.append(float(np.max(onset_env[start:end])))
        return np.array(strengths, dtype=float)

    def _assess_beat_quality(self, beat_times: np.ndarray, beat_strengths: np.ndarray) -> Dict:
        """Assess beat detection quality.
        
        Evaluates beat sequence quality across multiple dimensions:
        - Regularity: How evenly spaced are the beats?
        - Strength: How prominent are the beat onsets?
        - Confidence: Weighted combination of regularity and strength.
        
        Args:
            beat_times: Timestamps of detected beats.
            beat_strengths: Strength values for each beat.
            
        Returns:
            Dict with confidence, regularity, strength, mean_interval_ms.
        """
        if len(beat_times) < 2:
            return {
                'confidence': 0.0,
                'regularity': 0.0,
                'strength': 0.0,
                'mean_interval_ms': 0.0,
            }

        intervals = np.diff(beat_times)
        mean_interval = float(np.mean(intervals))
        interval_std = float(np.std(intervals))
        
        # Regularity: 1 - (normalized std dev)
        regularity = max(0.0, 1.0 - interval_std / (mean_interval + 1e-8))
        
        # Strength: average beat prominence
        strength_score = float(np.mean(beat_strengths))
        strength_score = max(0.0, min(1.0, strength_score))
        
        # Combined confidence
        confidence = regularity * 0.65 + strength_score * 0.35

        return {
            'confidence': float(confidence),
            'regularity': float(regularity),
            'strength': float(strength_score),
            'mean_interval_ms': float(mean_interval * 1000.0),
        }

    def segment_by_beats(
        self, y: np.ndarray, beat_times: List[float]
    ) -> List[np.ndarray]:
        """Split audio by beat timestamps.
        
        Divides the audio waveform into segments at provided beat boundaries.
        Useful for per-beat analysis or visualization.
        
        Args:
            y: Audio waveform.
            beat_times: List of beat timestamps (seconds).
            
        Returns:
            List of audio segments (numpy arrays).
        """
        samples = librosa.time_to_samples(beat_times, sr=self.sr)
        samples = samples[samples < len(y)]
        if len(samples) == 0:
            return [y]
        return np.split(y, samples)


def detect_beats(
    audio_path: str,
    bpm_hint: Optional[float] = None,
    sensitivity: float = 0.5,
    audio_bytes: Optional[bytes] = None,
) -> dict:
    """Wrapper function for backward-compatible beat detection.
    
    High-level convenience function that handles full beat detection
    pipeline in a single call.
    
    Args:
        audio_path: Path to audio file.
        bpm_hint: Optional user-provided BPM hint.
        sensitivity: Beat tracking sensitivity [0.0-1.0].
        audio_bytes: Optional bytes buffer (overrides audio_path).
        
    Returns:
        Dict with beat_times, bpm, multiple BPM candidates, quality metrics.
    
    Examples:
        ```python
        # Simple detection from file
        result = detect_beats('song.wav')
        print(f"BPM: {result['bpm']:.1f}")
        
        # With BPM hint and custom sensitivity
        result = detect_beats('song.wav', bpm_hint=120.0, sensitivity=0.8)
        
        # From audio bytes (e.g., uploaded file)
        with open('song.wav', 'rb') as f:
            result = detect_beats('dummy.wav', audio_bytes=f.read())
        ```
    """
    detector = AdvancedBeatDetector()
    y = detector._load_audio(audio_path, audio_bytes)
    tempo, beat_times, info = detector.get_beats(
        y, auto_bpm=True, n_candidates=6, bpm_hint=bpm_hint, sensitivity=sensitivity
    )
    if not beat_times and len(y) > 0:
        fallback_bpm = float(bpm_hint or info.get("primary_bpm") or 120.0)
        fallback_bpm = fallback_bpm if fallback_bpm > 0 else 120.0
        interval = 60.0 / fallback_bpm
        duration = len(y) / detector.sr
        beat_times = np.arange(0.0, max(duration, interval), interval, dtype=float).tolist()
        info["primary_bpm"] = fallback_bpm
        info["bpm_candidates"] = info.get("bpm_candidates") or [fallback_bpm]
        info["beat_strengths"] = [0.0 for _ in beat_times]
        info["num_beats"] = len(beat_times)
        info["beat_quality"] = {
            "confidence": 0.0,
            "regularity": 0.0,
            "strength": 0.0,
            "mean_interval_ms": float(interval * 1000.0),
        }
        tempo = fallback_bpm

    result = {
        'beat_times': beat_times,
        'bpm': float(tempo),
        'sensitivity': float(sensitivity),
        'primary_bpm': info['primary_bpm'],
        'bpm_candidates': info['bpm_candidates'],
        'beat_strengths': info['beat_strengths'],
        'beat_quality': info['beat_quality'],
        'num_beats': info['num_beats'],
        'trimmed_start': info['trimmed_start'],
    }
    if bpm_hint is not None:
        result['bpm_hint'] = float(bpm_hint)
    return result


class BeatDetector(AdvancedBeatDetector):
    """Compatibility wrapper for the existing interface.
    
    Provides backward compatibility with older BeatDetector API
    while delegates to the advanced implementation.
    """

    def get_beats(self, y: np.ndarray) -> Tuple[float, List[float]]:
        """Detect beats with default parameters.
        
        Simplified API for basic beat detection without advanced options.
        
        Args:
            y: Audio waveform.
            
        Returns:
            Tuple of (tempo, beat_times_list).
        """
        tempo, beat_times, _ = super().get_beats(y, auto_bpm=True)
        return tempo, beat_times
