"""Shared pytest fixtures.

Uses a temporary SQLite database so the suite runs without PostgreSQL. The
production database is PostgreSQL (see deployment/docker-compose.yml).
"""

from __future__ import annotations

import os
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="netquota-test-")
os.environ["NETQUOTA_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/test.db"
os.environ["NETQUOTA_JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD"] = "test-admin-pass"
os.environ["NETQUOTA_STALE_AFTER_MINUTES"] = "30"

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402
from app.security.ratelimit import reset_rate_limits  # noqa: E402
from app.timeutil import utcnow  # noqa: E402


@pytest.fixture(autouse=True)
async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    reset_rate_limits()
    async with SessionLocal() as session:
        session.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("test-admin-pass"),
                created_at=utcnow(),
                is_active=True,
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c


@pytest.fixture
async def admin_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "test-admin-pass"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}