"""
Token counting and cost estimation.
Uses a simple word-based heuristic (no tiktoken dependency) for pre-call estimation.
Actual token counts come from the provider response.
"""
from __future__ import annotations

import re


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~0.75 words per token (GPT family average).
    Good enough for model selection; actual counts are recorded from provider.
    """
    words = len(re.findall(r"\S+", text))
    return max(1, int(words / 0.75))


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    cost_per_1m_input: float,
    cost_per_1m_output: float,
) -> float:
    """Return estimated cost in USD."""
    return (input_tokens * cost_per_1m_input + output_tokens * cost_per_1m_output) / 1_000_000
