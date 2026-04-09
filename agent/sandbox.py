"""Resolve and constrain paths under a sandbox root."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Sandbox:
    root: Path
    max_file_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

    def resolve_path(self, path_str: str) -> Path:
        raw = Path(path_str)
        if raw.is_absolute():
            candidate = raw.resolve()
        else:
            candidate = (self.root / raw).resolve()
        self._ensure_under_root(candidate)
        return candidate

    def _ensure_under_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Path outside sandbox: {path}") from exc
