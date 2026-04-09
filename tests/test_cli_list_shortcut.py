"""Tests for top-level `orchestrator list` convenience command."""

from typer.testing import CliRunner

from cli.main import app


def test_list_defaults_to_accounts(monkeypatch):
    runner = CliRunner()
    called = {"accounts": 0}

    def fake_list_accounts():
        called["accounts"] += 1

    monkeypatch.setattr("cli.commands.accounts.list_accounts", fake_list_accounts)

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert called["accounts"] == 1


def test_list_models_calls_model_list(monkeypatch):
    runner = CliRunner()
    called = {"models": 0}

    def fake_list_models():
        called["models"] += 1

    monkeypatch.setattr("cli.commands.model.list_models", fake_list_models)

    result = runner.invoke(app, ["list", "models"])

    assert result.exit_code == 0
    assert called["models"] == 1


def test_list_traces_passes_limit(monkeypatch):
    runner = CliRunner()
    seen = {"limit": None}

    def fake_list_traces(limit=20):
        seen["limit"] = limit

    monkeypatch.setattr("cli.commands.trace.list_traces", fake_list_traces)

    result = runner.invoke(app, ["list", "traces", "--limit", "7"])

    assert result.exit_code == 0
    assert seen["limit"] == 7


def test_list_invalid_resource_returns_error(monkeypatch):
    runner = CliRunner()
    errors = []

    def fake_print_error(message):
        errors.append(message)

    monkeypatch.setattr("utils.console.print_error", fake_print_error)

    result = runner.invoke(app, ["list", "unknown"])

    assert result.exit_code == 1
    assert errors
    assert "Unknown list resource" in errors[0]

