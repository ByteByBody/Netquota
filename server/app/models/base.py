"""Shared model mixins and UUID helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


def new_uuid() -> str:
    return str(uuid.uuid4())


class BaseMixin:
    """Adds a UUID primary key.

    UUIDs are stored as 36-char strings for portability across SQLite and
    PostgreSQL (no native UUID type needed).
    """

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)