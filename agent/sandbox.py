"""Resolve and constrain paths under a sandbox root, with a sensitive-file denylist."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Credential and key/DB material the agent must never read, write, list into, or
# search, even when it sits inside the sandbox root.
_DENIED_NAMES = {
    ".env", ".netrc", "orchestrator.db", "orchestrator.db-wal", "orchestrator.db-shm",
    # Private-key and password files (config files like .npmrc are NOT here: they
    # are commonly legitimate project files, and secret values they may hold are
    # caught by the credential/secret name rules and by log redaction).
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".git-credentials", ".pgpass", ".htpasswd",
}
_DENIED_SUFFIXES = {".key", ".pem", ".pfx", ".p12", ".keystore", ".jks"}
# Credential directories. Matched only on components BELOW the sandbox root (see
# is_sensitive_path), so a sandbox_root nested under one of these does not deny
# every file. ".docker" is intentionally absent: project-local .docker/ dirs
# (Dockerfiles, compose fragments) are common and legitimate.
_DENIED_DIR_PARTS = {".orchestrator", ".ssh", ".aws", ".gnupg", ".kube", ".gcloud", ".azure"}


def is_sensitive_path(path: Path, root: Path | None = None) -> bool:
    """True if *path* (already resolved) is a credential or secret-like target.

    When *root* is given, the credential-directory denylist is matched only on the
    components below root (what the agent navigated into), not the root's own
    ancestors, so a sandbox root nested under e.g. ``.gnupg`` does not deny every
    file. Name/suffix/substring rules always apply regardless of root."""
    name = path.name.lower()
    if name in _DENIED_NAMES:
        return True
    if name.startswith(".env"):  # .env, .env.local, .env.prod, ...
        return True
    if path.suffix.lower() in _DENIED_SUFFIXES:
        return True
    if "credential" in name or "secret" in name:
        return True
    parts = path.parts
    if root is not None:
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            parts = path.parts
    if {p.lower() for p in parts} & _DENIED_DIR_PARTS:
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
        # .resolve() collapses ".." and follows symlinks, so the confinement check
        # below runs against the real target: a symlink inside the sandbox that
        # points outside is rejected, and ".." traversal cannot escape the root.
        if raw.is_absolute():
            candidate = raw.resolve()
        else:
            candidate = (self.root / raw).resolve()
        self._ensure_under_root(candidate)
        if is_sensitive_path(candidate, self.root):
            raise ValueError(f"Access denied to sensitive path: {candidate}")
        return candidate

    def _ensure_under_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Path outside sandbox: {path}") from exc
