"""Device schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DevicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    group_id: str | None = Field(default=None)
    is_active: bool | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    platform: str
    agent_version: str | None = None
    created_at: datetime
    last_seen_at: datetime | None = None
    is_active: bool
    measurement_scope: str
    measurement_quality: str
    last_sequence: int
    group_id: str | None = None
    group_name: str | None = None
    is_stale: bool = False


class DeviceDetailOut(DeviceOut):
    capabilities: dict = Field(default_factory=dict)
    current_period_received: int = 0
    current_period_sent: int = 0
    interfaces: list[str] = Field(default_factory=list)
    recent_warnings: list[str] = Field(default_factory=list)