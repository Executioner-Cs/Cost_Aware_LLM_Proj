"""
Tests for core/semantic_cache.py
Uses a temporary directory for both Qdrant and SQLite to avoid state leakage.
"""
import pytest
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base
from core.semantic_cache import SemanticCache


@pytest.fixture
def tmp_cache(tmp_path):
    """Provide an isolated SemanticCache instance backed by tmp dirs."""
    qdrant_path = tmp_path / "qdrant"
    db_path = tmp_path / "test.db"

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    cache = SemanticCache(
        qdrant_path=qdrant_path,
        sqlite_session=session,
        similarity_threshold=0.92,
    )
    yield cache
    cache.close()
    session.close()


def _fake_embed(text: str) -> list[float]:
    """Return a deterministic 384-dim unit vector based on hash of text."""
    import hashlib, math
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    vec = []
    for i in range(384):
        val = math.sin(h + i)
        vec.append(val)
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def _nearly_same_embed(base: list[float]) -> list[float]:
    """Return a vector that is cosine-similar ≥ 0.99 to base (just add tiny noise)."""
    import math
    noisy = [v + 0.0001 * (i % 3 - 1) for i, v in enumerate(base)]
    norm = math.sqrt(sum(v * v for v in noisy))
    return [v / norm for v in noisy]


def _orthogonal_embed(base: list[float]) -> list[float]:
    """Return a very different unit vector."""
    import math
    vec = [0.0] * 384
    # set dimension 0 to 1, all else 0 (orthogonal if base[0] ≈ 0)
    vec[1] = 1.0
    return vec


def test_miss_on_empty_cache(tmp_cache):
    emb = _fake_embed("hello world")
    result = tmp_cache.lookup(emb, "simple", "balanced")
    assert result is None


def test_store_and_hit(tmp_cache):
    emb = _fake_embed("hello world")
    tmp_cache.store(
        embedding=emb,
        task_type="simple",
        quality="balanced",
        response_text="Hi there!",
        provider="openai",
        model_id="gpt-4o-mini",
        input_tokens=10,
        output_tokens=5,
    )
    # Lookup with nearly identical vector
    similar_emb = _nearly_same_embed(emb)
    result = tmp_cache.lookup(similar_emb, "simple", "balanced")
    assert result is not None
    assert result.response_text == "Hi there!"
    assert result.similarity >= 0.92


def test_task_type_filter(tmp_cache):
    """A reasoning result should NOT be served to a json_extract request."""
    emb = _fake_embed("test prompt")
    tmp_cache.store(
        embedding=emb,
        task_type="reasoning",
        quality="balanced",
        response_text="Deep reasoning answer",
        provider="anthropic",
        model_id="claude-sonnet",
        input_tokens=20,
        output_tokens=40,
    )
    similar_emb = _nearly_same_embed(emb)
    result = tmp_cache.lookup(similar_emb, "json_extract", "balanced")
    assert result is None


def test_quality_filter(tmp_cache):
    """A cheap-quality result should NOT be served to a best-quality request."""
    emb = _fake_embed("quality test prompt")
    tmp_cache.store(
        embedding=emb,
        task_type="simple",
        quality="cheap",
        response_text="Cheap answer",
        provider="openai",
        model_id="gpt-4o-mini",
        input_tokens=5,
        output_tokens=10,
    )
    similar_emb = _nearly_same_embed(emb)
    result = tmp_cache.lookup(similar_emb, "simple", "best")
    assert result is None


def test_hit_increments_count(tmp_cache):
    from db.models import CacheEntry
    emb = _fake_embed("count test")
    tmp_cache.store(
        embedding=emb,
        task_type="simple",
        quality="balanced",
        response_text="Answer",
        provider="openai",
        model_id="gpt-4o-mini",
        input_tokens=5,
        output_tokens=5,
    )
    similar = _nearly_same_embed(emb)
    # Hit twice
    tmp_cache.lookup(similar, "simple", "balanced")
    result = tmp_cache.lookup(similar, "simple", "balanced")
    assert result is not None
    entry = tmp_cache.get_entry(result.entry_id)
    assert entry.hit_count == 2


def test_clear_all(tmp_cache):
    emb = _fake_embed("clear test")
    tmp_cache.store(
        embedding=emb, task_type="simple", quality="balanced",
        response_text="x", provider="openai", model_id="m",
        input_tokens=1, output_tokens=1,
    )
    deleted = tmp_cache.clear()
    assert deleted == 1
    result = tmp_cache.lookup(_nearly_same_embed(emb), "simple", "balanced")
    assert result is None


def test_clear_by_task_type(tmp_cache):
    e1 = _fake_embed("simple prompt abc")
    e2 = _fake_embed("reasoning prompt xyz")
    tmp_cache.store(e1, "simple", "balanced", "resp1", "openai", "m", 1, 1)
    tmp_cache.store(e2, "reasoning", "balanced", "resp2", "openai", "m", 1, 1)

    deleted = tmp_cache.clear(task_type="simple")
    assert deleted == 1

    stats = tmp_cache.stats()
    assert stats["total_entries"] == 1
