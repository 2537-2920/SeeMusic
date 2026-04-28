"""Guitar lead-sheet helpers."""

from .lead_sheet import (
    extract_melody_from_musicxml,
    generate_guitar_lead_sheet,
    generate_guitar_lead_sheet_from_musicxml,
)

try:
    from .audio_pipeline import generate_guitar_lead_sheet_from_audio
except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency guard
    if exc.name != "verovio":
        raise
