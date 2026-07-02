"""Tests for agent tool dispatcher."""
from __future__ import annotations

import tempfile
from pathlib import Path

from agent.dispatcher import dispatch_tool
from agent.sandbox import Sandbox


def test_dispatch_read_file():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "f.txt").write_text("data", encoding="utf-8")
        sb = Sandbox(root=root)
        out = dispatch_tool("read_file", '{"path": "f.txt"}', sandbox=sb)
        assert out["ok"] is True
        assert out["content"] == "data"


def test_dispatch_unknown_tool():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = dispatch_tool("nope", "{}", sandbox=sb)
        assert out["ok"] is False
