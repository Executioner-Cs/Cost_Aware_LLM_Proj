"""Discovery fallback must be honest: when model discovery fails or is
unavailable, the connector still returns its built-in catalog (backward
compatible) but warns the user instead of falling back silently. All network is
mocked; no real calls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from providers.openai.connector import OpenAIConnector
from providers.anthropic.connector import AnthropicConnector


def test_openai_warns_and_falls_back_on_discovery_exception():
    c = OpenAIConnector("sk-test")
    with patch("providers.openai.connector.httpx.get", side_effect=Exception("network down")), \
         patch("providers.openai.connector.print_warning") as warn:
        models = c.list_models()
    assert len(models) > 0          # fallback catalog still returned
    assert warn.called              # but the fallback is now visible


def test_openai_warns_on_non_200():
    resp = MagicMock(status_code=401)
    c = OpenAIConnector("sk-test")
    with patch("providers.openai.connector.httpx.get", return_value=resp), \
         patch("providers.openai.connector.print_warning") as warn:
        models = c.list_models()
    assert len(models) > 0
    assert warn.called


def test_openai_no_warning_on_successful_discovery():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"data": [{"id": "gpt-4o-mini"}]}
    c = OpenAIConnector("sk-test")
    with patch("providers.openai.connector.httpx.get", return_value=resp), \
         patch("providers.openai.connector.print_warning") as warn:
        models = c.list_models()
    assert any(m.external_model_id == "gpt-4o-mini" for m in models)
    assert not warn.called          # discovery worked, no fallback, no noise


def test_anthropic_warns_and_falls_back_on_discovery_exception():
    c = AnthropicConnector("sk-ant-test")
    with patch("providers.anthropic.connector.httpx.get", side_effect=Exception("boom")), \
         patch("providers.anthropic.connector.print_warning") as warn:
        models = c.list_models()
    assert len(models) > 0
    assert warn.called
