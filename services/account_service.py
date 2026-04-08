"""Service for account management: list, sync, disconnect."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import ConnectedAccount
from db.repositories.accounts import list_all, get_by_id, delete, update
from db.repositories.models import upsert_models, list_for_account
import uuid


def list_accounts(session: Session) -> list[ConnectedAccount]:
    return list_all(session)


def sync_account(session: Session, account_id: str) -> ConnectedAccount:
    """Re-validate key + refresh model list for an account."""
    from services.connect_service import _load_connector
    from utils.crypto import decrypt
    from db.models import ModelRegistry

    account = get_by_id(session, account_id)
    if not account:
        raise ValueError(f"Account '{account_id}' not found")

    api_key = decrypt(account.encrypted_token)
    connector = _load_connector(account.provider, api_key)

    if not connector.validate_key():
        account.status = "invalid"
        update(session, account)
        raise ValueError(f"Key validation failed for account '{account_id}'")

    models_info = connector.list_models()
    now = datetime.now(timezone.utc).isoformat()

    orm_models = [
        ModelRegistry(
            id=str(uuid.uuid4()),
            account_id=account_id,
            provider=account.provider,
            external_model_id=m.external_model_id,
            display_name=m.display_name,
            tier=m.tier,
            context_window=m.context_window,
            cost_per_1m_input=m.cost_per_1m_input,
            cost_per_1m_output=m.cost_per_1m_output,
            supports_json=int(m.supports_json),
            supports_tools=int(m.supports_tools),
            supports_vision=int(m.supports_vision),
            enabled=1,
            discovered_at=now,
        )
        for m in models_info
    ]
    upsert_models(session, orm_models)

    account.last_synced_at = now
    update(session, account)
    return account


def disconnect_account(session: Session, account_id: str) -> None:
    account = get_by_id(session, account_id)
    if not account:
        raise ValueError(f"Account '{account_id}' not found")
    delete(session, account)
