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
from providers.source import get_model_source
from utils.crypto import encrypt


_PROVIDER_CONNECTOR_MAP: dict[str, str] = {
    "anthropic": "providers.anthropic.connector.AnthropicConnector",
    "openai": "providers.openai.connector.OpenAIConnector",
    "groq": "providers.groq.connector.GroqConnector",
    "gemini": "providers.gemini.connector.GeminiConnector",
}

# Provider names that map to non-cloud source types (base_url, no fixed SDK).
_SOURCE_TYPE_BY_PROVIDER: dict[str, str] = {
    "ollama": "ollama",
    "openai-compatible": "openai_compatible",
    "openai_compatible": "openai_compatible",
}


def connect(
    session: Session,
    provider: str,
    api_key: str,
    *,
    base_url: str | None = None,
) -> ConnectedAccount:
    """
    Discover models and persist an account + its models.

    Cloud providers validate an API key via their connector. Source types
    (ollama, openai-compatible) discover models over HTTP at ``base_url``; a key
    is optional (ollama is keyless). Returns the created ConnectedAccount.
    Raises ValueError on invalid key, unreachable source, or unsupported name.
    """
    provider = provider.lower()
    source_type = _SOURCE_TYPE_BY_PROVIDER.get(provider, "cloud")
    now = datetime.now(timezone.utc).isoformat()
    account_id = str(uuid.uuid4())

    if source_type == "cloud":
        if provider not in _PROVIDER_CONNECTOR_MAP:
            raise ValueError(f"Unsupported provider '{provider}'. Supported: {list(_PROVIDER_CONNECTOR_MAP)}")
        connector = _load_connector(provider, api_key)
        if not connector.validate_key():
            raise ValueError(f"API key validation failed for provider '{provider}'")
        info = connector.whoami()
        models_info: list[ModelInfo] = connector.list_models()
        display_name = info.get("display_name")
        email = info.get("email")
        plan = info.get("plan")
        auth_method = "pat"
        encrypted_token = encrypt(api_key)
    else:
        if not base_url and source_type == "ollama":
            from providers.ollama import DEFAULT_BASE_URL
            base_url = DEFAULT_BASE_URL
        if not base_url:
            raise ValueError(
                f"Source '{provider}' requires --base-url (for example http://localhost:8000/v1)."
            )
        # Heads-up: the model registry keys identity by (provider, external_model_id),
        # so two local endpoints of the same provider that expose a same-named model
        # collide in the registry today. One endpoint per local provider is the
        # supported configuration until source-qualified model identity lands.
        existing_local = [a for a in get_by_provider(session, provider) if (a.source_type or "cloud") != "cloud"]
        if existing_local:
            from utils.console import print_warning
            print_warning(
                f"Another '{provider}' source is already connected. Models sharing a name "
                f"across endpoints can collide in the registry; use one endpoint per local "
                f"provider until source-qualified model identity lands."
            )
        source = get_model_source(provider, source_type=source_type, base_url=base_url)
        try:
            models_info = source.list_models(api_key or "")
        except Exception as exc:
            raise ValueError(f"Could not reach source '{provider}' at {base_url}: {exc}") from exc
        display_name = f"{provider} @ {base_url}"
        email = None
        plan = None
        auth_method = "pat" if api_key else "none"
        encrypted_token = encrypt(api_key) if api_key else None

    account = ConnectedAccount(
        id=account_id,
        provider=provider,
        display_name=display_name,
        email=email,
        auth_method=auth_method,
        encrypted_token=encrypted_token,
        plan=plan,
        status="active",
        connected_at=now,
        last_synced_at=now,
        source_type=source_type,
        base_url=base_url,
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
