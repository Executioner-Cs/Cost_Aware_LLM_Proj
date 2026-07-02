"""`orchestrator agent --help` must show a description for every subcommand.

Previously edit / explain / fix-tests / refactor had no docstring, so their
help column rendered blank and the command group looked unfinished.
"""
from __future__ import annotations

from typer.testing import CliRunner

from cli.commands import agent as agent_cmd
from cli.main import app


def test_agent_subcommands_have_help_docstrings():
    by_name = {c.name: c for c in agent_cmd.app.registered_commands}
    for name in ("run", "edit", "explain", "fix-tests", "refactor"):
        callback = by_name[name].callback
        assert (callback.__doc__ or "").strip(), f"agent '{name}' has no help text"


def test_agent_help_renders_without_error():
    result = CliRunner().invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    # Command names are still listed.
    for name in ("edit", "explain", "fix-tests", "refactor"):
        assert name in result.output
