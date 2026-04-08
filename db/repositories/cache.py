"""SQLite payload CRUD for cache_entries table.
Note: semantic_cache.py is the only caller from the routing path.
This module provides direct access for CLI inspection commands.
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import CacheEntry


def get_by_id(session: Session, entry_id: str) -> Optional[CacheEntry]:
    return session.get(CacheEntry, entry_id)


def list_all(session: Session, limit: int = 50) -> list[CacheEntry]:
    return session.query(CacheEntry).order_by(CacheEntry.created_at.desc()).limit(limit).all()
