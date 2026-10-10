"""Enrollment schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EnrollmentCodeCreate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    ttl_minutes: int | None = Field(default=None, ge=1, le=1440)
    # Optionally pre-assign the enrolling device to a group.
    group_id: str | None = None


class EnrollmentCodeCreated(BaseModel):
    id: str
    code: str
    label: str | None = None
    expires_at: datetime
    group_id: str | None = None


class EnrollmentCodeOut(BaseModel):
    id: str
    label: str | None = None
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    used_by_device_id: str | None = None
    is_revoked: bool
    is_expired: bool


class EnrollInResponse(BaseModel):
    pass