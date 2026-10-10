"""Domain events: thresholds, staleness, enrollment, accounting warnings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import BaseMixin


class Event(BaseMixin, Base):
    __tablename__ = "events"

    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="SET NULL")
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="SET NULL")
    )
    quota_period_id: Mapped[str | None] = mapped_column(String(36))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str | None] = mapped_column(Text)
    # JSON-encoded structured detail.
    details_json: Mapped[str | None] = mapped_column(Text)
    # Key used to deduplicate threshold events within a period.
    dedupe_key: Mapped[str | None] = mapped_column(String(160), index=True)

    __table_args__ = (
        Index("ix_event_type_created", "event_type", "created_at"),
        Index("ix_event_group_created", "group_id", "created_at"),
    )