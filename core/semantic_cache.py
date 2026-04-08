"""
Semantic cache: Qdrant (vector lookup) + SQLite (payload store).

Architecture:
  - Qdrant stores 384-dim embeddings + lightweight payload (sqlite_id, task_type, quality)
  - SQLite stores full response text + metadata keyed by sqlite_id
  - A hit requires: cosine similarity >= threshold AND exact task_type + quality match
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from db.models import CacheEntry


COLLECTION = "semantic_cache"


@dataclass
class CacheResult:
    entry_id: str
    response_text: str
    similarity: float
    provider: Optional[str]
    model_id: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]


class SemanticCache:
    def __init__(
        self,
        qdrant_path: Path,
        sqlite_session: Session,
        similarity_threshold: float = 0.92,
        task_thresholds: Optional[dict[str, float]] = None,
    ) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._threshold = similarity_threshold
        self._task_thresholds: dict[str, float] = task_thresholds or {}
        self.session = sqlite_session
        self.qdrant = QdrantClient(path=str(qdrant_path))
        self._ensure_collection()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def lookup(
        self,
        embedding: list[float],
        task_type: str,
        quality: str,
    ) -> Optional[CacheResult]:
        """Return CacheResult on hit, None on miss."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        threshold = self._task_thresholds.get(task_type, self._threshold)

        results = self.qdrant.search(
            collection_name=COLLECTION,
            query_vector=embedding,
            query_filter=Filter(
                must=[
                    FieldCondition(key="task_type", match=MatchValue(value=task_type)),
                    FieldCondition(key="quality", match=MatchValue(value=quality)),
                ]
            ),
            limit=1,
            score_threshold=threshold,
            with_payload=True,
        )

        if not results:
            return None

        hit = results[0]
        sqlite_id = hit.payload["sqlite_id"]  # type: ignore[index]

        entry = self.session.get(CacheEntry, sqlite_id)
        if entry is None:
            return None

        # Update hit stats
        entry.hit_count = (entry.hit_count or 0) + 1
        entry.last_hit_at = _now()
        self.session.commit()

        return CacheResult(
            entry_id=entry.id,
            response_text=entry.response_text,
            similarity=hit.score,
            provider=entry.provider,
            model_id=entry.model_id,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
        )

    def store(
        self,
        embedding: list[float],
        task_type: str,
        quality: str,
        response_text: str,
        provider: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Write vector to Qdrant + payload to SQLite."""
        from qdrant_client.models import PointStruct

        entry_id = str(uuid.uuid4())
        now = _now()

        # SQLite write
        entry = CacheEntry(
            id=entry_id,
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
        self.session.commit()

        # Qdrant write
        self.qdrant.upsert(
            collection_name=COLLECTION,
            points=[
                PointStruct(
                    id=entry_id,
                    vector=embedding,
                    payload={
                        "sqlite_id": entry_id,
                        "task_type": task_type,
                        "quality": quality,
                        "created_at": now,
                    },
                )
            ],
        )

    def stats(self) -> dict:
        """Return basic cache statistics for CLI display."""
        from sqlalchemy import func, text

        total = self.session.query(func.count(CacheEntry.id)).scalar() or 0
        total_hits = self.session.query(func.sum(CacheEntry.hit_count)).scalar() or 0
        top_entries = (
            self.session.query(CacheEntry)
            .order_by(CacheEntry.hit_count.desc())
            .limit(5)
            .all()
        )
        return {
            "total_entries": total,
            "total_hits": total_hits,
            "top_entries": [
                {
                    "id": e.id,
                    "response_preview": e.response_text[:60],
                    "hit_count": e.hit_count or 0,
                    "last_hit_at": e.last_hit_at,
                }
                for e in top_entries
            ],
        }

    def clear(
        self,
        task_type: Optional[str] = None,
        older_than_days: Optional[int] = None,
    ) -> int:
        """Delete matching cache entries from both Qdrant and SQLite. Returns count deleted."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query = self.session.query(CacheEntry)
        if task_type:
            query = query.filter(CacheEntry.task_type == task_type)
        if older_than_days is not None:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
            query = query.filter(CacheEntry.created_at < cutoff)

        entries = query.all()
        ids = [e.id for e in entries]

        for entry in entries:
            self.session.delete(entry)
        self.session.commit()

        if ids:
            self.qdrant.delete(
                collection_name=COLLECTION,
                points_selector=ids,
            )

        return len(ids)

    def get_entry(self, entry_id: str) -> Optional[CacheEntry]:
        return self.session.get(CacheEntry, entry_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        collections = {c.name for c in self.qdrant.get_collections().collections}
        if COLLECTION not in collections:
            self.qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def close(self) -> None:
        self.qdrant.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
