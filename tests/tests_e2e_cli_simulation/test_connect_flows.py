from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.tests_e2e_cli_simulation.conftest import run_cli


class _DummyStatus:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyConsole:
    def status(self, _message):
        return _DummyStatus()


def _fake_account():
    a = MagicMock()
    a.id = "12345678-abcd"
    a.display_name = "test-user"
    return a


def test_connect_uses_cli_api_key_over_env(runner, env):
    env.set(OPENAI_API_KEY="sk-env")

    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console", _DummyConsole()):
            with patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc:
                with patch("cli.commands.connect.load_dotenv_once") as ld:
                    with patch("cli.commands.connect.get_provider_api_key") as gep:
                        with patch("cli.commands.connect.typer.prompt") as prompt:
                            r = run_cli(runner, ["connect", "openai", "--api-key", "sk-cli"])

    assert r.exit_code == 0
    assert "Connected" in r.stdout
    svc.assert_called_once()
    assert svc.call_args[0][1] == "openai"
    assert svc.call_args[0][2] == "sk-cli"
    ld.assert_not_called()
    gep.assert_not_called()
    prompt.assert_not_called()


def test_connect_uses_env_key_without_prompt(runner, env):
    env.set(OPENAI_API_KEY="sk-env")

    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console", _DummyConsole()):
            with patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc:
                with patch("cli.commands.connect.load_dotenv_once") as ld:
                    with patch("cli.commands.connect.get_provider_api_key", return_value="sk-env") as gep:
                        with patch("cli.commands.connect.typer.prompt") as prompt:
                            r = run_cli(runner, ["connect", "openai"])

    assert r.exit_code == 0
    assert "Connected" in r.stdout
    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-env"
    ld.assert_called_once()
    gep.assert_called_once()
    prompt.assert_not_called()


def test_connect_prompts_when_no_env_key(runner, env):
    env.unset("OPENAI_API_KEY")

    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console", _DummyConsole()):
            with patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc:
                with patch("cli.commands.connect.load_dotenv_once"):
                    with patch("cli.commands.connect.get_provider_api_key", return_value=None):
                        with patch("cli.commands.connect.typer.prompt", return_value="sk-prompt") as prompt:
                            r = run_cli(runner, ["connect", "openai"])

    assert r.exit_code == 0
    assert "Connected" in r.stdout
    assert svc.call_args[0][2] == "sk-prompt"
    prompt.assert_called_once()


def test_connect_empty_prompt_exits_1(runner, env):
    env.unset("OPENAI_API_KEY")

    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console", _DummyConsole()):
            with patch("cli.commands.connect.load_dotenv_once"):
                with patch("cli.commands.connect.get_provider_api_key", return_value=None):
                    with patch("cli.commands.connect.typer.prompt", return_value=""):
                        r = run_cli(runner, ["connect", "openai"])

    assert r.exit_code == 1
    assert "API key is required" in r.stdout


def test_connect_invalid_provider(runner):
    # No mocks needed; should fail fast on unsupported provider.
    r = run_cli(runner, ["connect", "not-a-provider", "--api-key", "x"])
    assert r.exit_code == 1
    assert "Unsupported provider" in r.stdout

