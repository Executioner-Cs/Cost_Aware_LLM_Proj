"""Shell blocking patterns."""
from __future__ import annotations

import tempfile
from pathlib import Path

from agent.sandbox import Sandbox
from agent.tools.execution import run_shell


def test_run_shell_blocks_pattern():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = run_shell(
            sb,
            "rm -rf /",
            allow_shell=True,
            blocked_shell_patterns=["rm -rf"],
        )
        assert out["ok"] is False
        assert "blocked" in out["error"].lower()
