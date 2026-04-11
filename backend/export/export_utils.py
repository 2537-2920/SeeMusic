"""Export utility helpers."""

from __future__ import annotations


def build_export_files(resource_id: str, formats: list[str]) -> list[dict]:
    return [
        {
            "format": fmt,
            "download_url": f"https://example.com/download/{resource_id}.{fmt}",
            "expires_in": 3600,
        }
        for fmt in formats
    ]

