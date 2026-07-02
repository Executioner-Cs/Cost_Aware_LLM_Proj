"""Tests for top-level command group help behavior."""

import pytest
from typer.testing import CliRunner

from cli.main import app


@pytest.mark.parametrize("group_name", ["accounts", "model", "trace", "cache"])
def test_group_command_without_subcommand_shows_help(group_name):
    runner = CliRunner()

    result = runner.invoke(app, [group_name])

    # Typer can return non-zero for missing subcommand, but output should still
    # be a clean help page (no error panel).
    assert "Usage:" in result.output
    assert "--help" in result.output
    assert "Error" not in result.output

