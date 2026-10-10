"""Revocable administrator sessions (supports JWT revocation)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import BaseMixin


class AdminSession(BaseMixin, Base):
    __tablename__ = "admin_sessions"

    admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False
    )
    # Hash of the JWT id (jti); lets us revoke a session without storing the token.
    token_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (Index("ix_admin_session_admin", "admin_id"),)