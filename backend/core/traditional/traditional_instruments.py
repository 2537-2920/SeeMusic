"""Traditional instrument presets."""

from __future__ import annotations


def get_traditional_instruments() -> dict:
    return {
        "guzheng": {"range": "D3-D6", "family": "plucked"},
        "erhu": {"range": "D4-A6", "family": "bowed"},
        "pipa": {"range": "A3-A6", "family": "plucked"},
        "dizi": {"range": "D4-C7", "family": "wind"},
    }

