"""Group and usage schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    reset_day: int = Field(default=1, ge=1, le=28)
    quota_bytes: int | None = Field(default=None, ge=0)
    device_ids: list[str] = Field(default_factory=list)


class GroupPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    reset_day: int | None = Field(default=None, ge=1, le=28)
    quota_bytes: int | None = Field(default=None, ge=0)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    reset_day: int
    device_count: int = 0


class UsagePoint(BaseModel):
    bucket: date
    received_bytes: int
    sent_bytes: int
    total_bytes: int


class GroupQuotaSummary(BaseModel):
    group_id: str
    group_name: str
    quota_bytes: int
    used_bytes: int
    remaining_bytes: int
    percentage_used: float
    period_starts_at: datetime | None = None
    period_ends_at: datetime | None = None
    device_count: int = 0
    highest_threshold: int | None = None
    measurement_quality: str = "unknown"
    has_missing_measurements: bool = False


class GroupUsageOut(BaseModel):
    group_id: str
    group_name: str
    summary: GroupQuotaSummary
    series: list[UsagePoint] = Field(default_factory=list)


class GroupUsageSeries(BaseModel):
    group_id: str
    granularity: str
    series: list[UsagePoint] = Field(default_factory=list)