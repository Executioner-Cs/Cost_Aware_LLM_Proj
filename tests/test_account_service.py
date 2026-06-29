"""account_service.sync_account: the cloud path is preserved (validate key, list
via connector), and local sources re-discover through the ModelSource instead of
crashing on a missing connector. No network: connector and source are stubbed."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ConnectedAccount, ModelRegistry
from providers.base import ModelInfo
from services import account_service


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _info(ext):
    return ModelInfo(
        external_model_id=ext, display_name=ext, tier="small",
        context_window=8192, cost_per_1m_input=0.0, cost_per_1m_output=0.0,
    )


class _FakeConnector:
    def __init__(self, valid=True):
        self._valid = valid

    def validate_key(self):
        return self._valid

    def list_models(self):
        return [_info("cloud-model")]


def _add(session, **kwargs):
    base = dict(
        auth_method="pat", status="active",
        connected_at=datetime.now(timezone.utc).isoformat(),
    )
    base.update(kwargs)
    session.add(ConnectedAccount(**base))
    session.commit()


def test_sync_cloud_account_validates_and_lists(monkeypatch, tmp_path):
    session = _session(tmp_path)
    try:
        _add(session, id="acc-cloud", provider="openai", encrypted_token="enc", source_type="cloud")
        monkeypatch.setattr("utils.crypto.decrypt", lambda t: "key")
        monkeypatch.setattr("services.connect_service._load_connector", lambda p, k: _FakeConnector(True))

        updated = account_service.sync_account(session, "acc-cloud")
        assert updated.last_synced_at
        rows = session.query(ModelRegistry).filter_by(account_id="acc-cloud").all()
        assert [r.external_model_id for r in rows] == ["cloud-model"]
    finally:
        session.close()


def test_sync_cloud_invalid_key_marks_invalid_and_raises(monkeypatch, tmp_path):
    session = _session(tmp_path)
    try:
        _add(session, id="acc-bad", provider="openai", encrypted_token="enc", source_type="cloud")
        monkeypatch.setattr("utils.crypto.decrypt", lambda t: "key")
        monkeypatch.setattr("services.connect_service._load_connector", lambda p, k: _FakeConnector(False))

        with pytest.raises(ValueError, match="validation failed"):
            account_service.sync_account(session, "acc-bad")
        assert session.get(ConnectedAccount, "acc-bad").status == "invalid"
    finally:
        session.close()


def test_sync_local_ollama_rediscovers_without_connector(monkeypatch, tmp_path):
    session = _session(tmp_path)
    try:
        _add(
            session, id="acc-ollama", provider="ollama", auth_method="none",
            encrypted_token=None, source_type="ollama", base_url="http://localhost:11434",
        )
        # There is no connector for ollama; sync must go through the source. The
        # keyless token must not be decrypted (None).
        monkeypatch.setattr(
            "providers.source.ModelSource.list_models",
            lambda self, api_key: [_info("llama3")],
        )
        updated = account_service.sync_account(session, "acc-ollama")
        assert updated.last_synced_at
        rows = session.query(ModelRegistry).filter_by(account_id="acc-ollama").all()
        assert [r.external_model_id for r in rows] == ["llama3"]
    finally:
        session.close()
