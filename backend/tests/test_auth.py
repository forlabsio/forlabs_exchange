import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async def override_get_db():
        async with SessionLocal() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_nonce_returns_200(test_db):
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()
    with patch("app.routers.auth.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/auth/nonce?address=0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18")
            assert r.status_code == 200
            assert "nonce" in r.json()

@pytest.mark.asyncio
async def test_verify_creates_user(test_db):
    from eth_account import Account
    from eth_account.messages import encode_defunct

    acct = Account.create()
    nonce = "test-nonce-123"
    message = f"ForLabsEX Login\nNonce: {nonce}"
    msg = encode_defunct(text=message)
    signed = acct.sign_message(msg)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=nonce)
    mock_redis.delete = AsyncMock()

    with patch("app.routers.auth.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/auth/verify", json={
                "address": acct.address,
                "signature": signed.signature.hex(),
            })
            assert r.status_code == 200, r.text
            assert "access_token" in r.json()

@pytest.mark.asyncio
async def test_verify_invalid_signature(test_db):
    nonce = "test-nonce-456"
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=nonce)

    with patch("app.routers.auth.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/auth/verify", json={
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
                "signature": "0x" + "00" * 65,
            })
            assert r.status_code == 401

@pytest.mark.asyncio
async def test_me_with_valid_token(test_db):
    from eth_account import Account
    from eth_account.messages import encode_defunct

    acct = Account.create()
    nonce = "test-nonce-789"
    message = f"ForLabsEX Login\nNonce: {nonce}"
    msg = encode_defunct(text=message)
    signed = acct.sign_message(msg)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=nonce)
    mock_redis.delete = AsyncMock()

    with patch("app.routers.auth.get_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/auth/verify", json={
                "address": acct.address,
                "signature": signed.signature.hex(),
            })
            token = r.json()["access_token"]

            r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            assert r.json()["wallet_address"].lower() == acct.address.lower()
