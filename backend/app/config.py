"""Configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"

_config: dict | None = None


def load_config(path: Path | None = None) -> dict:
    global _config
    p = path or CONFIG_PATH
    if p.exists():
        with open(p) as f:
            _config = yaml.safe_load(f) or {}
    else:
        _config = {}
    return _config


def get_config() -> dict:
    if _config is None:
        return load_config()
    return _config
