"""Tests for cli/main.py."""
from pathlib import Path

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

