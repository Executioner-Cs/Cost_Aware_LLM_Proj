"""
Task type classifier.
Uses keyword + heuristic rules (no LLM call).
Returns: 'simple' | 'json_extract' | 'reasoning' | 'vision' | 'tools'
"""
from __future__ import annotations

import re

_JSON_PATTERNS = [
    r"\bjson\b",
    r"\bextract\b.{0,30}\b(field|fields|value|values|key|keys)\b",
    r"\bparse\b.{0,30}\bjson\b",
    r"\bstructured output\b",
    r"\bline item",
    r"\bcsv\b",
    r"\bas a dict\b",
]

_REASONING_PATTERNS = [
    r"\breason\b",
    r"\banalyse\b",
    r"\banalyze\b",
    r"\bexplain\b.{0,40}\bwhy\b",
    r"\btradeoff\b",
    r"\btrade-off\b",
    r"\bpros and cons\b",
    r"\bstep by step\b",
    r"\bthink through\b",
    r"\bdebug\b",
    r"\bdiagnose\b",
    r"\bcritique\b",
    r"\bevaluate\b",
    r"\bcompare\b.{0,30}\bwith\b",
]

_VISION_PATTERNS = [
    r"\bimage\b",
    r"\bphoto\b",
    r"\bscreenshot\b",
    r"\bpicture\b",
    r"\bdiagram\b",
    r"\bvisual\b",
    r"\bdescribe.{0,20}(this|the)\b",
]

_TOOLS_PATTERNS = [
    r"\bcall.{0,20}\bfunction\b",
    r"\btool.{0,20}\bcall\b",
    r"\buse.{0,20}(api|tool|function)\b",
    r"\bexecute\b",
]


def classify(prompt: str) -> str:
    """Return one of: 'simple', 'json_extract', 'reasoning', 'vision', 'tools'."""
    lower = prompt.lower()

    if _matches_any(lower, _VISION_PATTERNS):
        return "vision"
    if _matches_any(lower, _TOOLS_PATTERNS):
        return "tools"
    if _matches_any(lower, _JSON_PATTERNS):
        return "json_extract"
    if _matches_any(lower, _REASONING_PATTERNS):
        return "reasoning"
    return "simple"


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)
