"""Convert pitch sequences into score structures."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.core.score.note_mapping import frequency_to_note
from backend.core.score.score_utils import create_score


def build_score_from_pitch_sequence(
    pitch_sequence: List[Dict[str, Any]],
    tempo: int = 120,
    time_signature: str = "4/4",
    key_signature: str = "C",
) -> Dict[str, Any]:
    measures = [{"measure_no": 1, "notes": []}]
    for index, item in enumerate(pitch_sequence, start=1):
        note = frequency_to_note(float(item.get("frequency", 0)))
        measures[0]["notes"].append(
            {
                "note_id": f"n_{index}",
                "pitch": note,
                "duration": "quarter" if item.get("duration", 0.5) >= 0.5 else "eighth",
                "start_beat": index,
            }
        )
    return create_score(measures, tempo=tempo, time_signature=time_signature, key_signature=key_signature)

