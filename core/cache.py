"""
Cache backends for the routing path.

Default is the exact-match cache (:class:`ExactCache`): a single SQLite lookup
keyed by ``sha256(normalized_prompt + task_type + quality)``. It needs no
embedding model and no vector store, so importing or using it never pulls
sentence-transformers, torch, or qdrant-client.

The semantic cache (similarity search over embeddings) is opt-in. It is built
only when ``[cache] mode = "semantic"`` and its heavy dependencies are loaded
lazily, inside :class:`SemanticCacheBackend`, never at module import time.

``get_cache(config, session, home)`` is the single entry point:
  - ``enabled = false``           -> :class:`NoOpCache`
  - ``mode = "off"``              -> :class:`NoOpCache`
  - ``mode = "exact"`` (default)  -> :class:`ExactCache`
  - ``mode = "semantic"``         -> :class:`SemanticCacheBackend` (lazy heavy imports)
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import Base, ExactCacheEntry
from utils.hashing import sha256_hex


class MissingFeatureError(RuntimeError):
    """Raised when an optional capability is requested but its extra is not installed."""

    def __init__(self, extra: str, hint: str) -> None:
        self.extra = extra
        self.hint = hint
        super().__init__(hint)


@dataclass
class CacheResult:
    """Uniform cache hit shape. ``similarity`` is 1.0 for exact hits."""
    entry_id: str
    response_text: str
    similarity: float
    provider: Optional[str]
    model_id: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.strip())


class BaseCache(ABC):
    """Cache interface used by the router. Keyed by (prompt, task_type, quality)."""

    @abstractmethod
    def lookup(self, prompt: str, task_type: str, quality: str) -> Optional[CacheResult]:
        ...

    @abstractmethod
    def store(
        self,
        prompt: str,
        task_type: str,
        quality: str,
        response_text: str,
        provider: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        ...

    @abstractmethod
    def stats(self) -> dict:
        ...

    @abstractmethod
    def clear(self, task_type: Optional[str] = None, older_than_days: Optional[int] = None) -> int:
        ...

    def close(self) -> None:  # default no-op; semantic backend overrides
        return None


class NoOpCache(BaseCache):
    """Cache disabled. Every lookup misses; stores are dropped."""

    def lookup(self, prompt: str, task_type: str, quality: str) -> Optional[CacheResult]:
        return None

    def store(self, prompt, task_type, quality, response_text, provider, model_id, input_tokens, output_tokens) -> None:
        return None

    def stats(self) -> dict:
        return {"total_entries": 0, "total_hits": 0, "top_entries": []}

    def clear(self, task_type: Optional[str] = None, older_than_days: Optional[int] = None) -> int:
        return 0


class ExactCache(BaseCache):
    """Exact-match cache backed by the ``exact_cache`` SQLite table.

    The key is ``sha256(normalized_prompt + task_type + quality)``: a hit can
    only ever return the answer to the *same* question at the same task/quality,
    so it cannot serve a different prompt's answer the way similarity search can.
    """

    _KEY_SEP = "\x1f"

    def __init__(self, session: Session, ttl_seconds: Optional[int] = None) -> None:
        self.session = session
        self.ttl_seconds = ttl_seconds
        # Provision the table on the bound engine. create_all only creates
        # missing tables, so this safely adds exact_cache to an existing DB
        # without touching other tables (this repo has no migration system).
        bind = session.get_bind()
        if bind is not None:
            Base.metadata.create_all(bind, tables=[ExactCacheEntry.__table__])

    def _key(self, prompt: str, task_type: str, quality: str) -> str:
        return sha256_hex(self._KEY_SEP.join((_normalize(prompt), task_type, quality)))

    def _is_expired(self, created_at: str) -> bool:
        if not self.ttl_seconds:
            return False
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)).isoformat()
        return created_at < cutoff

    def lookup(self, prompt: str, task_type: str, quality: str) -> Optional[CacheResult]:
        key = self._key(prompt, task_type, quality)
        entry = self.session.get(ExactCacheEntry, key)
        if entry is None:
            return None
        if self._is_expired(entry.created_at):
            return None  # TTL-on-read: treat stale entries as a miss
        entry.hit_count = (entry.hit_count or 0) + 1
        entry.last_hit_at = _now()
        self.session.commit()
        return CacheResult(
            entry_id=entry.prompt_hash,
            response_text=entry.response_text,
            similarity=1.0,
            provider=entry.provider,
            model_id=entry.model_id,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
        )

    def store(self, prompt, task_type, quality, response_text, provider, model_id, input_tokens, output_tokens) -> None:
        key = self._key(prompt, task_type, quality)
        now = _now()
        entry = self.session.get(ExactCacheEntry, key)
        if entry is None:
            entry = ExactCacheEntry(
                prompt_hash=key,
                response_text=response_text,
                task_type=task_type,
                quality=quality,
                provider=provider,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                hit_count=0,
                created_at=now,
            )
            self.session.add(entry)
        else:
            # Refresh the stored answer and reset its TTL clock.
            entry.response_text = response_text
            entry.provider = provider
            entry.model_id = model_id
            entry.input_tokens = input_tokens
            entry.output_tokens = output_tokens
            entry.created_at = now
        self.session.commit()

    def stats(self) -> dict:
        total = self.session.query(func.count(ExactCacheEntry.prompt_hash)).scalar() or 0
        total_hits = self.session.query(func.sum(ExactCacheEntry.hit_count)).scalar() or 0
        top = (
            self.session.query(ExactCacheEntry)
            .order_by(ExactCacheEntry.hit_count.desc())
            .limit(5)
            .all()
        )
        return {
            "total_entries": total,
            "total_hits": total_hits,
            "top_entries": [
                {
                    "id": e.prompt_hash,
                    "response_preview": e.response_text[:60],
                    "hit_count": e.hit_count or 0,
                    "last_hit_at": e.last_hit_at,
                }
                for e in top
            ],
        }

    def clear(self, task_type: Optional[str] = None, older_than_days: Optional[int] = None) -> int:
        query = self.session.query(ExactCacheEntry)
        if task_type:
            query = query.filter(ExactCacheEntry.task_type == task_type)
        if older_than_days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
            query = query.filter(ExactCacheEntry.created_at < cutoff)
        entries = query.all()
        count = len(entries)
        for e in entries:
            self.session.delete(e)
        self.session.commit()
        return count


class SemanticCacheBackend(BaseCache):
    """Adapter over the existing similarity-search cache.

    All heavy imports (qdrant-client via SemanticCache.__init__, and
    sentence-transformers via embeddings) happen here and only here, so the
    default exact/off path stays free of the ML/vector stack. Behavior of the
    underlying SemanticCache is unchanged; this only owns prompt embedding so
    the cache interface can be prompt-keyed like ExactCache.
    """

    def __init__(
        self,
        session: Session,
        home: Path,
        similarity_threshold: float = 0.92,
        task_thresholds: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        try:
            from core.semantic_cache import SemanticCache  # lazy: pulls qdrant-client
        except ModuleNotFoundError as exc:
            raise MissingFeatureError(
                "cache",
                'semantic cache requires a vector backend. Install the light backend: '
                'pip install "orchestrator-cli[cache]"  (or the heavy backend: '
                'pip install "orchestrator-cli[heavy-cache]"). Or set [cache] mode = "exact".',
            ) from exc
        self._inner = SemanticCache(
            qdrant_path=home / "qdrant",
            sqlite_session=session,
            similarity_threshold=similarity_threshold,
            task_thresholds=task_thresholds or {},
        )
        self._embed_cache: dict[str, list[float]] = {}

    def _embed(self, prompt: str) -> list[float]:
        if prompt not in self._embed_cache:
            try:
                from embeddings.embedder import embed  # lazy: pulls sentence-transformers/torch
            except ModuleNotFoundError as exc:
                raise MissingFeatureError(
                    "cache",
                    'semantic cache needs an embedding backend. Install: '
                    'pip install "orchestrator-cli[cache]"  (FastEmbed, no PyTorch) or '
                    'pip install "orchestrator-cli[heavy-cache]". Or set [cache] mode = "exact".',
                ) from exc
            # Keep only the latest prompt's vector: one route embeds once.
            self._embed_cache = {prompt: embed(prompt)}
        return self._embed_cache[prompt]

    def lookup(self, prompt: str, task_type: str, quality: str) -> Optional[CacheResult]:
        return self._inner.lookup(self._embed(prompt), task_type, quality)

    def store(self, prompt, task_type, quality, response_text, provider, model_id, input_tokens, output_tokens) -> None:
        self._inner.store(
            embedding=self._embed(prompt),
            task_type=task_type,
            quality=quality,
            response_text=response_text,
            provider=provider,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def stats(self) -> dict:
        return self._inner.stats()

    def clear(self, task_type: Optional[str] = None, older_than_days: Optional[int] = None) -> int:
        return self._inner.clear(task_type=task_type, older_than_days=older_than_days)

    def get_entry(self, entry_id: str):
        return self._inner.get_entry(entry_id)

    def close(self) -> None:
        self._inner.close()


def get_cache(config: dict, session: Session, home: Path) -> BaseCache:
    """Build the cache backend from config. Default mode is exact."""
    cache_cfg = config.get("cache", {}) if config else {}
    if not cache_cfg.get("enabled", True):
        return NoOpCache()

    mode = (cache_cfg.get("mode") or "exact").lower()
    ttl_seconds = cache_cfg.get("ttl_seconds")

    if mode == "off":
        return NoOpCache()
    if mode == "semantic":
        return SemanticCacheBackend(
            session=session,
            home=home,
            similarity_threshold=cache_cfg.get("similarity_threshold", 0.92),
            task_thresholds=cache_cfg.get("task_thresholds", {}),
            ttl_seconds=ttl_seconds,
        )
    # "exact" and any unknown value default to the safe exact cache.
    return ExactCache(session, ttl_seconds=ttl_seconds)
