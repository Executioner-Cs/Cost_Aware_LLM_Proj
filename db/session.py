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


def _ensure_account_columns(engine) -> None:
    """Add the ModelSource columns to an existing connected_accounts table.

    This repo has no migration framework and ``create_all`` cannot ALTER an
    existing table, so the nullable ``source_type`` / ``base_url`` columns are
    added in place. Idempotent and safe: it runs only when the table already
    exists and is missing them; brand-new DBs get the columns from create_all.
    """
    with engine.connect() as conn:
        info = conn.exec_driver_sql("PRAGMA table_info(connected_accounts)").fetchall()
        if not info:
            return  # table not created yet
        existing = {row[1] for row in info}
        if "source_type" not in existing:
            conn.exec_driver_sql("ALTER TABLE connected_accounts ADD COLUMN source_type VARCHAR")
        if "base_url" not in existing:
            conn.exec_driver_sql("ALTER TABLE connected_accounts ADD COLUMN base_url VARCHAR")
        conn.commit()


def get_engine(db_path: Path | None = None):
    if db_path is None:
        db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    _ensure_account_columns(engine)
    return engine


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
