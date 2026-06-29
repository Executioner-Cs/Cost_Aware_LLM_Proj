"""
P0 agent-safety tests: subprocess env scrubbing, run_python/run_shell gating,
tool-log redaction, sandbox denylist, and write_file overwrite safety.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ToolCall
from agent.sandbox import Sandbox
from agent.tools import execution, file_io, search
from agent.dispatcher import dispatch_tool
from agent.tool_logging import log_tool_call, redact
from schemas.tools import agent_tools


# --------------------------------------------------------------------------- #
# 1. Subprocess environment scrubbing
# --------------------------------------------------------------------------- #

def test_safe_env_excludes_secrets(monkeypatch):
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
              "GOOGLE_API_KEY", "ORCHESTRATOR_KEY_FILE", "MY_SECRET", "SOME_TOKEN",
              "DB_PASSWORD", "X_CREDENTIALS"):
        monkeypatch.setenv(k, "leak")
    env = execution._safe_subprocess_env()
    for bad in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
                "GOOGLE_API_KEY", "ORCHESTRATOR_KEY_FILE", "MY_SECRET", "SOME_TOKEN",
                "DB_PASSWORD", "X_CREDENTIALS"):
        assert bad not in env, f"{bad} leaked into subprocess env"
    assert "PATH" in env  # subprocess still needs a PATH


def test_run_python_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-supersecret-value-123456")
    monkeypatch.setenv("ORCHESTRATOR_KEY_FILE", "C:/secret/key.bin")
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        code = "import os; print('OPENAI_API_KEY' in os.environ, 'ORCHESTRATOR_KEY_FILE' in os.environ)"
        out = execution.run_python(sb, code, enabled=True)
        assert out["ok"] is True, out
        assert "False False" in out["stdout"]


# --------------------------------------------------------------------------- #
# 2 + 3. run_python / run_shell gating
# --------------------------------------------------------------------------- #

def test_run_python_disabled_by_default():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = execution.run_python(sb, "print(1)")
        assert out["ok"] is False
        assert "disabled" in out["error"]


def test_run_python_enabled_runs():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = execution.run_python(sb, "print(7)", enabled=True)
        assert out["ok"] is True
        assert "7" in out["stdout"]


def test_dispatch_run_python_gated():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        off = dispatch_tool("run_python", '{"code": "print(1)"}', sandbox=sb)
        assert off["ok"] is False and "disabled" in off["error"]
        on = dispatch_tool("run_python", '{"code": "print(1)"}', sandbox=sb, allow_python=True)
        assert on["ok"] is True


def test_code_exec_tools_gated_in_schema():
    base = {t["function"]["name"] for t in agent_tools()}
    assert "run_python" not in base
    assert "run_shell" not in base
    assert {"read_file", "write_file", "list_dir", "search_codebase", "run_tests"} <= base
    assert "run_python" in {t["function"]["name"] for t in agent_tools(allow_python=True)}
    assert "run_shell" in {t["function"]["name"] for t in agent_tools(allow_shell=True)}


def test_run_shell_disabled_by_default():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        out = execution.run_shell(sb, "echo hi")
        assert out["ok"] is False


# --------------------------------------------------------------------------- #
# 5. Tool-log redaction
# --------------------------------------------------------------------------- #

def test_redact_removes_secrets():
    out = redact({
        "command": "export OPENAI_API_KEY=sk-abc123456789 && run",
        "api_key": "sk-secretvalue123456",
        "nested": [{"token": "tok_abcdef123456"}],
    })
    blob = json.dumps(out)
    assert "sk-abc123456789" not in blob
    assert "sk-secretvalue123456" not in blob
    assert "tok_abcdef123456" not in blob
    assert "***REDACTED***" in blob


def test_log_tool_call_persists_redacted(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tc.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        log_tool_call(
            session, "run_shell",
            {"command": "FOO_TOKEN=tok_abcdef123456 deploy"},
            {"stdout": "leaked sk-ant-abcdef123456 here"},
            5,
        )
        row = session.query(ToolCall).first()
        assert "tok_abcdef123456" not in row.args_json
        assert "sk-ant-abcdef123456" not in row.result_json
        assert "***REDACTED***" in (row.args_json + row.result_json)
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# 6. Sandbox denylist
# --------------------------------------------------------------------------- #

def test_sandbox_denies_sensitive_paths():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        for bad in (".env", ".env.local", "secret.key", "orchestrator.db", "my.pem", "credentials.json"):
            with pytest.raises(ValueError):
                sb.resolve_path(bad)
        assert sb.resolve_path("notes.txt").name == "notes.txt"


def test_sandbox_denies_more_credential_paths():
    # Expanded denylist: credential dirs, private keys, keystores.
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        for bad in (
            ".ssh/known_hosts", "id_rsa", "id_ed25519", ".aws/credentials",
            ".gnupg/secring.gpg", ".kube/config", ".docker/config.json",
            "server.pfx", "store.keystore", ".git-credentials", ".npmrc",
        ):
            with pytest.raises(ValueError):
                sb.resolve_path(bad)
        # A normal source file is still allowed.
        assert sb.resolve_path("src/main.py").name == "main.py"


def test_sandbox_symlink_target_outside_root_rejected(tmp_path):
    # A symlink inside the sandbox pointing outside must be rejected (resolve()
    # follows it, then confinement fails). Skip where symlinks need privileges.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    root = tmp_path / "root"
    root.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this platform")
    sb = Sandbox(root=root)
    with pytest.raises(ValueError):
        sb.resolve_path("escape/secret.txt")


def test_default_blocked_shell_patterns_expanded():
    from agent.config import _parse_blocked_patterns
    defaults = _parse_blocked_patterns(None)
    for pat in ("rm -rf", "sudo ", "curl ", "wget ", "chmod -R", "> /dev/"):
        assert pat in defaults
    # A user-supplied list still fully overrides the defaults.
    assert _parse_blocked_patterns("foo, bar") == ["foo", "bar"]


def test_redact_more_key_shapes():
    blob = json.dumps(redact({
        "log": "ghp_0123456789abcdefghij0123456789abcd used; xoxb-123456-abcdef pushed",
        "openai": "sk-proj-abcdef123456 here",
        "pem": "-----BEGIN RSA PRIVATE KEY-----",
    }))
    assert "ghp_0123456789abcdefghij" not in blob
    assert "xoxb-123456-abcdef" not in blob
    assert "sk-proj-abcdef123456" not in blob
    assert "BEGIN RSA PRIVATE KEY" not in blob
    assert "***REDACTED***" in blob


# --------------------------------------------------------------------------- #
# 7. write_file overwrite safety
# --------------------------------------------------------------------------- #

def test_write_file_refuses_overwrite_by_default():
    with tempfile.TemporaryDirectory() as d:
        sb = Sandbox(root=Path(d))
        assert file_io.write_file(sb, "a.txt", "one")["ok"] is True
        blocked = file_io.write_file(sb, "a.txt", "two")
        assert blocked["ok"] is False and "overwrite" in blocked["error"]
        assert file_io.write_file(sb, "a.txt", "three", overwrite=True)["ok"] is True
        assert (Path(d) / "a.txt").read_text() == "three"


# --------------------------------------------------------------------------- #
# Sensitive files never surface in search results
# --------------------------------------------------------------------------- #

def test_search_excludes_sensitive_files():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "ok.py").write_text("needle here")
        (root / "secret.py").write_text("needle here")
        res = search.search_codebase(Sandbox(root=root), "needle")
        paths = " ".join(res.get("paths", []))
        assert "ok.py" in paths
        assert "secret.py" not in paths
