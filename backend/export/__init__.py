"""Export helpers with lazy imports."""

from __future__ import annotations

from typing import Any


def build_export_files(*args: Any, **kwargs: Any):
    from .export_utils import build_export_files as _impl

    return _impl(*args, **kwargs)


def export_traditional_score(*args: Any, **kwargs: Any):
    from .traditional_export import export_traditional_score as _impl

    return _impl(*args, **kwargs)


def export_guitar_lead_sheet_pdf(*args: Any, **kwargs: Any):
    from .guitar_export import export_guitar_lead_sheet_pdf as _impl

    return _impl(*args, **kwargs)


__all__ = ["build_export_files", "export_traditional_score", "export_guitar_lead_sheet_pdf"]
