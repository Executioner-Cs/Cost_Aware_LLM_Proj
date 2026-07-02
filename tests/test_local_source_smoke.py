"""Local-source smoke coverage with fakes only: no real Ollama, no network, no
keys. Verifies that connecting two distinct local endpoints that expose the same
model name yields two distinct routing candidates, each tied to its own endpoint
(end-to-end through connect -> registry -> candidate pool)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base
from providers.base import ModelInfo


def _fake_llama3(self, api_key):
    return [ModelInfo(
        external_model_id="llama3", display_name="llama3", tier="balanced",
        context_window=8192, cost_per_1m_input=0.0, cost_per_1m_output=0.0,
    )]


def test_two_local_endpoints_remain_distinct_routing_candidates(monkeypatch, tmp_path):
    from services import connect_service
    from db.repositories.models import list_enabled
    from db.repositories.accounts import get_by_id

    engine = create_engine(f"sqlite:///{tmp_path / 's.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr("providers.source.ModelSource.list_models", _fake_llama3)
    monkeypatch.setattr("utils.console.print_warning", lambda msg: None)  # warning tested elsewhere

    connect_service.connect(session, "ollama", "", base_url="http://a:11434")
    connect_service.connect(session, "ollama", "", base_url="http://b:11434")

    candidates = [m for m in list_enabled(session) if m.external_model_id == "llama3"]
    assert len(candidates) == 2, "two distinct local endpoints must yield two routing candidates"
    base_urls = {get_by_id(session, m.account_id).base_url for m in candidates}
    assert base_urls == {"http://a:11434", "http://b:11434"}
    session.close()
