"""Pydantic schemas for traces."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class TraceOut(BaseModel):
    id: str
    prompt_preview: Optional[str]
    task_type: Optional[str]
    route_reason: Optional[str]
    provider: Optional[str]
    model_external_id: Optional[str]
    cache_hit: int
    cache_similarity: Optional[float]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost_usd: Optional[float]
    latency_ms: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}
