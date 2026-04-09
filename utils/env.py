"""Environment helpers (including optional .env loading)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


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
        # Never fail CLI startup due to dotenv issues.
        return


def get_provider_api_key(provider: str) -> Optional[str]:
    """
    Return provider API key from environment variables, if present.

    Providers map to env var names:
      - anthropic -> ANTHROPIC_API_KEY
      - openai    -> OPENAI_API_KEY
      - groq      -> GROQ_API_KEY
      - gemini    -> GEMINI_API_KEY
    """
    key = (provider or "").strip().lower()
    env_var = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }.get(key)
    if not env_var:
        return None
    v = os.environ.get(env_var)
    if not v:
        return None
    v = v.strip()
    return v or None

