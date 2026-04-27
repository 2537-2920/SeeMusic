"""Score-related algorithms.

This module intentionally avoids eager imports for heavy submodules to prevent
package-level circular imports during app startup.
"""

from __future__ import annotations

from typing import Any

from .note_mapping import frequency_to_note


def build_canonical_score_from_musicxml(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .musicxml_utils import build_canonical_score_from_musicxml as _impl

    return _impl(*args, **kwargs)


def build_musicxml_from_measures(*args: Any, **kwargs: Any) -> str:
    from .musicxml_utils import build_musicxml_from_measures as _impl

    return _impl(*args, **kwargs)


def build_score_from_pitch_sequence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .sheet_extraction import build_score_from_pitch_sequence as _impl

    return _impl(*args, **kwargs)


def create_score(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .score_utils import create_score as _impl

    return _impl(*args, **kwargs)


def get_score(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .score_utils import get_score as _impl

    return _impl(*args, **kwargs)


def undo_score(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .score_utils import undo_score as _impl

    return _impl(*args, **kwargs)


def redo_score(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .score_utils import redo_score as _impl

    return _impl(*args, **kwargs)


def update_score_musicxml(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .score_utils import update_score_musicxml as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "build_canonical_score_from_musicxml",
    "build_musicxml_from_measures",
    "build_score_from_pitch_sequence",
    "create_score",
    "frequency_to_note",
    "get_score",
    "redo_score",
    "undo_score",
    "update_score_musicxml",
]
