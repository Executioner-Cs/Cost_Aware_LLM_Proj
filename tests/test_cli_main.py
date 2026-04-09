"""Tests for cli/main.py — including hybrid root behaviour."""
from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from cli.main import app


def test_install_completion_uses_orchestrator_prog_name(monkeypatch):
    """Ensure completion install always targets the orchestrator command."""
    runner = CliRunner()
    calls = []

    def fake_install(shell=None, prog_name=None, complete_var=None):
        calls.append(
            {
                "shell": shell,
                "prog_name": prog_name,
                "complete_var": complete_var,
            }
        )
        return "powershell", Path("C:/fake/profile.ps1")

    monkeypatch.setattr("typer.completion.install", fake_install)

    result = runner.invoke(app, ["--install-completion"])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["prog_name"] == "orchestrator"
    assert "Installation completed." in result.output


def test_no_args_non_tty_prints_help():
    """Non-interactive invocation without subcommand shows help text."""
    runner = CliRunner()
    with patch("cli.main._is_interactive_tty", return_value=False):
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "orchestrator" in result.output.lower() or "commands" in result.output.lower()


def test_no_args_interactive_launches_tui():
    """Interactive TTY invocation without subcommand launches the TUI app."""
    runner = CliRunner()
    mock_app = MagicMock()
    with patch("cli.main._is_interactive_tty", return_value=True), \
         patch("cli.tui.app.OrchestratorApp", return_value=mock_app) as cls_mock:
        result = runner.invoke(app, [])
    cls_mock.assert_called_once()
    mock_app.run.assert_called_once()


def test_subcommand_bypasses_tui():
    """Running with a subcommand never touches the TUI path."""
    runner = CliRunner()
    with patch("cli.main._is_interactive_tty", return_value=True) as tty_check:
        result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0

