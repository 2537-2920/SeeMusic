"""Traditional instrument presets."""

from __future__ import annotations


def get_traditional_instruments() -> dict:
    return {
        "guzheng": {"range": "D2-D6", "family": "plucked", "tuning": "21弦 D调定弦"},
        "erhu": {"range": "D4-A6", "family": "bowed"},
        "pipa": {"range": "A3-A6", "family": "plucked"},
        "dizi": {
            "range": "D4-C7",
            "family": "wind",
            "default_flute_type": "G",
            "supported_flute_types": ["C", "D", "E", "F", "G", "A", "Bb"],
        },
    }
