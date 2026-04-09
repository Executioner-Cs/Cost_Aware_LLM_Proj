from __future__ import annotations

from tests.tests_e2e_cli_simulation.conftest import run_cli


def test_unknown_command(runner):
    r = run_cli(runner, ["frobnicate"])
    assert r.exit_code != 0
    assert "No such command" in (r.stdout + r.stderr)


def test_missing_required_argument(runner):
    r = run_cli(runner, ["connect"])
    assert r.exit_code != 0
    assert "Missing argument" in (r.stdout + r.stderr)


def test_unknown_option(runner):
    r = run_cli(runner, ["connect", "openai", "--api-keey", "x"])
    assert r.exit_code != 0
    assert "No such option" in (r.stdout + r.stderr)

