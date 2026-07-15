"""Compatibility wrapper for Baidu Excel batch geocoding."""

from __future__ import annotations

from pathlib import Path

from .excel_processor import BatchSummary, ProgressCallback, StatusCallback, process_excel


def process_baidu_excel(
    file_path: str | Path,
    output_path: str | Path | None = None,
    log: ProgressCallback | None = None,
    status: StatusCallback | None = None,
    sleep_seconds: float = 0.15,
) -> BatchSummary:
    """Geocode a workbook through the Baidu provider strategy."""
    return process_excel(file_path, "baidu", output_path, log, status, sleep_seconds)
