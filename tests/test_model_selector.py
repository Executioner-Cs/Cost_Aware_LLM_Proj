"""Tests for core/model_selector.py"""
import pytest
from core.model_selector import select
from db.models import ModelRegistry


def _make_model(
    id: str,
    provider: str,
    external_id: str,
    tier: str,
    cost_in: float,
    cost_out: float,
    ctx: int = 128_000,
    json: bool = True,
    tools: bool = True,
    vision: bool = False,
) -> ModelRegistry:
    m = ModelRegistry()
    m.id = id
    m.provider = provider
    m.external_model_id = external_id
    m.tier = tier
    m.context_window = ctx
    m.cost_per_1m_input = cost_in
    m.cost_per_1m_output = cost_out
    m.supports_json = int(json)
    m.supports_tools = int(tools)
    m.supports_vision = int(vision)
    m.enabled = 1
    return m


MODELS = [
    _make_model("1", "openai", "gpt-4o-mini", "small", 0.15, 0.60),
    _make_model("2", "openai", "gpt-4o", "balanced", 2.50, 10.00),
    _make_model("3", "anthropic", "claude-haiku", "small", 0.25, 1.25),
    _make_model("4", "anthropic", "claude-sonnet", "balanced", 3.00, 15.00),
    _make_model("5", "anthropic", "claude-opus", "large", 15.00, 75.00),
]


def test_cheapest_for_simple():
    m = select(MODELS, "simple", "balanced")
    # cheapest enabled model should be gpt-4o-mini (0.15+0.60=0.75)
    assert m is not None
    assert m.external_model_id == "gpt-4o-mini"


def test_best_quality_selects_large():
    m = select(MODELS, "simple", "best")
    assert m is not None
    assert m.tier == "large"


def test_cheap_quality_selects_small():
    m = select(MODELS, "simple", "cheap")
    assert m is not None
    assert m.tier == "small"


def test_json_extract_requires_json_cap():
    no_json_models = [_make_model("x", "p", "m", "small", 0.01, 0.01, json=False)]
    m = select(no_json_models, "json_extract", "balanced")
    assert m is None


def test_vision_requires_vision_cap():
    m = select(MODELS, "vision", "balanced")
    # none of MODELS have vision=True except if we add one
    assert m is None  # no vision-capable models in base set


def test_token_limit_excluded():
    # model with tiny context should be excluded
    tiny = _make_model("tiny", "x", "tiny-model", "small", 0.01, 0.01, ctx=100)
    m = select([tiny], "simple", "balanced", input_tokens=200)
    assert m is None


def test_disabled_model_excluded():
    disabled = _make_model("d", "x", "disabled", "small", 0.01, 0.01)
    disabled.enabled = 0
    m = select([disabled], "simple", "balanced")
    assert m is None
