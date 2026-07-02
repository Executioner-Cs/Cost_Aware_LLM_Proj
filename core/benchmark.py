"""Deterministic benchmark grading.

Exact/contains/JSON-validity scoring only. No LLM-as-judge in this version: a
judge would be a non-deterministic, separately-labeled experiment, not a default
scoring path. Pure functions, no I/O.
"""
from __future__ import annotations

import json

GRADERS = ("exact", "contains", "json_valid")


def grade(grader: str, response: str, expected: str | None) -> bool:
    """Return True if *response* passes the given deterministic grader."""
    text = (response or "").strip()
    if grader == "exact":
        return text == (expected or "").strip()
    if grader == "contains":
        if not expected:
            return bool(text)
        return expected.strip().lower() in text.lower()
    if grader == "json_valid":
        try:
            json.loads(text)
            return True
        except (ValueError, TypeError):
            return False
    raise ValueError(f"unknown grader '{grader}' (expected one of {GRADERS})")
