"""Pydantic schemas for accounts."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class AccountOut(BaseModel):
    id: str
    provider: str
    display_name: Optional[str]
    email: Optional[str]
    auth_method: str
    plan: Optional[str]
    status: str
    connected_at: str
    last_synced_at: Optional[str]

    model_config = {"from_attributes": True}
