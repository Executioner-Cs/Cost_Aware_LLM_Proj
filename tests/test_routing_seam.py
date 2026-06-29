"""
Config / routing seam: config loading is independent of init_service, the core
router no longer reaches into init_service, and routing_service is a thin,
behavior-preserving delegation boundary.
"""
from __future__ import annotations

from pathlib import Path

from schemas.routing import RouteRequest

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Config seam
# --------------------------------------------------------------------------- #

def test_config_service_loads_without_init_service(tmp_path, monkeypatch):
    from services.config_service import get_home, load_config

    assert load_config(tmp_path) == {}  # no config.toml -> empty dict
    (tmp_path / "config.toml").write_text('[cache]\nmode = "exact"\n', encoding="utf-8")
    assert load_config(tmp_path)["cache"]["mode"] == "exact"

    monkeypatch.setenv("ORCHESTRATOR_HOME", str(tmp_path))
    assert get_home() == Path(str(tmp_path))


def test_init_service_reexports_config_helpers():
    # Existing importers (agent, cli, tui) still do `from services.init_service
    # import get_home, load_config`; that must keep working after the move.
    from services import init_service, config_service
    assert init_service.get_home is config_service.get_home
    assert init_service.load_config is config_service.load_config


def test_core_router_has_no_init_service_coupling():
    src = (REPO_ROOT / "core" / "router.py").read_text(encoding="utf-8")
    assert "services.init_service" not in src   # the flagged core -> services coupling is gone
    assert "services.config_service" in src


# --------------------------------------------------------------------------- #
# Routing seam
# --------------------------------------------------------------------------- #

def test_routing_service_delegates_to_core_router(monkeypatch):
    from services import routing_service

    captured = {}

    def fake_route(request, session):
        captured["request"] = request
        captured["session"] = session
        return "SENTINEL_RESULT"

    monkeypatch.setattr("core.router.route", fake_route)
    sentinel_session = object()
    req = RouteRequest(prompt="hello world")
    result = routing_service.route_prompt(req, session=sentinel_session)

    assert result == "SENTINEL_RESULT"          # returns exactly what core.router produced
    assert captured["request"] is req           # request passed through unchanged
    assert captured["session"] is sentinel_session  # caller's session reused, not replaced


def test_routing_service_creates_and_closes_own_session(monkeypatch):
    from services import routing_service

    captured = {}

    def fake_route(request, session):
        captured["session"] = session
        return "OK"

    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    fake = FakeSession()
    monkeypatch.setattr("core.router.route", fake_route)
    monkeypatch.setattr("db.session.get_session", lambda: fake)

    result = routing_service.route_prompt(RouteRequest(prompt="hi"))

    assert result == "OK"
    assert captured["session"] is fake  # the service-owned session was used
    assert fake.closed is True          # and closed afterwards
