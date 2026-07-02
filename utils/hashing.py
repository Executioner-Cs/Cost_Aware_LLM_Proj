"""Utility hashing: used for exact cache keys (core/cache.py) and trace IDs."""
from __future__ import annotations
import hashlib


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
