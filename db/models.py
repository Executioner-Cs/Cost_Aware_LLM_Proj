"""
SQLAlchemy ORM table definitions.
Source of truth: CLAUDE.md § SQLite schema
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    display_name = Column(String)
    email = Column(String)
    auth_method = Column(String, nullable=False)   # 'oauth' | 'pat' | 'session_cookie'
    encrypted_token = Column(Text, nullable=False)
    encrypted_refresh = Column(Text)
    token_expires_at = Column(String)
    plan = Column(String)
    status = Column(String, default="active")
    connected_at = Column(String, nullable=False)
    last_synced_at = Column(String)

    models = relationship("ModelRegistry", back_populates="account", cascade="all, delete-orphan")


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("connected_accounts.id"), nullable=True)
    provider = Column(String, nullable=False)
    external_model_id = Column(String, nullable=False)
    display_name = Column(String)
    tier = Column(String, nullable=False)          # 'small' | 'balanced' | 'large'
    context_window = Column(Integer)
    cost_per_1m_input = Column(Float)
    cost_per_1m_output = Column(Float)
    supports_json = Column(Integer, default=0)
    supports_tools = Column(Integer, default=0)
    supports_vision = Column(Integer, default=0)
    enabled = Column(Integer, default=1)
    discovered_at = Column(String, nullable=False)

    account = relationship("ConnectedAccount", back_populates="models")


class Trace(Base):
    __tablename__ = "traces"

    id = Column(String, primary_key=True)
    prompt_preview = Column(Text)
    task_type = Column(String)
    route_reason = Column(String)
    provider = Column(String)
    model_external_id = Column(String)
    cache_hit = Column(Integer, default=0)
    cache_similarity = Column(Float)               # cosine sim score, null on miss
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    estimated_cost_usd = Column(Float)
    latency_ms = Column(Integer)
    status = Column(String, default="ok")
    error_message = Column(Text)
    created_at = Column(String, nullable=False)


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(String, primary_key=True)          # uuid4, same as Qdrant point ID
    response_text = Column(Text, nullable=False)
    task_type = Column(String, nullable=False)
    quality = Column(String, nullable=False)
    provider = Column(String)
    model_id = Column(String)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    hit_count = Column(Integer, default=0)
    created_at = Column(String, nullable=False)
    last_hit_at = Column(String)
