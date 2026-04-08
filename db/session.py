"""
SQLAlchemy session factory.
Uses SQLite at ORCHESTRATOR_HOME/orchestrator.db
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from db.models import Base


def get_db_path() -> Path:
    home = Path(os.environ.get("ORCHESTRATOR_HOME", Path.home() / ".orchestrator"))
    return home / "orchestrator.db"


def get_engine(db_path: Path | None = None):
    if db_path is None:
        db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


def create_all_tables(db_path: Path | None = None) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def make_session_factory(db_path: Path | None = None):
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session(db_path: Path | None = None) -> Session:
    """Return a new SQLAlchemy session (caller must close)."""
    factory = make_session_factory(db_path)
    return factory()
