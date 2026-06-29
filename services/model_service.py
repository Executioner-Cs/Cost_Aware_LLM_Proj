"""Service for listing models from the registry."""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import ModelRegistry
from db.repositories.models import list_enabled
from providers.source import ModelSource, available_sources


def list_models(session: Session) -> list[ModelRegistry]:
    return list_enabled(session)


def list_sources() -> list[ModelSource]:
    """Registered model sources. Today these wrap the cloud providers; later
    branches register local / OpenAI-compatible / gateway sources here."""
    return available_sources()
