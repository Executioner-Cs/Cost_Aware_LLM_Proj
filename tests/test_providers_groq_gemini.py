"""Tests for Groq and Gemini connectors (mocked HTTP / SDK)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from providers.gemini.connector import GeminiConnector
from providers.groq.connector import GroqConnector


def test_groq_validate_key_success():
    with patch("providers.groq.connector.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert GroqConnector("k").validate_key() is True
        mock_get.assert_called_once()


def test_groq_validate_key_failure():
    with patch("providers.groq.connector.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        assert GroqConnector("bad").validate_key() is False


def test_groq_list_models_non_empty():
    models = GroqConnector("k").list_models()
    assert len(models) >= 1
    assert models[0].external_model_id


def test_gemini_validate_key_success():
    with patch("providers.gemini.connector.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert GeminiConnector("k").validate_key() is True


def test_gemini_validate_key_failure():
    with patch("providers.gemini.connector.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=403)
        assert GeminiConnector("bad").validate_key() is False


def test_gemini_list_models_non_empty():
    models = GeminiConnector("k").list_models()
    assert any(m.external_model_id.startswith("gemini") for m in models)


def test_connect_service_includes_providers():
    from services import connect_service

    assert "groq" in connect_service._PROVIDER_CONNECTOR_MAP
    assert "gemini" in connect_service._PROVIDER_CONNECTOR_MAP
