from __future__ import annotations

from unittest.mock import MagicMock, patch

import click

from tests.tests_e2e_cli_simulation.conftest import run_cli


def test_global_verbose_flag_rejected_until_implemented(runner):
    r = run_cli(runner, ["-v"])
    assert r.exit_code != 0
    assert "No such option" in (r.stdout + r.stderr)


def test_connect_non_interactive_prompt_abort(runner):
    # Simulate CI/non-interactive: prompt raises Abort.
    with patch("cli.commands.connect.get_session", return_value=MagicMock()):
        with patch("cli.commands.connect.console") as _c:
            with patch("cli.commands.connect.load_dotenv_once"):
                with patch("cli.commands.connect.get_provider_api_key", return_value=None):
                    with patch("cli.commands.connect.typer.prompt", side_effect=click.Abort):
                        r = run_cli(runner, ["connect", "openai"])
    assert r.exit_code != 0

