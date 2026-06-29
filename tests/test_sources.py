"""
OpenAI-compatible + Ollama sources through the ModelSource seam. All HTTP is
mocked; no real network calls. Cloud routing behavior is unchanged.
"""
from __future__ import annotations

import sys

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ConnectedAccount, ModelRegistry
from providers import ollama, openai_compatible
from providers.base import GenerateResult, ModelInfo
from providers.source import get_model_source, ModelSource


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"status {self.status_code}")


# --------------------------------------------------------------------------- #
# get_model_source dispatch
# --------------------------------------------------------------------------- #

def test_get_model_source_builds_non_cloud():
    s = get_model_source("ollama", source_type="ollama", base_url="http://x:11434")
    assert isinstance(s, ModelSource) and s.source_type == "ollama" and s.base_url == "http://x:11434"
    c = get_model_source("openai-compat", source_type="openai_compatible", base_url="http://x/v1")
    assert c.source_type == "openai_compatible"
    # cloud unchanged: still resolves the static registry source
    assert get_model_source("openai").source_type == "cloud"


def test_source_modules_are_httpx_only():
    # Fresh interpreter: importing the new sources must pull no SDK/ML/vector
    # libs (httpx is a base dependency). A subprocess avoids pollution from other
    # tests that legitimately import provider SDKs.
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    probe = (
        "import sys; import providers.ollama, providers.openai_compatible, providers.source; "
        "bad=[m for m in ('torch','sentence_transformers','qdrant_client','openai','anthropic','google') if m in sys.modules]; "
        "sys.exit('LOADED:'+','.join(bad) if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", probe], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout + result.stderr).strip()


# --------------------------------------------------------------------------- #
# Ollama
# --------------------------------------------------------------------------- #

def test_ollama_list_models(monkeypatch):
    def fake_get(url, **kwargs):
        assert url.endswith("/api/tags")
        return FakeResp({"models": [{"name": "llama3:8b", "details": {"context_length": 4096}}]})

    monkeypatch.setattr("httpx.get", fake_get)
    models = ollama.list_models("http://localhost:11434")
    assert len(models) == 1
    assert models[0].external_model_id == "llama3:8b"
    assert models[0].context_window == 4096
    assert models[0].cost_per_1m_input == 0.0  # local: free


def test_ollama_generate_via_source(monkeypatch):
    def fake_post(url, **kwargs):
        assert url.endswith("/api/chat")
        return FakeResp({"message": {"content": "hi"}, "prompt_eval_count": 5, "eval_count": 3})

    monkeypatch.setattr("httpx.post", fake_post)
    result = get_model_source("ollama", source_type="ollama", base_url="http://h:11434").generate("p", "llama3", "")
    assert isinstance(result, GenerateResult)
    assert result.response_text == "hi" and result.input_tokens == 5 and result.output_tokens == 3
    assert result.provider == "ollama"


def test_ollama_unreachable_raises(monkeypatch):
    def boom(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("httpx.get", boom)
    with pytest.raises(httpx.ConnectError):
        ollama.list_models("http://localhost:11434")


# --------------------------------------------------------------------------- #
# OpenAI-compatible
# --------------------------------------------------------------------------- #

def test_openai_compatible_list_models_sends_auth(monkeypatch):
    def fake_get(url, headers=None, **kwargs):
        assert url.endswith("/models")
        assert headers == {"Authorization": "Bearer k"}
        return FakeResp({"data": [{"id": "my-model"}]})

    monkeypatch.setattr("httpx.get", fake_get)
    assert openai_compatible.list_models("http://host/v1", "k")[0].external_model_id == "my-model"


def test_openai_compatible_no_key_no_auth_header(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, **kwargs):
        seen["headers"] = headers
        return FakeResp({"data": []})

    monkeypatch.setattr("httpx.get", fake_get)
    openai_compatible.list_models("http://host/v1", None)
    assert seen["headers"] == {}


def test_openai_compatible_generate(monkeypatch):
    def fake_post(url, headers=None, **kwargs):
        assert url.endswith("/chat/completions")
        return FakeResp({
            "choices": [{"message": {"content": "yo"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        })

    monkeypatch.setattr("httpx.post", fake_post)
    result = openai_compatible.generate("http://host/v1", "p", "my-model", "k")
    assert result.response_text == "yo"
    assert result.input_tokens == 2 and result.output_tokens == 1
    assert result.provider == "openai_compatible"


# --------------------------------------------------------------------------- #
# connect_service registers a source (no network: discovery is stubbed)
# --------------------------------------------------------------------------- #

def test_connect_registers_keyless_ollama_source(monkeypatch, tmp_path):
    from services import connect_service

    engine = create_engine(f"sqlite:///{tmp_path / 's.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        monkeypatch.setattr(
            "providers.source.ModelSource.list_models",
            lambda self, api_key: [ModelInfo(
                external_model_id="llama3", display_name="llama3", tier="balanced",
                context_window=8192, cost_per_1m_input=0.0, cost_per_1m_output=0.0,
            )],
        )
        account = connect_service.connect(session, "ollama", "")  # keyless, default base_url

        assert account.source_type == "ollama"
        assert account.base_url  # defaulted to the local Ollama URL
        assert account.encrypted_token is None  # keyless
        rows = session.query(ModelRegistry).filter_by(provider="ollama").all()
        assert len(rows) == 1 and rows[0].external_model_id == "llama3"
    finally:
        session.close()
