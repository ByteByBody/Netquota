"""Dashboard summary endpoint (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...models import AdminUser
from ...schemas.dashboard import DashboardSummary
from ...security.deps import get_current_admin
from ...services.dashboard import build_summary

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    summary = await build_summary(session)
    await session.commit()
    return summary