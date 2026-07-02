"""Pydantic schemas for route requests and results."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class RouteRequest(BaseModel):
    prompt: str
    task_type: Optional[str] = None        # auto-classified if None
    quality: str = "balanced"              # 'cheap' | 'balanced' | 'best'
    dry_run: bool = False
    policy: Optional[str] = None           # routing policy name; None -> cheapest-capable default
    task_set: Optional[str] = None         # scope a scorecard-aware policy to one task set


class RouteResult(BaseModel):
    task_type: str
    route_reason: str
    provider: Optional[str]
    model_id: Optional[str]
    cache_hit: bool
    cache_similarity: Optional[float]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost_usd: float
    latency_ms: Optional[int]
    response_text: Optional[str]
    status: str = "ok"
    error_message: Optional[str] = None
    route_explanation: Optional[str] = None   # set only for non-default policies
