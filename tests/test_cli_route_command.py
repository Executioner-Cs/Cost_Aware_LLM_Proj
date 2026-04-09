"""Tests for top-level `orchestrator route` command wiring."""

from types import SimpleNamespace

from typer.testing import CliRunner

from cli.main import app


def test_route_dry_run_flag_is_parsed(monkeypatch):
    runner = CliRunner()
    captured = {"dry_run": None}

    class DummySession:
        def close(self):
            return None

    def fake_get_session():
        return DummySession()

    def fake_route(request, _session):
        captured["dry_run"] = request.dry_run
        return SimpleNamespace(
            task_type="simple",
            route_reason="dry_run_test",
            provider=None,
            model_id=None,
            cache_hit=False,
            cache_similarity=None,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=0.0,
            latency_ms=None,
            response_text=None,
        )

    monkeypatch.setattr("db.session.get_session", fake_get_session)
    monkeypatch.setattr("core.router.route", fake_route)
    monkeypatch.setattr("utils.console.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("utils.console.print_error", lambda _msg: None)

    result = runner.invoke(app, ["route", "hello", "--dry-run"])

    assert result.exit_code == 0
    assert captured["dry_run"] is True

