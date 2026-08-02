import os
import ssl
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
import httpx
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

import app.models.user  # noqa: F401
import app.models.purchase_history  # noqa: F401
import app.models.verdict_history  # noqa: F401
import app.models.agent_result  # noqa: F401

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

_raw_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
if not _raw_url:
    pytest.skip("No DATABASE_URL configured — skipping integration tests", allow_module_level=True)


def _make_async_url(url: str) -> tuple[str, dict]:
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    needs_ssl = any(k in ("sslmode", "channel_binding") for k, _ in query)
    cleaned = [(k, v) for k, v in query if k not in ("sslmode", "channel_binding")]
    cleaned_qs = urlencode(cleaned)
    base = url.split("?")[0]
    final_url = f"{base}?{cleaned_qs}" if cleaned_qs else base
    connect_args = {"ssl": ssl.create_default_context()} if needs_ssl else {}
    return final_url, connect_args


_async_url, _connect_args = _make_async_url(_raw_url)

pytestmark = pytest.mark.asyncio

SIGNUP_PAYLOAD = {
    "name": "Test User",
    "email": "test@example.com",
    "password": "securepass123",
    "monthly_income": 80000,
    "monthly_savings_target": 20000,
    "active_emis": 5000,
    "recurring_bills": 10000,
}


@pytest.fixture(autouse=True)
async def _setup_db():
    engine = create_async_engine(_async_url, echo=False, connect_args=_connect_args)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = override_get_db

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
    fastapi_app.dependency_overrides.pop(get_db, None)


async def signup(client: httpx.AsyncClient) -> dict:
    resp = await client.post("/auth/signup", json=SIGNUP_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


async def login(client: httpx.AsyncClient) -> dict:
    resp = await client.post("/auth/login", json={
        "email": SIGNUP_PAYLOAD["email"],
        "password": SIGNUP_PAYLOAD["password"],
    })
    assert resp.status_code == 200
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestSignupAndLogin:
    async def test_signup_returns_token_and_user(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            data = await signup(c)
            assert "access_token" in data
            assert data["user"]["email"] == SIGNUP_PAYLOAD["email"]
            assert data["user"]["name"] == SIGNUP_PAYLOAD["name"]

    async def test_duplicate_signup_returns_409(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            await signup(c)
            resp = await c.post("/auth/signup", json=SIGNUP_PAYLOAD)
            assert resp.status_code == 409

    async def test_login_returns_token(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            await signup(c)
            data = await login(c)
            assert "access_token" in data
            assert data["user"]["email"] == SIGNUP_PAYLOAD["email"]

    async def test_login_wrong_password_returns_401(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            await signup(c)
            resp = await c.post("/auth/login", json={
                "email": SIGNUP_PAYLOAD["email"],
                "password": "wrongpassword",
            })
            assert resp.status_code == 401


class TestJWTProtectedRoutes:
    async def test_purchase_history_rejects_unauthenticated(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            resp = await c.get("/api/v1/purchase-history")
            assert resp.status_code == 401

    async def test_purchase_history_rejects_invalid_token(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            resp = await c.get("/api/v1/purchase-history", headers=auth_headers("not-a-jwt"))
            assert resp.status_code == 401


class TestPurchaseHistoryCRUD:
    async def test_create_and_list_purchase_history(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            token = (await signup(c))["access_token"]
            headers = auth_headers(token)

            create_resp = await c.post("/api/v1/purchase-history", json={
                "product_name": "MacBook Air M3",
                "product_category": "Laptops",
                "purchase_price": 114900,
                "status": "STILL_USING_HAPPY",
                "regret_score": 10,
            }, headers=headers)
            assert create_resp.status_code == 201
            created = create_resp.json()
            assert created["product_name"] == "MacBook Air M3"
            assert created["purchase_price"] == 114900
            assert created["is_returned"] is False
            assert created["is_resold"] is False

            list_resp = await c.get("/api/v1/purchase-history", headers=headers)
            assert list_resp.status_code == 200
            items = list_resp.json()
            assert len(items) == 1
            assert items[0]["id"] == created["id"]

    async def test_create_purchase_history_returned_status(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
            token = (await signup(c))["access_token"]
            headers = auth_headers(token)

            resp = await c.post("/api/v1/purchase-history", json={
                "product_name": "Bad Headphones",
                "product_category": "Headphones",
                "purchase_price": 3000,
                "status": "RETURNED",
                "regret_score": 90,
            }, headers=headers)
            assert resp.status_code == 201
            assert resp.json()["is_returned"] is True
