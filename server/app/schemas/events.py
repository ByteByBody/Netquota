"""Event schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    id: str
    event_type: str
    created_at: datetime
    device_id: str | None = None
    group_id: str | None = None
    quota_period_id: str | None = None
    severity: str
    message: str | None = None
    details: dict = Field(default_factory=dict)