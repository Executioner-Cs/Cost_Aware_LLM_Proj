"""Benchmark CLI validation. These cases all fail before any DB access, so they
do not touch the real ~/.orchestrator database."""
from __future__ import annotations

from tests.tests_e2e_cli_simulation.conftest import run_cli


def test_benchmark_help_lists_subcommands(runner):
    r = run_cli(runner, ["benchmark", "--help"])
    assert r.exit_code == 0
    out = r.stdout + r.stderr
    for sub in ("create", "add-task", "run", "scorecards"):
        assert sub in out


def test_create_missing_name_exits_nonzero(runner):
    r = run_cli(runner, ["benchmark", "create"])
    assert r.exit_code != 0
    assert "Missing argument" in (r.stdout + r.stderr)


def test_add_task_invalid_grader_exits_one(runner):
    r = run_cli(runner, ["benchmark", "add-task", "ts", "q", "--grader", "vibes"])
    assert r.exit_code == 1
    assert "grader must be one of" in (r.stdout + r.stderr)


def test_add_task_contains_without_expected_exits_one(runner):
    # contains/exact need an expected answer; guarded before the DB is opened.
    r = run_cli(runner, ["benchmark", "add-task", "ts", "q", "--grader", "contains"])
    assert r.exit_code == 1
    assert "needs --expected" in (r.stdout + r.stderr)
