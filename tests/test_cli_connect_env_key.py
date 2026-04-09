from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from cli.commands.connect import cmd_connect


def test_connect_uses_cli_api_key_without_prompt(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    fake_account = MagicMock()
    fake_account.id = "acc"
    fake_account.display_name = "me"

    with patch("cli.commands.connect.load_dotenv_once") as ld:
        with patch("cli.commands.connect.get_provider_api_key") as gek:
            with patch("cli.commands.connect.typer.prompt") as prompt:
                with patch("cli.commands.connect.svc_connect", return_value=fake_account) as svc:
                    with patch("cli.commands.connect.get_session") as gs:
                        gs.return_value = MagicMock()
                        cmd_connect("openai", api_key="sk-cli")

    svc.assert_called_once()
    args = svc.call_args[0]
    assert args[1] == "openai"
    assert args[2] == "sk-cli"
    prompt.assert_not_called()
    ld.assert_not_called()
    gek.assert_not_called()


def test_connect_uses_env_key_when_cli_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

    fake_account = MagicMock()
    fake_account.id = "acc"
    fake_account.display_name = "me"

    with patch("cli.commands.connect.load_dotenv_once") as ld:
        with patch("cli.commands.connect.get_provider_api_key", return_value="sk-env") as gek:
            with patch("cli.commands.connect.typer.prompt") as prompt:
                with patch("cli.commands.connect.svc_connect", return_value=fake_account) as svc:
                    with patch("cli.commands.connect.get_session") as gs:
                        gs.return_value = MagicMock()
                        cmd_connect("openai", api_key="")

    svc.assert_called_once()
    args = svc.call_args[0]
    assert args[2] == "sk-env"
    prompt.assert_not_called()
    ld.assert_called_once()
    gek.assert_called_once()


def test_connect_prompts_when_no_cli_or_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    fake_account = MagicMock()
    fake_account.id = "acc"
    fake_account.display_name = "me"

    with patch("cli.commands.connect.load_dotenv_once") as ld:
        with patch("cli.commands.connect.get_provider_api_key", return_value=None) as gek:
            with patch("cli.commands.connect.typer.prompt", return_value="sk-prompt") as prompt:
                with patch("cli.commands.connect.svc_connect", return_value=fake_account) as svc:
                    with patch("cli.commands.connect.get_session") as gs:
                        gs.return_value = MagicMock()
                        cmd_connect("openai", api_key="")

    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-prompt"
    prompt.assert_called_once()
    ld.assert_called_once()
    gek.assert_called_once()


def test_connect_errors_on_empty_prompt(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("cli.commands.connect.load_dotenv_once"):
        with patch("cli.commands.connect.get_provider_api_key", return_value=None):
            with patch("cli.commands.connect.typer.prompt", return_value=""):
                # cmd_connect prints the ValueError and raises typer.Exit(1)
                with pytest.raises(Exception) as exc:
                    cmd_connect("openai", api_key="")
                assert exc.value.exit_code == 1

