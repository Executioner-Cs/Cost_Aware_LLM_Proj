"""Application-level routing orchestration.

A thin service boundary between the CLI/TUI and the core routing pipeline. It
owns the session lifecycle for a route request and returns the same
``RouteResult`` the core pipeline produces. Future routing policies and source
selection plug in here without changing the CLI surface or the core pipeline
contract.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from schemas.routing import RouteRequest, RouteResult


def route_prompt(request: RouteRequest, session: Optional[Session] = None) -> RouteResult:
    """Route a request through the core pipeline.

    If no session is supplied, one is created and closed here. The returned
    ``RouteResult`` and all trace/cache side effects are identical to calling
    ``core.router.route`` directly; this only owns the session boundary.

    ``route`` is imported lazily so the live ``core.router.route`` is always used
    (respecting test patches) and never captured as a stale module-level binding.
    """
    from core.router import route as _core_route

    own_session = session is None
    if own_session:
        from db.session import get_session
        session = get_session()
    try:
        return _core_route(request, session)
    finally:
        if own_session:
            session.close()
