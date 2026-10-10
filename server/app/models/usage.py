"""Raw usage samples and calculated usage deltas."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import BaseMixin


class UsageSample(BaseMixin, Base):
    """An original cumulative counter observation from an agent.

    ``received``/``sent`` totals are the raw values the agent read from the OS.
    """

    __tablename__ = "usage_samples"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interface_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bytes_received_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bytes_sent_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    measurement_scope: Mapped[str] = mapped_column(String(32), default="unknown")
    measurement_quality: Mapped[str] = mapped_column(String(32), default="unknown")
    # True when the agent reported a counter reset for this interface this cycle.
    reset_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "device_id", "sequence", "interface_name", name="uq_sample_device_sequence"
        ),
        Index("ix_sample_device_iface", "device_id", "interface_name", "sequence"),
    )


class UsageDelta(BaseMixin, Base):
    """Traffic attributable to a (device, group, quota_period) tuple.

    One delta row per accepted sample.  ``sample_id`` is unique so retries of the
    same sample can never create a second delta.
    """

    __tablename__ = "usage_deltas"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="SET NULL")
    )
    quota_period_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("quota_periods.id", ondelete="SET NULL")
    )
    sample_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("usage_samples.id", ondelete="CASCADE"), nullable=False
    )
    received_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sent_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # True when this delta absorbed a counter reset (previous counter discarded).
    from_reset: Mapped[bool] = mapped_column(Boolean, default=False)
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("sample_id", name="uq_delta_sample"),
        Index("ix_delta_device_recorded", "device_id", "recorded_at"),
        Index("ix_delta_group_recorded", "group_id", "recorded_at"),
        Index("ix_delta_period", "quota_period_id"),
    )