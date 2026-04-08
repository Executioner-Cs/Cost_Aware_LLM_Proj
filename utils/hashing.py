"""Utility hashing – used for trace IDs, not cache keys."""
from __future__ import annotations
import hashlib


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
