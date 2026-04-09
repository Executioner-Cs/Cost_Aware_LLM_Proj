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


def test_env_var_wins_over_dotenv_loader(runner, env):
    # We simulate dotenv loading would happen, but env var is already present.
    env.set(OPENAI_API_KEY="sk-os-env")

    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console", _DummyConsole()):
            with patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc:
                with patch("cli.commands.connect.load_dotenv_once") as ld:
                    # get_provider_api_key reads os.environ, so don't override it.
                    with patch("cli.commands.connect.typer.prompt") as prompt:
                        r = run_cli(runner, ["connect", "openai"])

    assert r.exit_code == 0
    assert "Connected" in r.stdout
    svc.assert_called_once()
    assert svc.call_args[0][2] == "sk-os-env"
    ld.assert_called_once()
    prompt.assert_not_called()


def test_whitespace_only_key_treated_as_missing(runner, env):
    env.set(OPENAI_API_KEY="   ")

    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console", _DummyConsole()):
            with patch("cli.commands.connect.svc_connect", return_value=_fake_account()) as svc:
                with patch("cli.commands.connect.load_dotenv_once"):
                    with patch("cli.commands.connect.typer.prompt", return_value="sk-prompt") as prompt:
                        r = run_cli(runner, ["connect", "openai"])

    assert r.exit_code == 0
    assert svc.call_args[0][2] == "sk-prompt"
    prompt.assert_called_once()

