"""Re-export get_embedder for consumers that prefer this module path."""
from embeddings.embedder import get_embedder, embed

__all__ = ["get_embedder", "embed"]
