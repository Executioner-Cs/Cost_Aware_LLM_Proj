"""Output validation after provider call."""
from __future__ import annotations

import json


class ValidationError(Exception):
    pass


def validate(response_text: str, task_type: str) -> None:
    """
    Raises ValidationError on failure.
    - All tasks: non-empty response.
    - json_extract: must be valid JSON.
    """
    if not response_text or not response_text.strip():
        raise ValidationError("Empty response from provider")

    if task_type == "json_extract":
        # Be lenient: strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # remove first and last fence lines
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Response is not valid JSON: {exc}") from exc
