"""Tests for agent sandbox, file I/O, search, execution, and tool_calls table."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from agent.sandbox import Sandbox
from agent.tools import execution, file_io, search
from db.models import Base, ToolCall
from db.session import get_engine


def _session(tmp_db: Path) -> Session:
    engine = get_engine(tmp_db)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_sandbox_rejects_escape():
    with tempfile.TemporaryDirectory() as d:
        inner = Path(d) / "inner"
        inner.mkdir()
        sb = Sandbox(root=inner)
        with pytest.raises(ValueError):
            sb.resolve_path("../../..")


def test_read_write_list_file_io():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        w = file_io.write_file(sb, "a/b.txt", "hello")
        assert w["ok"] is True
        r = file_io.read_file(sb, "a/b.txt")
        assert r["ok"] and r["content"] == "hello"
        lst = file_io.list_dir(sb, ".")
        assert lst["ok"] and "a" in lst["entries"]


def test_tool_call_logged_when_session_provided():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "t.db"
        session = _session(db_path)
        try:
            sb = Sandbox(root=Path(td))
            sub = Path(td) / "proj"
            sub.mkdir()
            sb2 = Sandbox(root=sub)
            file_io.read_file(sb2, "missing.txt", session=session)
            rows = session.query(ToolCall).all()
            assert len(rows) == 1
            assert rows[0].name == "read_file"
        finally:
            session.close()
            session.bind.dispose()


def test_run_python():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = execution.run_python(sb, "print(1+1)", enabled=True)
        assert out["ok"] is True
        assert "2" in out["stdout"]


def test_run_shell_disabled_by_default():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = execution.run_shell(sb, "echo hi")
        assert out["ok"] is False


def test_search_naive_finds_file():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "x.py").write_text("unique_marker_xyz", encoding="utf-8")
        sb = Sandbox(root=root)
        with patch("agent.tools.search.shutil.which", return_value=None):
            res = search.search_codebase(sb, "unique_marker_xyz")
        assert res["ok"] is True
        assert any("x.py" in p for p in res["paths"])
