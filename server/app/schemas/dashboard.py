"""Dashboard aggregate schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .groups import GroupQuotaSummary, UsagePoint


class DeviceHealth(BaseModel):
    id: str
    name: str
    platform: str
    group_name: str | None = None
    last_seen_at: datetime | None = None
    minutes_since_report: int | None = None
    measurement_quality: str = "unknown"


class DashboardSummary(BaseModel):
    generated_at: datetime
    active_period_starts_at: datetime | None = None
    active_period_ends_at: datetime | None = None

    device_count: int
    reporting_device_count: int
    stale_device_count: int
    revoked_device_count: int

    total_received_bytes: int
    total_sent_bytes: int
    total_bytes: int

    groups: list[GroupQuotaSummary] = Field(default_factory=list)
    recent_events: list[dict] = Field(default_factory=list)
    stale_devices: list[DeviceHealth] = Field(default_factory=list)
    measurement_warnings: list[str] = Field(default_factory=list)
    usage_series: list[UsagePoint] = Field(default_factory=list)