"""Environment helpers (including optional .env loading)."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Optional

_PROVIDER_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^sk-\.\.\.$"),
    re.compile(r"^sk-ant-\.\.\.$"),
    re.compile(r"^gsk_\.\.\.$"),
    re.compile(r"^your[_-]?(api[_-]?)?key", re.IGNORECASE),
    re.compile(r"^<.+>$"),
    re.compile(r"^CHANGE[_-]?ME", re.IGNORECASE),
    re.compile(r"^xxx+$", re.IGNORECASE),
    re.compile(r"^TODO", re.IGNORECASE),
    re.compile(r"^REPLACE", re.IGNORECASE),
    re.compile(r"^\.\.\.$"),
)


@lru_cache(maxsize=1)
def load_dotenv_once() -> None:
    """
    Load a repo-root `.env` file once per process.

    This is a convenience for local development. If no `.env` exists, this is a no-op.
    """
    try:
        from dotenv import find_dotenv, load_dotenv

        path = find_dotenv(usecwd=True)
        if path:
            load_dotenv(path, override=False)
    except Exception:
        return


def is_placeholder_key(value: str) -> bool:
    """Return True if value looks like a template placeholder rather than a real key."""
    v = (value or "").strip()
    if not v:
        return True
    if len(v) < 8:
        return True
    return any(p.search(v) for p in _PLACEHOLDER_PATTERNS)


def get_provider_env_var(provider: str) -> Optional[str]:
    """Return the environment variable name for a provider, or None."""
    return _PROVIDER_ENV_VARS.get((provider or "").strip().lower())


def get_provider_api_key(provider: str) -> Optional[str]:
    """
    Return provider API key from environment variables, if present and not a placeholder.

    Returns None if the env var is unset, empty, or looks like a placeholder.
    """
    env_var = get_provider_env_var(provider)
    if not env_var:
        return None
    v = os.environ.get(env_var)
    if not v:
        return None
    v = v.strip()
    if not v or is_placeholder_key(v):
        return None
    return v

