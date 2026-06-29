"""SQLite payload CRUD for the legacy cache_entries table.

The legacy semantic cache that wrote this table was removed; the table is
retained so old data and the DB schema are preserved. This module now backs
only the `cache inspect` CLI/TUI command for inspecting any pre-existing rows.
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import CacheEntry


def get_by_id(session: Session, entry_id: str) -> Optional[CacheEntry]:
    return session.get(CacheEntry, entry_id)


def list_all(session: Session, limit: int = 50) -> list[CacheEntry]:
    return session.query(CacheEntry).order_by(CacheEntry.created_at.desc()).limit(limit).all()
