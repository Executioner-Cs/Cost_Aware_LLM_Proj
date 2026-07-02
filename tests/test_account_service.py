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


def test_sync_cloud_missing_token_raises_clear_error(monkeypatch, tmp_path):
    session = _session(tmp_path)
    try:
        _add(session, id="acc-notoken", provider="openai", encrypted_token=None, source_type="cloud")

        def _must_not_load(*a, **k):
            raise AssertionError("connector must not be loaded when the token is missing")

        monkeypatch.setattr("services.connect_service._load_connector", _must_not_load)
        with pytest.raises(ValueError, match="no stored token"):
            account_service.sync_account(session, "acc-notoken")
    finally:
        session.close()


def test_sync_legacy_none_source_type_takes_cloud_path(monkeypatch, tmp_path):
    session = _session(tmp_path)
    try:
        # Rows created before the sources branch have source_type=None.
        _add(session, id="acc-legacy", provider="openai", encrypted_token="enc", source_type=None)
        monkeypatch.setattr("utils.crypto.decrypt", lambda t: "key")
        monkeypatch.setattr("services.connect_service._load_connector", lambda p, k: _FakeConnector(True))
        account_service.sync_account(session, "acc-legacy")
        rows = session.query(ModelRegistry).filter_by(account_id="acc-legacy").all()
        assert [r.external_model_id for r in rows] == ["cloud-model"]
    finally:
        session.close()


def test_sync_openai_compatible_passes_decrypted_key(monkeypatch, tmp_path):
    session = _session(tmp_path)
    captured = {}
    try:
        _add(session, id="acc-oc", provider="openai_compatible", encrypted_token="enc",
             source_type="openai_compatible", base_url="http://h/v1")
        monkeypatch.setattr("utils.crypto.decrypt", lambda t: "real-key")

        def _capture(self, api_key):
            captured["key"] = api_key
            return [_info("m1")]

        monkeypatch.setattr("providers.source.ModelSource.list_models", _capture)
        account_service.sync_account(session, "acc-oc")
        assert captured["key"] == "real-key"   # keyed source sends its decrypted key
    finally:
        session.close()


def test_sync_local_unreachable_raises_value_error(monkeypatch, tmp_path):
    import httpx
    session = _session(tmp_path)
    try:
        _add(session, id="acc-ol", provider="ollama", auth_method="none", encrypted_token=None,
             source_type="ollama", base_url="http://localhost:11434")

        def _boom(self, api_key):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr("providers.source.ModelSource.list_models", _boom)
        # Normalized to ValueError so the CLI handler reports it cleanly.
        with pytest.raises(ValueError, match="Could not reach"):
            account_service.sync_account(session, "acc-ol")
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
