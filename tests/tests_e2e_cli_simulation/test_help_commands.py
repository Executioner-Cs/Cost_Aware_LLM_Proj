from __future__ import annotations

from tests.tests_e2e_cli_simulation.conftest import run_cli


def test_root_help(runner):
    r = run_cli(runner, ["--help"])
    assert r.exit_code == 0
    assert "Usage:" in r.stdout
    # Typer + rich can render help without a literal "Commands:" line; assert semantic contents.
    assert "connect" in r.stdout
    assert "route" in r.stdout
    assert r.stderr == ""


def test_connect_help(runner):
    r = run_cli(runner, ["connect", "--help"])
    assert r.exit_code == 0
    assert "Usage:" in r.stdout
    assert "Provider:" in r.stdout
    assert "--api-key" in r.stdout


def test_invalid_help_flag(runner):
    r = run_cli(runner, ["--halp"])
    assert r.exit_code != 0
    assert "No such option" in (r.stdout + r.stderr)

