"""Pitch-related algorithms."""

try:
    from .audio_utils import infer_audio_metadata
    from .pitch_comparison import build_pitch_comparison_payload, load_pitch_sequence_json
    from .pitch_detection import detect_pitch_sequence
    from .realtime_tuning import analyze_audio_frame
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    pass
