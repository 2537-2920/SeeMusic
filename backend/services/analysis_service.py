"""End-to-end audio analysis orchestration."""

from __future__ import annotations

import soundfile as sf
from typing import Any

from backend.core.pitch.audio_utils import infer_audio_metadata
from backend.core.pitch.pitch_detection import detect_pitch_sequence
from backend.core.score.sheet_extraction import build_score_from_pitch_sequence
from backend.utils.audio_logger import record_audio_log
from backend.utils.data_visualizer import build_pitch_curve


def analyze_audio(file_name: str, audio_bytes: bytes, sample_rate: int | None = None) -> dict[str, Any]:
    from backend.core.rhythm.beat_detection import detect_beats

    metadata = infer_audio_metadata(file_name, sample_rate=sample_rate, duration=None)
    pitch_sequence = detect_pitch_sequence(
        file_name=file_name,
        sample_rate=metadata["sample_rate"],
        duration=metadata["duration"],
        audio_bytes=audio_bytes,
    )
    beat_result = detect_beats(file_name, audio_bytes=audio_bytes)
    score = build_score_from_pitch_sequence(pitch_sequence)
    pitch_curve = build_pitch_curve(pitch_sequence, pitch_sequence)
    log_entry = record_audio_log(
        {
            "file_name": file_name,
            "sample_rate": metadata["sample_rate"],
            "duration": metadata["duration"],
            "analysis_id": metadata["analysis_id"],
        }
    )
    return {
        "analysis_id": metadata["analysis_id"],
        "pitch_sequence": pitch_sequence,
        "beat_result": beat_result,
        "score": score,
        "pitch_curve": pitch_curve,
        "log": log_entry,
    }


async def process_rhythm_scoring(
    user_audio_path: str,
    ref_audio_path: str,
    language: str = 'en',
    scoring_model: str = 'balanced',
    threshold_ms: float = 50.0,
) -> dict[str, Any]:
    """
    Comprehensive rhythm scoring between user and reference audio files.
    
    Analyzes beat timing, consistency, and provides multilingual feedback.
    
    Args:
        user_audio_path: Path to user's audio file
        ref_audio_path: Path to reference audio file
        language: Language for feedback ('en', 'zh'). Default 'en'
        scoring_model: Scoring model ('strict', 'balanced', 'lenient'). Default 'balanced'
        threshold_ms: Time window for on-time classification (ms). Default 50
        
    Returns:
        Dict with score, analysis results, and multilingual feedback
        
    Example:
        ```python
        result = await process_rhythm_scoring(
            '/tmp/user_singing.wav',
            'assets/references/default_ref.wav',
            language='zh',
            scoring_model='balanced'
        )
        print(result['score'])  # 85.5
        print(result['feedback']['main_issues'])  # ['做得很好！']
        ```
    """
    from backend.core.rhythm.beat_detection import AdvancedBeatDetector
    from backend.core.rhythm.i18n import FeedbackFormatter
    from backend.core.rhythm.rhythm_analysis import AdvancedRhythmAnalyzer

    # Initialize analyzers
    beat_detector = AdvancedBeatDetector()
    rhythm_analyzer = AdvancedRhythmAnalyzer(threshold_ms=threshold_ms)
    
    # Read audio files
    try:
        user_audio, user_sr = sf.read(user_audio_path, dtype='float32')
        ref_audio, ref_sr = sf.read(ref_audio_path, dtype='float32')
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Audio file not found: {e.filename}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to read audio file: {str(e)}") from e
    
    # Convert to mono if stereo
    if len(user_audio.shape) > 1:
        user_audio = user_audio.mean(axis=1)
    if len(ref_audio.shape) > 1:
        ref_audio = ref_audio.mean(axis=1)
    
    # Detect beats using optimized beat detector
    try:
        user_beat_result = beat_detector.get_beats(user_audio, user_sr)
        ref_beat_result = beat_detector.get_beats(ref_audio, ref_sr)
        
        user_beats = user_beat_result['beats']
        ref_beats = ref_beat_result['beats']
    except Exception as e:
        raise RuntimeError(f"Beat detection failed: {str(e)}") from e
    
    # Compare rhythms with optimized analyzer (with language support)
    try:
        comparison_result = rhythm_analyzer.compare_rhythm(
            user_beats,
            ref_beats,
            scoring_model=scoring_model,
            language=language  # NEW: Language parameter for i18n
        )
    except Exception as e:
        raise RuntimeError(f"Rhythm comparison failed: {str(e)}") from e
    
    # Format formatter for additional metrics
    formatter = FeedbackFormatter(language)
    
    # Build comprehensive response
    return {
        # Core scores
        'score': comparison_result['score'],
        'timing_accuracy': comparison_result['timing_accuracy'],
        'mean_deviation_ms': comparison_result['mean_deviation_ms'],
        'max_deviation_ms': comparison_result['max_deviation_ms'],
        'std_deviation_ms': comparison_result['std_deviation_ms'],
        
        # Beat analysis
        'missing_beats': comparison_result['missing_beats'],
        'extra_beats': comparison_result['extra_beats'],
        'valid_matches': comparison_result['valid_matches'],
        'total_ref_beats': comparison_result['total_ref_beats'],
        'coverage_ratio': comparison_result['coverage_ratio'],
        
        # Consistency and tempo
        'user_consistency': comparison_result['user_consistency'],
        'ref_consistency': comparison_result['ref_consistency'],
        'consistency_ratio': comparison_result['consistency_ratio'],
        'tempo_analysis': comparison_result['tempo_analysis'],
        
        # Error classification
        'error_classification': comparison_result['error_classification'],
        
        # Feedback (multilingual)
        'feedback': comparison_result['feedback'],
        'detailed_assessment': comparison_result['detailed_assessment'],
        
        # Metadata
        'language': language,
        'scoring_model': scoring_model,
        'analysis_type': 'rhythm_comparison',
        'reference_duration': float(len(ref_audio) / ref_sr),
        'user_duration': float(len(user_audio) / user_sr),
        'reference_bpm': ref_beat_result.get('bpm', 0),
        'user_bpm': user_beat_result.get('bpm', 0),
    }
