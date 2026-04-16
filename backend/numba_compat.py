"""Helpers for keeping numba-backed audio libs usable in restricted envs."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def ensure_numba_cache_dir() -> Path:
    """Provide numba a writable cache dir before importing librosa/numba users."""
    configured = os.environ.get("NUMBA_CACHE_DIR")
    cache_dir = Path(configured) if configured else Path(tempfile.gettempdir()) / "seemusic-numba-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = str(cache_dir)
    return cache_dir
