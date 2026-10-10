"""Administrator authentication schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AdminOut(BaseModel):
    id: str
    username: str
    created_at: datetime
    last_login_at: datetime | None = None