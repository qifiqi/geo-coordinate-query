"""Persistent API key configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import get_app_dir

CONFIG_FILE = get_app_dir() / "config.json"
DEFAULT_CONFIG: dict[str, str] = {"api_key": "", "baidu_ak": ""}
_config: dict[str, Any] = {}


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    """Load config from disk, falling back to known defaults."""
    if not path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

    return {**DEFAULT_CONFIG, **data}


def save_config(config: dict[str, Any], path: Path = CONFIG_FILE) -> None:
    """Save config using UTF-8 so Chinese paths and notes stay readable."""
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(config, file_obj, ensure_ascii=False, indent=2)


def get_config() -> dict[str, Any]:
    global _config
    if not _config:
        _config = load_config()
    return _config


def update_config(**values: str) -> None:
    config = get_config()
    config.update(values)
    save_config(config)


def get_api_key() -> str:
    return str(get_config().get("api_key", ""))


def get_baidu_ak() -> str:
    return str(get_config().get("baidu_ak", ""))
