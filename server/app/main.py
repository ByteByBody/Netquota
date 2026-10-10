"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .api.v1 import api_router
from .config import get_settings
from .database import Base, SessionLocal, engine
from .models import AdminUser
from .models.enums import EventType
from .security.passwords import hash_password
from .services.events import emit_event
from .timeutil import utcnow

logger = logging.getLogger("netquota")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def bootstrap_admin() -> None:
    settings = get_settings()
    if not settings.admin_bootstrap_password:
        return
    async with SessionLocal() as session:
        existing = await session.scalar(select(AdminUser).limit(1))
        if existing is not None:
            return
        session.add(
            AdminUser(
                username=settings.admin_bootstrap_username,
                password_hash=hash_password(settings.admin_bootstrap_password),
                created_at=utcnow(),
            )
        )
        await session.commit()
        logger.warning(
            "Bootstrapped administrator '%s'. Change the password after first login.",
            settings.admin_bootstrap_username,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bootstrap_admin()
    async with SessionLocal() as session:
        await emit_event(
            session, EventType.SERVER_STARTED, message="NetQuota server started"
        )
        await session.commit()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="NetQuota API",
        version="1.0.0",
        description=(
            "Internet usage and group quota management. Totals are "
            "device-reported usage, not guaranteed ISP-billed usage."
        ),
        lifespan=lifespan,
    )

    # Dashboard is served from a separate origin in development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", include_in_schema=False)
    async def root_health() -> dict:
        return {"status": "ok", "service": "netquota"}

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()