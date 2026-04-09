from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services import init_service
from utils.setup_interactive import InteractiveStatus


def _stub_interactive_ok(monkeypatch):
    monkeypatch.setattr(
        init_service,
        "get_interactive_status",
        lambda _console: InteractiveStatus(can_prompt=True, reason_code="ok", message="ok"),
    )
    monkeypatch.setattr(init_service, "render_init_handoff_panel", lambda: None)


def _stub_connect_success(monkeypatch, calls):
    fake_account = MagicMock()
    fake_account.id = "abc123456"
    fake_account.display_name = "me"
    monkeypatch.setattr(init_service, "get_session", lambda: MagicMock())

    def _connect(session, provider, key):
        calls.setdefault("connect_calls", []).append((provider, key))
        return fake_account

    monkeypatch.setattr(init_service, "svc_connect", _connect)


# --- Happy path: env key exists and works ---

def test_env_key_connects_directly(monkeypatch):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: "openai")
    monkeypatch.setattr(init_service, "get_provider_api_key", lambda _p: "sk-real-key")
    monkeypatch.setattr(init_service, "_prompt_api_key", lambda _p: calls.setdefault("prompted", True) or "")
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda _r: calls.setdefault("fallback", True))
    _stub_connect_success(monkeypatch, calls)

    init_service._run_post_init_connect_handoff()

    assert calls["connect_calls"] == [("openai", "sk-real-key")]
    assert "prompted" not in calls
    assert "fallback" not in calls


# --- Happy path: no env key, user prompted, connects ---

def test_no_env_key_prompts_then_connects(monkeypatch):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: "anthropic")
    monkeypatch.setattr(init_service, "get_provider_api_key", lambda _p: None)
    monkeypatch.setattr(init_service, "_prompt_api_key", lambda _p: "sk-prompted")
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda _r: calls.setdefault("fallback", True))
    _stub_connect_success(monkeypatch, calls)

    init_service._run_post_init_connect_handoff()

    assert calls["connect_calls"] == [("anthropic", "sk-prompted")]
    assert "fallback" not in calls


# --- Env key fails auth -> retry with prompt succeeds ---

def test_env_key_fails_retry_prompt_succeeds(monkeypatch):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: "openai")
    monkeypatch.setattr(init_service, "get_provider_api_key", lambda _p: "sk-stale")
    monkeypatch.setattr(init_service, "_prompt_api_key", lambda _p: "sk-fresh")
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda _r: calls.setdefault("fallback", True))

    fake_account = MagicMock()
    fake_account.id = "acc987654"
    fake_account.display_name = "user"
    monkeypatch.setattr(init_service, "get_session", lambda: MagicMock())

    def _connect(session, provider, key):
        calls.setdefault("connect_calls", []).append((provider, key))
        if key == "sk-stale":
            raise ValueError("API key validation failed for provider 'openai'")
        return fake_account

    monkeypatch.setattr(init_service, "svc_connect", _connect)

    init_service._run_post_init_connect_handoff()

    assert calls["connect_calls"] == [("openai", "sk-stale"), ("openai", "sk-fresh")]
    assert "fallback" not in calls


# --- Env key fails, retry prompt also fails -> fallback ---

def test_env_key_fails_retry_fails_shows_fallback(monkeypatch):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: "gemini")
    monkeypatch.setattr(init_service, "get_provider_api_key", lambda _p: "bad-env")
    prompt_values = iter(["bad-prompt", ""])
    monkeypatch.setattr(init_service, "_prompt_api_key", lambda _p: next(prompt_values))
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda _r: calls.setdefault("fallback_reason", _r))

    monkeypatch.setattr(init_service, "get_session", lambda: MagicMock())

    def _connect(session, provider, key):
        raise ValueError("API key validation failed")

    monkeypatch.setattr(init_service, "svc_connect", _connect)

    init_service._run_post_init_connect_handoff()

    assert "fallback_reason" in calls
    assert "No API key supplied." == calls["fallback_reason"]


# --- No env key, user enters empty prompt -> fallback ---

def test_no_env_empty_prompt_shows_fallback(monkeypatch):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: "groq")
    monkeypatch.setattr(init_service, "get_provider_api_key", lambda _p: None)
    monkeypatch.setattr(init_service, "_prompt_api_key", lambda _p: "")
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda _r: calls.setdefault("fallback_reason", _r))

    init_service._run_post_init_connect_handoff()

    assert "No API key" in calls["fallback_reason"]


# --- Picker cancel -> fallback ---

def test_picker_cancel_prints_fallback(monkeypatch):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: None)
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda r: calls.setdefault("reason", r))

    init_service._run_post_init_connect_handoff()

    assert "No provider selected" in calls["reason"]


# --- Non-interactive terminal -> fallback, no picker ---

def test_noninteractive_skips_picker(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(
        init_service,
        "get_interactive_status",
        lambda _c: InteractiveStatus(can_prompt=False, reason_code="not_tty", message="TTY missing"),
    )
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: calls.setdefault("picker_called", True))
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda r: calls.setdefault("reason", r))
    monkeypatch.setattr(init_service, "render_init_handoff_panel", lambda: None)

    init_service._run_post_init_connect_handoff()

    assert "picker_called" not in calls
    assert "TTY missing" in calls["reason"]


# --- Parameterized: all providers get prompted when no env key ---

@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "groq"])
def test_all_providers_prompt_when_no_env(monkeypatch, provider):
    calls: dict = {}
    _stub_interactive_ok(monkeypatch)
    monkeypatch.setattr(init_service, "pick_provider", lambda _c: provider)
    monkeypatch.setattr(init_service, "get_provider_api_key", lambda _p: None)
    monkeypatch.setattr(init_service, "_prompt_api_key", lambda _p: "sk-test-key")
    monkeypatch.setattr(init_service, "_print_fallback_connect_commands", lambda _r: calls.setdefault("fallback", True))
    _stub_connect_success(monkeypatch, calls)

    init_service._run_post_init_connect_handoff()

    assert calls["connect_calls"] == [(provider, "sk-test-key")]
    assert "fallback" not in calls
