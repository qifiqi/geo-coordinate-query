"""Runtime path helpers."""

from __future__ import annotations

from pathlib import Path
import sys


def get_app_dir() -> Path:
    """Return the executable directory, including PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
