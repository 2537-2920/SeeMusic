"""Visualization payload builders."""

from __future__ import annotations

from typing import Any, Dict, List


def build_pitch_curve(reference_curve: List[Dict[str, Any]], user_curve: List[Dict[str, Any]]) -> dict:
    x_axis = [item.get("time", index) for index, item in enumerate(reference_curve or user_curve)]
    reference_values = [item.get("frequency", 0) for item in reference_curve]
    user_values = [item.get("frequency", 0) for item in user_curve]
    deviation_values = [round(user - ref, 2) for ref, user in zip(reference_values, user_values)]
    return {
        "x_axis": x_axis,
        "reference_curve": reference_values,
        "user_curve": user_values,
        "deviation_curve": deviation_values,
    }

