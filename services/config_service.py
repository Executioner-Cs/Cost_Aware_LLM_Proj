"""Configuration and home-directory loading.

Single source for the orchestrator home directory and the parsed config. It has
no initialization side effects, so any layer (core, cli, agent) can load config
without importing the heavier ``init_service`` flow. ``init_service`` re-exports
``get_home`` and ``load_config`` from here for backward compatibility.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path


def get_home() -> Path:
    return Path(os.environ.get("ORCHESTRATOR_HOME", Path.home() / ".orchestrator"))


def load_config(home: Path | None = None) -> dict:
    if home is None:
        home = get_home()
    config_path = home / "config.toml"
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)
