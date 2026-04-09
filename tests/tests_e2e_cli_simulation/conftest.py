from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pytest
from typer.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    # Typer's CliRunner API mirrors Click's and doesn't accept mix_stderr
    # on some versions; keep it default and use result.output.
    return CliRunner()


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    stdout: str
    stderr: str


def run_cli(runner: CliRunner, args: list[str]) -> RunResult:
    from cli.main import app

    res = runner.invoke(app, args)
    # Some Click/Typer versions expose .stderr property that raises if stderr
    # wasn't captured separately.
    try:
        stderr = res.stderr or ""
    except Exception:
        stderr = ""
    return RunResult(
        exit_code=res.exit_code,
        stdout=(getattr(res, "stdout", None) or getattr(res, "output", "") or ""),
        stderr=stderr,
    )


@pytest.fixture()
def env(monkeypatch):
    """
    Helper to set env vars in a structured way.
    Usage:
      env.set(OPENAI_API_KEY="sk-...") / env.unset("OPENAI_API_KEY")
    """

    class _Env:
        def set(self, **kwargs: str) -> None:
            for k, v in kwargs.items():
                monkeypatch.setenv(k, v)

        def unset(self, *keys: str) -> None:
            for k in keys:
                monkeypatch.delenv(k, raising=False)

    return _Env()

