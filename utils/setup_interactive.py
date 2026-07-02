"""Interactive setup helpers (provider picker + safe fallbacks)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from rich.console import Console

PROVIDER_CHOICES: list[tuple[str, str]] = [
    ("__skip__", "Skip for now"),
    ("openai", "openai"),
    ("anthropic", "anthropic"),
    ("gemini", "google gemini"),
    ("groq", "groq"),
]


@dataclass(frozen=True)
class InteractiveStatus:
    can_prompt: bool
    reason_code: str
    message: str


def get_interactive_status(console: Console) -> InteractiveStatus:
    """Assess if interactive picker UX can run, with a user-facing reason."""
    stdin_is_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    stdout_is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    if not stdin_is_tty or not stdout_is_tty or not console.is_terminal:
        return InteractiveStatus(
            can_prompt=False,
            reason_code="not_tty",
            message=(
                "Interactive provider picker unavailable because this session is not a full TTY. "
                "Run in a standard terminal session for arrow-key selection."
            ),
        )
    try:
        import questionary  # noqa: F401
    except Exception:
        return InteractiveStatus(
            can_prompt=False,
            reason_code="missing_dependency",
            message=(
                "Interactive provider picker unavailable because 'questionary' is not installed. "
                'Install the tui extra: pip install "orchestrator-cli[tui]".'
            ),
        )
    return InteractiveStatus(
        can_prompt=True,
        reason_code="ok",
        message="Interactive picker available.",
    )


def can_prompt_interactive(console: Console) -> bool:
    """Return True when we can safely use interactive picker/prompt UX."""
    return get_interactive_status(console).can_prompt


def pick_provider(console: Console) -> Optional[str]:
    """
    Show arrow-key provider picker and return provider id or None on cancel/failure.
    """
    if not can_prompt_interactive(console):
        return None

    try:
        import questionary

        result = questionary.select(
            "Select provider to connect now",
            choices=[
                questionary.Choice(title=label, value=provider)
                for provider, label in PROVIDER_CHOICES
            ],
            qmark=">",
            pointer="❯",
        ).ask()
        if not result:
            return None
        if str(result) == "__skip__":
            return None
        return str(result)
    except KeyboardInterrupt:
        return None
    except Exception:
        return None

