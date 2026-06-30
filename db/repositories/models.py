"""CRUD for model_registry table.

Model identity is source-endpoint-qualified. The dedup/upsert key is
(source_key, external_model_id), where source_key is the account's normalized
base_url for local / OpenAI-compatible sources, and the provider name for cloud
providers (which have no base_url). This keeps cloud behavior unchanged: the
same cloud provider connected twice still collapses to one model. It also fixes
the real collision: two local endpoints exposing the same model name stay
distinct. base_url already lives on ConnectedAccount, so no schema change is
needed, and routing still resolves the endpoint through model.account_id.
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from db.models import ModelRegistry, ConnectedAccount


# Metadata refreshed on re-sync. The source-qualified identity and the surrogate
# id / account_id are NOT in this list.
_MUTABLE_FIELDS = (
    "display_name", "tier", "context_window", "cost_per_1m_input",
    "cost_per_1m_output", "supports_json", "supports_tools",
    "supports_vision", "enabled",
)


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _source_key(session: Session, account_id: Optional[str], provider: str) -> str:
    """Identity scope for a model: the account's base_url for local/custom
    sources, or the provider name for cloud providers (which have no base_url)."""
    if account_id:
        account = session.get(ConnectedAccount, account_id)
        if account is not None and account.base_url:
            return _normalize_base_url(account.base_url)
    return provider


def _row_source_key(session: Session, row: ModelRegistry) -> str:
    return _source_key(session, row.account_id, row.provider)


def upsert_models(session: Session, models: list[ModelRegistry]) -> None:
    """Insert or update models keyed on (source_key, external_model_id).

    Each sync builds rows with fresh UUIDs; the lookup is on the logical
    source-qualified identity, not the surrogate id, so re-syncing a source
    updates its rows in place instead of duplicating them. A matching row's id
    and account_id are preserved, keeping foreign keys and ownership intact.
    """
    for m in models:
        key = _source_key(session, m.account_id, m.provider)
        existing = _get_by_source_external_id(session, key, m.external_model_id)
        if existing is not None:
            for attr in _MUTABLE_FIELDS:
                setattr(existing, attr, getattr(m, attr))
        else:
            session.add(m)
    session.commit()


def list_enabled(session: Session) -> list[ModelRegistry]:
    """Enabled models, deduplicated by source-qualified identity
    (source_key, external_model_id). The earliest-discovered row per identity
    wins. Two local endpoints exposing the same model stay separate; the same
    cloud provider connected twice still collapses to one.
    """
    rows = (
        session.query(ModelRegistry)
        .filter_by(enabled=1)
        .order_by(
            ModelRegistry.provider,
            ModelRegistry.external_model_id,
            ModelRegistry.discovered_at,
        )
        .all()
    )
    seen: set[tuple[str, str]] = set()
    unique: list[ModelRegistry] = []
    for m in rows:
        key = (_row_source_key(session, m), m.external_model_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique


def list_for_account(session: Session, account_id: str) -> list[ModelRegistry]:
    return session.query(ModelRegistry).filter_by(account_id=account_id).all()


def get_by_external_id(session: Session, provider: str, external_id: str) -> Optional[ModelRegistry]:
    """Lookup by (provider, external_model_id). Kept for cloud callers and
    inspection. Source-qualified upsert uses the internal source-key lookup."""
    return (
        session.query(ModelRegistry)
        .filter_by(provider=provider, external_model_id=external_id)
        .first()
    )


def _get_by_source_external_id(
    session: Session, source_key: str, external_id: str
) -> Optional[ModelRegistry]:
    """Find an existing row whose source-qualified identity matches. Scans the
    rows sharing this external_model_id (a small set) and compares source keys."""
    candidates = session.query(ModelRegistry).filter_by(external_model_id=external_id).all()
    for row in candidates:
        if _row_source_key(session, row) == source_key:
            return row
    return None
