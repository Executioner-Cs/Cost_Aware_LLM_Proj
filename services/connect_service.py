"""
Service for connecting provider accounts.
Validates API key, discovers models, and persists to DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import ConnectedAccount, ModelRegistry
from db.repositories.accounts import create as create_account, get_by_provider
from db.repositories.models import upsert_models
from providers.base import ModelInfo
from utils.crypto import encrypt


_PROVIDER_CONNECTOR_MAP: dict[str, str] = {
    "anthropic": "providers.anthropic.connector.AnthropicConnector",
    "openai": "providers.openai.connector.OpenAIConnector",
}


def connect(session: Session, provider: str, api_key: str) -> ConnectedAccount:
    """
    Validate API key, pull model list, persist account + models.
    Returns the created ConnectedAccount.
    Raises ValueError on invalid key or unsupported provider.
    """
    provider = provider.lower()
    if provider not in _PROVIDER_CONNECTOR_MAP:
        raise ValueError(f"Unsupported provider '{provider}'. Supported: {list(_PROVIDER_CONNECTOR_MAP)}")

    connector = _load_connector(provider, api_key)

    if not connector.validate_key():
        raise ValueError(f"API key validation failed for provider '{provider}'")

    info = connector.whoami()
    models_info: list[ModelInfo] = connector.list_models()

    now = datetime.now(timezone.utc).isoformat()
    account_id = str(uuid.uuid4())

    account = ConnectedAccount(
        id=account_id,
        provider=provider,
        display_name=info.get("display_name"),
        email=info.get("email"),
        auth_method="pat",
        encrypted_token=encrypt(api_key),
        plan=info.get("plan"),
        status="active",
        connected_at=now,
        last_synced_at=now,
    )
    create_account(session, account)

    # Persist model registry
    orm_models = [
        ModelRegistry(
            id=str(uuid.uuid4()),
            account_id=account_id,
            provider=provider,
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

    return account


def _load_connector(provider: str, api_key: str):
    import importlib
    module_path, class_name = _PROVIDER_CONNECTOR_MAP[provider].rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(api_key)
