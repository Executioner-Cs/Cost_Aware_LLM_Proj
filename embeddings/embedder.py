"""
Sentence-transformers embedding wrapper.
Model is loaded once (singleton via lru_cache) and reused across calls.
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load once (~200ms first call), reuse forever. ~22 MB model."""
    return SentenceTransformer(EMBEDDING_MODEL)


def embed(text: str) -> list[float]:
    """Return unit-normalised 384-dim embedding for *text*."""
    model = get_embedder()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
