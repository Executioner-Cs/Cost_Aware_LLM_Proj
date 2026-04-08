"""Service for listing models from the registry."""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import ModelRegistry
from db.repositories.models import list_enabled


def list_models(session: Session) -> list[ModelRegistry]:
    return list_enabled(session)
