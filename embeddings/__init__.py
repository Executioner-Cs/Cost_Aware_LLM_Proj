"""Embedding helpers, exposed lazily.

Importing this package must NOT import sentence-transformers (and its torch
stack). Attributes resolve on first access via PEP 562 ``__getattr__`` so the
default exact-cache route path stays free of the ML dependencies.
"""
from __future__ import annotations

__all__ = ["get_embedder", "embed"]


def __getattr__(name: str):
    if name in __all__:
        from embeddings import embedder
        return getattr(embedder, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
