"""Multi-track separation stubs."""

from __future__ import annotations


def separate_tracks(
    file_name: str,
    model: str = "demucs",
    stems: int = 2,
    audio_bytes: bytes | None = None,
) -> dict:
    tracks = []
    names = ["vocal", "accompaniment", "drums", "bass", "other"]
    for index in range(min(stems, len(names))):
        name = names[index]
        tracks.append(
            {
                "name": name,
                "download_url": f"https://example.com/{file_name}_{model}_{name}.wav",
            }
        )
    return {"task_id": f"sep_{file_name}", "tracks": tracks, "model": model}

