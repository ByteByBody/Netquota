"""Device registration and enrollment codes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import BaseMixin, new_uuid


class Device(BaseMixin, Base):
    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    agent_version: Mapped[str | None] = mapped_column(String(64))
    # Hashed device credential (never store the raw credential).
    credential_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 hash of the *current* credential, indexed for fast lookup.
    credential_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Free-form measurement capability metadata supplied at enrollment.
    measurement_scope: Mapped[str] = mapped_column(String(32), default="unknown")
    measurement_quality: Mapped[str] = mapped_column(String(32), default="unknown")
    capabilities_json: Mapped[str | None] = mapped_column(Text)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_devices_platform", "platform"),
        Index("ix_devices_is_active", "is_active"),
    )


class EnrollmentCode(BaseMixin, Base):
    __tablename__ = "enrollment_codes"

    # Store only a hash of the single-use code.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(200))
    # Optional group the enrolling device is assigned to.
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    used_by_device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="SET NULL")
    )
    created_by_admin_id: Mapped[str | None] = mapped_column(String(36))
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_enrollment_expires", "expires_at"),)