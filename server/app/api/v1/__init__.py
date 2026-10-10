"""Aggregate API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from . import admin_auth, agents, dashboard, devices, enrollment, events, groups, system

api_router = APIRouter()

api_router.include_router(system.router, tags=["system"])
api_router.include_router(enrollment.router, tags=["enrollment"])
api_router.include_router(agents.router, tags=["agent"])
api_router.include_router(admin_auth.router, tags=["auth"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(devices.router, tags=["devices"])
api_router.include_router(groups.router, tags=["groups"])
api_router.include_router(events.router, tags=["events"])