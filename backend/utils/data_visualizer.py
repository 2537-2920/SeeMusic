"""Visualization payload builders."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.core.pitch.pitch_comparison import build_pitch_comparison_payload

def build_pitch_curve(reference_curve: List[Dict[str, Any]], user_curve: List[Dict[str, Any]]) -> dict:
    return build_pitch_comparison_payload(reference_curve, user_curve)
