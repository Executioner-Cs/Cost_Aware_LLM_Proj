"""
Tests for the exact-default cache (core/cache.py) and the cache factory.

The exact path must work without importing the ML/vector stack. The
``test_route_exact_mode_*`` cases poison the heavy modules in ``sys.modules`` so
any accidental import on the default route path fails loudly.
"""
import sys
import math
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

from db.models import Base, ModelRegistry, ConnectedAccount, ExactCacheEntry
from core.cache import get_cache, ExactCache, NoOpCache, SemanticCacheBackend
from schemas.routing import RouteRequest


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


# --------------------------------------------------------------------------- #
# ExactCache hit/miss without embeddings/Qdrant
# --------------------------------------------------------------------------- #

def test_exact_cache_miss_then_hit(session):
    cache = ExactCache(session)
    assert cache.lookup("What is 2+2?", "simple", "balanced") is None
    cache.store("What is 2+2?", "simple", "balanced", "4", "openai", "gpt-4o-mini", 5, 1)
    hit = cache.lookup("What is 2+2?", "simple", "balanced")
    assert hit is not None
    assert hit.response_text == "4"
    assert hit.similarity == 1.0
    assert hit.provider == "openai"


def test_exact_cache_distinguishes_task_and_quality(session):
    cache = ExactCache(session)
    cache.store("ping", "simple", "balanced", "A", "openai", "m", 1, 1)
    # A different task_type or quality is a different key -> miss.
    assert cache.lookup("ping", "reasoning", "balanced") is None
    assert cache.lookup("ping", "simple", "best") is None
    # Whitespace-normalized identical prompt -> hit.
    assert cache.lookup("  ping  ", "simple", "balanced") is not None


def test_exact_cache_ttl_expiry(session):
    cache = ExactCache(session, ttl_seconds=3600)
    cache.store("stale?", "simple", "balanced", "old", "openai", "m", 1, 1)
    key = cache._key("stale?", "simple", "balanced")
    entry = session.get(ExactCacheEntry, key)
    entry.created_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    session.commit()
    assert cache.lookup("stale?", "simple", "balanced") is None  # expired -> miss


# --------------------------------------------------------------------------- #
# get_cache factory: default is exact, not semantic
# --------------------------------------------------------------------------- #

def test_get_cache_returns_exact_by_default(session, tmp_path):
    assert isinstance(get_cache({"cache": {"enabled": True}}, session, tmp_path), ExactCache)


def test_get_cache_empty_config_defaults_exact(session, tmp_path):
    assert isinstance(get_cache({}, session, tmp_path), ExactCache)


def test_default_cache_is_exact_not_semantic(session, tmp_path):
    cache = get_cache({"cache": {"enabled": True, "mode": "exact"}}, session, tmp_path)
    assert isinstance(cache, ExactCache)
    assert not isinstance(cache, SemanticCacheBackend)


def test_get_cache_disabled_returns_noop(session, tmp_path):
    cache = get_cache({"cache": {"enabled": False}}, session, tmp_path)
    assert isinstance(cache, NoOpCache)
    assert cache.lookup("x", "simple", "balanced") is None


def test_get_cache_off_mode_returns_noop(session, tmp_path):
    assert isinstance(get_cache({"cache": {"enabled": True, "mode": "off"}}, session, tmp_path), NoOpCache)


# --------------------------------------------------------------------------- #
# Old DB without exact_cache gains the table safely (no migration framework)
# --------------------------------------------------------------------------- #

def test_old_db_without_exact_cache_gains_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    # Simulate a database created before exact_cache existed.
    older_tables = [t for name, t in Base.metadata.tables.items() if name != "exact_cache"]
    Base.metadata.create_all(engine, tables=older_tables)
    assert "exact_cache" not in sa_inspect(engine).get_table_names()

    s = sessionmaker(bind=engine)()
    cache = ExactCache(s)  # __init__ provisions exact_cache via create_all
    assert "exact_cache" in sa_inspect(engine).get_table_names()
    cache.store("q", "simple", "balanced", "a", "openai", "m", 1, 1)
    assert cache.lookup("q", "simple", "balanced").response_text == "a"
    s.close()


# --------------------------------------------------------------------------- #
# Route in exact mode imports no heavy dependencies
# --------------------------------------------------------------------------- #

def _populate(session):
    now = datetime.now(timezone.utc).isoformat()
    session.add(ConnectedAccount(
        id="acc-1", provider="openai", display_name="T", auth_method="pat",
        encrypted_token="x", status="active", connected_at=now,
    ))
    session.add(ModelRegistry(
        id="m-1", account_id="acc-1", provider="openai",
        external_model_id="gpt-4o-mini", display_name="GPT-4o Mini", tier="small",
        context_window=128_000, cost_per_1m_input=0.15, cost_per_1m_output=0.60,
        supports_json=1, supports_tools=1, supports_vision=1, enabled=1,
        discovered_at=now,
    ))
    session.commit()


def test_route_exact_mode_no_heavy_imports(session, tmp_path, monkeypatch):
    _populate(session)
    from providers.base import GenerateResult

    fake = GenerateResult(
        response_text="Paris", input_tokens=10, output_tokens=5,
        latency_ms=100, model_id="gpt-4o-mini", provider="openai",
    )
    exact_cfg = {"cache": {"enabled": True, "mode": "exact", "ttl_seconds": 86400}}

    # Poison the heavy modules: any import attempt on the exact path now raises
    # ImportError, which would fail the route and this test.
    for mod in ("sentence_transformers", "torch", "qdrant_client", "transformers"):
        monkeypatch.setitem(sys.modules, mod, None)

    with (
        patch("core.router.get_home", return_value=tmp_path),
        patch("core.router.load_config", return_value=exact_cfg),
        patch("core.router.decrypt", return_value="fake-key"),
        patch("providers.openai.adapter.OpenAIAdapter.generate", return_value=fake),
    ):
        from core.router import route
        r1 = route(RouteRequest(prompt="Capital of France?"), session)
        assert r1.response_text == "Paris"
        assert r1.cache_hit is False

        # Identical prompt: exact cache hit, provider must NOT be called again.
        with patch(
            "providers.openai.adapter.OpenAIAdapter.generate",
            side_effect=AssertionError("provider called on a cache hit"),
        ):
            r2 = route(RouteRequest(prompt="Capital of France?"), session)
        assert r2.cache_hit is True
        assert r2.response_text == "Paris"

    # Confirm nothing replaced the sentinels with a real heavy import.
    for mod in ("sentence_transformers", "torch", "qdrant_client"):
        assert sys.modules.get(mod) is None


# --------------------------------------------------------------------------- #
# Semantic cache remains available when explicitly configured (deps present)
# --------------------------------------------------------------------------- #

def test_semantic_mode_available_when_configured(session, tmp_path, monkeypatch):
    """mode = "semantic" builds the semantic backend and round-trips a hit.

    A fake embedder is injected so the test exercises the real semantic backend
    and Qdrant without loading sentence-transformers/torch.
    """
    def fake_embed(text: str):
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        vec = [math.sin(h + i) for i in range(384)]
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec]

    import embeddings.embedder as emb
    monkeypatch.setattr(emb, "embed", fake_embed)

    cache = get_cache(
        {"cache": {"enabled": True, "mode": "semantic", "similarity_threshold": 0.5}},
        session, tmp_path,
    )
    assert isinstance(cache, SemanticCacheBackend)
    cache.store("hello world", "simple", "balanced", "Hi", "openai", "m", 3, 2)
    hit = cache.lookup("hello world", "simple", "balanced")
    assert hit is not None
    assert hit.response_text == "Hi"
    cache.close()
