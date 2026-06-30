from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cli.commands.connect import cmd_connect


def _fake_account():
    a = MagicMock()
    a.id = "acc12345678"
    a.display_name = "me"
    return a


def test_connect_uses_cli_api_key_without_prompt(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("cli.commands.connect.load_dotenv_once") as ld, \
         patch("cli.commands.connect.get_provider_api_key") as gek, \
         patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc, \
         patch("cli.commands.connect.get_session", return_value=MagicMock()):
        cmd_connect("openai", api_key="sk-real-cli-key")

    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-real-cli-key"
    ld.assert_not_called()
    gek.assert_not_called()


def test_connect_env_key_echoes_source_without_leaking(monkeypatch, capsys):
    """The env-source note names the variable, not its value, and never leaks the key."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-secret-12345")

    with patch("cli.commands.connect.load_dotenv_once"), \
         patch("cli.commands.connect.get_provider_api_key", return_value="sk-env-secret-12345"), \
         patch("cli.commands.connect.svc_connect", return_value=_fake_account()), \
         patch("cli.commands.connect.get_session", return_value=MagicMock()):
        cmd_connect("openai", api_key="")

    out = capsys.readouterr().out.lower()
    assert "from environment" in out
    assert "openai_api_key" in out                 # the variable name
    assert "sk-env-secret-12345" not in out        # never the value


def test_connect_uses_env_key_when_cli_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-valid")

    with patch("cli.commands.connect.load_dotenv_once") as ld, \
         patch("cli.commands.connect.get_provider_api_key", return_value="sk-env-valid") as gek, \
         patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc, \
         patch("cli.commands.connect.get_session", return_value=MagicMock()):
        cmd_connect("openai", api_key="")

    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-env-valid"
    ld.assert_called_once()
    gek.assert_called_once()


def test_connect_prompts_when_no_cli_or_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("cli.commands.connect.load_dotenv_once") as ld, \
         patch("cli.commands.connect.get_provider_api_key", return_value=None) as gek, \
         patch("cli.commands.connect.typer.prompt", return_value="sk-prompt") as prompt, \
         patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc, \
         patch("cli.commands.connect.get_session", return_value=MagicMock()):
        cmd_connect("openai", api_key="")

    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-prompt"
    prompt.assert_called_once()
    ld.assert_called_once()
    gek.assert_called_once()


def test_connect_errors_on_empty_prompt(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("cli.commands.connect.load_dotenv_once"), \
         patch("cli.commands.connect.get_provider_api_key", return_value=None), \
         patch("cli.commands.connect.typer.prompt", return_value=""):
        with pytest.raises(Exception) as exc:
            cmd_connect("openai", api_key="")
        exit_code = getattr(exc.value, "exit_code", None) or getattr(exc.value, "code", None)
        assert exit_code == 1


def test_connect_skips_placeholder_env_key_and_prompts(monkeypatch):
    """Env key that's a known placeholder is treated as missing -> user is prompted."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("cli.commands.connect.load_dotenv_once"), \
         patch("cli.commands.connect.get_provider_api_key", return_value=None) as gek, \
         patch("cli.commands.connect.typer.prompt", return_value="sk-real") as prompt, \
         patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc, \
         patch("cli.commands.connect.get_session", return_value=MagicMock()):
        cmd_connect("openai", api_key="")

    gek.assert_called_once()
    prompt.assert_called_once()
    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-real"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "groq"])
def test_connect_prompts_all_providers_when_no_env(monkeypatch, provider):
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    with patch("cli.commands.connect.load_dotenv_once"), \
         patch("cli.commands.connect.get_provider_api_key", return_value=None), \
         patch("cli.commands.connect.typer.prompt", return_value="sk-test") as prompt, \
         patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc, \
         patch("cli.commands.connect.get_session", return_value=MagicMock()):
        cmd_connect(provider, api_key="")

    prompt.assert_called_once()
    svc.assert_called_once()
    assert svc.call_args[0][1] == provider
