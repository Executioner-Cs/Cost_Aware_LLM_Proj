"""Fernet-based encryption for API tokens stored in SQLite."""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet


_KEY_FILE_ENV = "ORCHESTRATOR_KEY_FILE"
_DEFAULT_KEY_FILE = Path.home() / ".orchestrator" / ".key"


def _key_path() -> Path:
    return Path(os.environ.get(_KEY_FILE_ENV, str(_DEFAULT_KEY_FILE)))


def ensure_key() -> bytes:
    """Load existing Fernet key or generate and persist a new one."""
    kp = _key_path()
    if kp.exists():
        return kp.read_bytes().strip()
    key = Fernet.generate_key()
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_bytes(key)
    kp.chmod(0o600)
    return key


def get_fernet() -> Fernet:
    return Fernet(ensure_key())


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
