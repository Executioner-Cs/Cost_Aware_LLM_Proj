"""
Sentence-transformers embedding wrapper.
Model is loaded once (singleton via lru_cache) and reused across calls.
"""
from __future__ import annotations

from functools import lru_cache

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def get_embedder():
    """Load once (~200ms first call), reuse forever. ~22 MB model.

    sentence-transformers (and its torch stack) is imported here, lazily, so
    that importing this module costs nothing until an embedding is actually
    needed (semantic cache only). Belongs to the optional heavy-cache extra.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed(text: str) -> list[float]:
    """Return unit-normalised 384-dim embedding for *text*."""
    model = get_embedder()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
