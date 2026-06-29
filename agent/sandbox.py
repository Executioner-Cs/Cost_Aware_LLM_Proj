"""Resolve and constrain paths under a sandbox root, with a sensitive-file denylist."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Credential and key/DB material the agent must never read, write, list into, or
# search, even when it sits inside the sandbox root.
_DENIED_NAMES = {".env", ".netrc", "orchestrator.db", "orchestrator.db-wal", "orchestrator.db-shm"}
_DENIED_SUFFIXES = {".key", ".pem"}
_DENIED_DIR_PARTS = {".orchestrator"}


def is_sensitive_path(path: Path) -> bool:
    """True if *path* (already resolved) is a credential or secret-like target."""
    name = path.name.lower()
    if name in _DENIED_NAMES:
        return True
    if name.startswith(".env"):  # .env, .env.local, .env.prod, ...
        return True
    if path.suffix.lower() in _DENIED_SUFFIXES:
        return True
    if "credential" in name or "secret" in name:
        return True
    if {p.lower() for p in path.parts} & _DENIED_DIR_PARTS:
        return True
    return False


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
        if is_sensitive_path(candidate):
            raise ValueError(f"Access denied to sensitive path: {candidate}")
        return candidate

    def _ensure_under_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Path outside sandbox: {path}") from exc
