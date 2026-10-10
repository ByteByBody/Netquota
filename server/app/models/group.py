"""Groups and historical group assignments."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import BaseMixin


class Group(BaseMixin, Base):
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Day of month the quota period resets (1-28).
    reset_day: Mapped[int] = mapped_column(default=1)
    # Convenience default used when creating new quota periods.
    default_quota_bytes: Mapped[int] = mapped_column(BigInteger, default=0)


class GroupAssignment(BaseMixin, Base):
    """Time-bounded membership of a device in a group.

    Historical attribution is preserved: when a device changes groups the old
    row's ``valid_until`` is closed and a new open row is created.  Usage deltas
    reference the assignment that was active when the sample was recorded.
    """

    __tablename__ = "group_assignments"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    # The quota period that was active when this assignment opened.
    quota_period_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("quota_periods.id", ondelete="SET NULL")
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_group_assign_device_open", "device_id", "valid_until"),
        Index("ix_group_assign_group", "group_id"),
    )