from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils import setup_interactive
from utils.env import get_provider_api_key, is_placeholder_key


def test_get_interactive_status_not_tty(monkeypatch):
    monkeypatch.setattr(setup_interactive.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(setup_interactive.sys, "stdout", SimpleNamespace(isatty=lambda: False))

    status = setup_interactive.get_interactive_status(SimpleNamespace(is_terminal=False))

    assert status.can_prompt is False
    assert status.reason_code == "not_tty"
    assert "not a full TTY" in status.message


def test_get_interactive_status_missing_dependency(monkeypatch):
    monkeypatch.setattr(setup_interactive.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup_interactive.sys, "stdout", SimpleNamespace(isatty=lambda: True))

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "questionary":
            raise ModuleNotFoundError("questionary")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    status = setup_interactive.get_interactive_status(SimpleNamespace(is_terminal=True))

    assert status.can_prompt is False
    assert status.reason_code == "missing_dependency"
    assert 'orchestrator-cli[tui]' in status.message


def test_pick_provider_skip_option_returns_none(monkeypatch):
    monkeypatch.setattr(setup_interactive, "can_prompt_interactive", lambda _console: True)

    class _FakeQuestionary:
        class Choice:
            def __init__(self, title, value):
                self.title = title
                self.value = value

        @staticmethod
        def select(*args, **kwargs):
            class _Prompt:
                @staticmethod
                def ask():
                    return "__skip__"

            return _Prompt()

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "questionary":
            return _FakeQuestionary
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    selected = setup_interactive.pick_provider(SimpleNamespace(is_terminal=True))
    assert selected is None


# --- Placeholder detection tests ---

@pytest.mark.parametrize("value", [
    "sk-...",
    "sk-ant-...",
    "gsk_...",
    "your-key-here",
    "your_api_key",
    "<your-openai-key>",
    "CHANGEME",
    "CHANGE-ME",
    "xxx",
    "xxxxxxxx",
    "TODO",
    "REPLACE",
    "...",
    "",
    "   ",
    "short",
])
def test_placeholder_key_detected(value):
    assert is_placeholder_key(value) is True


@pytest.mark.parametrize("value", [
    "sk-proj-abc123456789xyzABCDEF",
    "sk-ant-api03-realkey1234567890",
    "gsk_realTokenValue12345678",
    "AIzaSyC-realGeminiKey12345",
])
def test_real_key_not_detected_as_placeholder(value):
    assert is_placeholder_key(value) is False


def test_get_provider_api_key_returns_none_for_placeholder(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-...")
    assert get_provider_api_key("openai") is None


def test_get_provider_api_key_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_provider_api_key("openai") is None


def test_get_provider_api_key_returns_real_value(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-abc123456789xyzABCDEF")
    assert get_provider_api_key("openai") == "sk-proj-abc123456789xyzABCDEF"

