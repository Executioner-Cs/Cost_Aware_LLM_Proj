"""Tests for core/cost_estimator.py"""
import pytest
from core.cost_estimator import estimate_tokens, estimate_cost


def test_estimate_tokens_basic():
    # "Hello world" = 2 words → ~2/0.75 ≈ 2
    result = estimate_tokens("Hello world")
    assert result >= 1


def test_estimate_tokens_longer():
    text = " ".join(["word"] * 75)
    result = estimate_tokens(text)
    assert 90 <= result <= 110  # ~100 tokens


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 1


def test_estimate_cost_zero():
    assert estimate_cost(0, 0, 1.0, 2.0) == 0.0


def test_estimate_cost_basic():
    # 1M input tokens at $3/M + 1M output at $15/M
    cost = estimate_cost(1_000_000, 1_000_000, 3.0, 15.0)
    assert abs(cost - 18.0) < 1e-9


def test_estimate_cost_small():
    # 100 input tokens at $0.25/M, 200 output at $1.25/M
    cost = estimate_cost(100, 200, 0.25, 1.25)
    expected = (100 * 0.25 + 200 * 1.25) / 1_000_000
    assert abs(cost - expected) < 1e-12
