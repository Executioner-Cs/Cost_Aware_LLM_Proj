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
    auth_method = Column(String, nullable=False)   # 'oauth' | 'pat' | 'session_cookie' | 'none'
    encrypted_token = Column(Text, nullable=True)  # nullable: local/keyless sources (e.g. Ollama) have no key
    encrypted_refresh = Column(Text)
    token_expires_at = Column(String)
    plan = Column(String)
    status = Column(String, default="active")
    connected_at = Column(String, nullable=False)
    last_synced_at = Column(String)
    # ModelSource fields. Cloud providers leave these defaulted; local and
    # OpenAI-compatible sources set source_type and a base_url endpoint.
    source_type = Column(String, default="cloud")
    base_url = Column(String)

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


class ToolCall(Base):
    """Structured log of agent/orchestrator tool invocations."""
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True)
    trace_id = Column(String, ForeignKey("traces.id"), nullable=True)
    name = Column(String, nullable=False)
    args_json = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
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


class ExactCacheEntry(Base):
    """Exact-match cache keyed by sha256(normalized_prompt + task_type + quality).

    Separate table from cache_entries (which is the semantic/Qdrant-linked store)
    so that ``Base.metadata.create_all`` provisions it on existing databases
    without a migration: create_all adds missing tables but never alters or adds
    columns to an existing one. No vectors are stored here.
    """
    __tablename__ = "exact_cache"

    prompt_hash = Column(String, primary_key=True)   # sha256 hex; primary key is indexed
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


class TaskSet(Base):
    """A user-owned set of representative tasks to benchmark models on."""
    __tablename__ = "task_sets"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(String, nullable=False)

    tasks = relationship("BenchmarkTask", back_populates="task_set", cascade="all, delete-orphan")


class BenchmarkTask(Base):
    """One task in a TaskSet: a prompt plus how to grade the response."""
    __tablename__ = "benchmark_tasks"

    id = Column(String, primary_key=True)
    task_set_id = Column(String, ForeignKey("task_sets.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    expected = Column(Text)                          # for exact / contains graders
    grader = Column(String, default="contains")      # 'exact' | 'contains' | 'json_valid'
    task_type = Column(String, default="simple")
    created_at = Column(String, nullable=False)

    task_set = relationship("TaskSet", back_populates="tasks")


class BenchmarkRun(Base):
    """One execution of a TaskSet across selected models."""
    __tablename__ = "benchmark_runs"

    id = Column(String, primary_key=True)
    task_set_id = Column(String, ForeignKey("task_sets.id"), nullable=False)
    status = Column(String, default="completed")
    created_at = Column(String, nullable=False)

    scorecards = relationship("Scorecard", back_populates="run", cascade="all, delete-orphan")


class Scorecard(Base):
    """Local per-model result for one BenchmarkRun.

    Deterministic scoring only (exact / contains / json_valid); no hosted service
    and no LLM-as-judge in this version. ``score`` is the task pass rate in [0, 1].
    """
    __tablename__ = "scorecards"

    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("benchmark_runs.id"), nullable=False)
    task_set_id = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    model_id = Column(String, nullable=False)
    tasks_total = Column(Integer, default=0)
    tasks_passed = Column(Integer, default=0)
    score = Column(Float, default=0.0)               # pass rate in [0, 1]
    avg_latency_ms = Column(Float)
    avg_cost_usd = Column(Float)
    created_at = Column(String, nullable=False)

    run = relationship("BenchmarkRun", back_populates="scorecards")
