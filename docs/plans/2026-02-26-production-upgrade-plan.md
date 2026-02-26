# ForLabsEX Production Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade ForLabsEX from paper-trading to production: MetaMask auth, real Binance trading, Polygon USDT subscription payments, admin subscription management, Railway Singapore deployment.

**Architecture:** Replace email/password auth with MetaMask EIP-191 signature verification. Bot runner executes real Binance market orders via operator's API keys. Subscriptions require Polygon USDT payment verified on-chain. Admin panel gets subscription management tab.

**Tech Stack:** FastAPI, SQLAlchemy async, eth-account, httpx (Binance API), Next.js 16, Tailwind v4, Zustand, MetaMask (window.ethereum)

**CRITICAL: DO NOT MODIFY** `frontend/components/exchange/ChartWidget.tsx`, `backend/app/services/market_data.py`, WebSocket streams, or any exchange chart UI.

---

## Task 1: Backend - Add new dependencies and config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`

**Step 1: Add new packages to requirements.txt**

Add these lines to `backend/requirements.txt`:
```
eth-account==0.13.4
web3==7.6.0
```

**Step 2: Update config.py with new settings**

Replace `backend/app/config.py` with:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BINANCE_BASE_URL: str = "https://api.binance.com"

    # Binance live trading
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_LIVE_TRADING: bool = False

    # Admin wallet address (MetaMask)
    ADMIN_WALLET_ADDRESS: str = ""

    # Polygon RPC for payment verification
    POLYGON_RPC_URL: str = "https://polygon-rpc.com"

    @field_validator('DATABASE_URL', mode='before')
    @classmethod
    def convert_database_url(cls, v):
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

settings = Settings()
```

**Step 3: Install new packages**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && pip install eth-account==0.13.4 web3==7.6.0`

**Step 4: Commit**
```bash
git add requirements.txt app/config.py
git commit -m "feat: add eth-account, web3 deps and new config settings"
```

---

## Task 2: Backend - Migrate User model to wallet-based auth

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/models/payment.py`
- Modify: `backend/app/models/bot.py`
- Create: `backend/alembic/versions/d4e5f6a7b8c9_metamask_auth.py`

**Step 1: Rewrite User model**

Replace `backend/app/models/user.py` with:
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    wallet_address = Column(String, unique=True, nullable=False, index=True)
    role = Column(Enum(UserRole), default=UserRole.user)
    is_subscribed = Column(Boolean, default=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    wallets = relationship("Wallet", back_populates="user")
    orders = relationship("Order", back_populates="user")
    bot_subscriptions = relationship("BotSubscription", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
```

**Step 2: Add payment fields to BotSubscription + create PaymentHistory model**

Add these columns to `BotSubscription` in `backend/app/models/bot.py` (after `allocated_usdt`):
```python
    tx_hash = Column(String, nullable=True)
    payment_amount = Column(Numeric(18, 6), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
```

Create `backend/app/models/payment.py`:
```python
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    tx_hash = Column(String, unique=True, nullable=False, index=True)
    amount = Column(Numeric(18, 6), nullable=False)
    network = Column(String(20), default="polygon")
    verified_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Step 3: Update models/__init__.py**

Replace `backend/app/models/__init__.py` with:
```python
from app.models.user import User, UserRole
from app.models.wallet import Wallet
from app.models.order import Order, Trade, OrderSide, OrderType, OrderStatus
from app.models.bot import Bot, BotSubscription, BotPerformance, BotStatus
from app.models.notification import Notification
from app.models.payment import PaymentHistory
```

**Step 4: Create Alembic migration**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && alembic revision --autogenerate -m "metamask auth and payment history"`

Then manually review the generated migration to ensure it:
- Drops `email` and `password_hash` columns from `users`
- Adds `wallet_address` column to `users`
- Adds `tx_hash`, `payment_amount`, `expires_at` to `bot_subscriptions`
- Creates `payment_history` table

**Step 5: Commit**
```bash
git add app/models/ alembic/versions/
git commit -m "feat: migrate User model to wallet_address, add PaymentHistory"
```

---

## Task 3: Backend - MetaMask authentication (EIP-191)

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/core/deps.py`
- Rewrite: `backend/app/routers/auth.py`
- Rewrite: `backend/app/schemas/auth.py`

**Step 1: Write test for nonce endpoint**

Create/replace `backend/tests/test_auth.py`:
```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
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
    """Test that verify endpoint creates new user and returns JWT."""
    from eth_account import Account
    from eth_account.messages import encode_defunct

    # Generate a test wallet
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
            data = r.json()
            assert "access_token" in data

@pytest.mark.asyncio
async def test_verify_invalid_signature(test_db):
    """Test that invalid signature is rejected."""
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
    """Test /me endpoint returns wallet_address."""
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
    mock_redis.set = AsyncMock()

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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL (old auth endpoints don't match)

**Step 3: Rewrite security.py**

Replace `backend/app/core/security.py` with:
```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from app.config import settings

def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.SECRET_KEY, settings.ALGORITHM)

def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload["sub"])
    except JWTError:
        return None
```

**Step 4: Update deps.py for wallet-based admin check**

Replace `backend/app/core/deps.py` with:
```python
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.core.security import decode_token
from app.config import settings

bearer = HTTPBearer()
bearer_optional = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    user_id = decode_token(credentials.credentials)
    if not user_id:
        return None
    return await db.get(User, user_id)

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not settings.ADMIN_WALLET_ADDRESS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin not configured")
    if user.wallet_address.lower() != settings.ADMIN_WALLET_ADDRESS.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user

async def require_subscription(user: User = Depends(get_current_user)) -> User:
    if not user.is_subscribed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Subscription required")
    return user
```

**Step 5: Rewrite auth schemas**

Replace `backend/app/schemas/auth.py` with:
```python
from pydantic import BaseModel

class NonceResponse(BaseModel):
    nonce: str

class VerifyRequest(BaseModel):
    address: str
    signature: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

**Step 6: Rewrite auth router**

Replace `backend/app/routers/auth.py` with:
```python
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from eth_account.messages import encode_defunct
from eth_account import Account
from app.database import get_db
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import NonceResponse, VerifyRequest, TokenResponse
from app.core.security import create_access_token
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

NONCE_TTL = 300  # 5 minutes

@router.get("/nonce", response_model=NonceResponse)
async def get_nonce(address: str = Query(..., min_length=42, max_length=42)):
    redis = await get_redis()
    nonce = secrets.token_hex(16)
    await redis.set(f"nonce:{address.lower()}", nonce, ex=NONCE_TTL)
    return NonceResponse(nonce=nonce)

@router.post("/verify", response_model=TokenResponse)
async def verify_signature(body: VerifyRequest, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    stored_nonce = await redis.get(f"nonce:{body.address.lower()}")
    if not stored_nonce:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nonce expired or not found")

    message = f"ForLabsEX Login\nNonce: {stored_nonce}"
    msg = encode_defunct(text=message)
    try:
        sig_bytes = bytes.fromhex(body.signature.removeprefix("0x"))
        recovered = Account.recover_message(msg, signature=sig_bytes)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    if recovered.lower() != body.address.lower():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature mismatch")

    await redis.delete(f"nonce:{body.address.lower()}")

    user = await db.scalar(select(User).where(User.wallet_address == body.address.lower()))
    if not user:
        role = "admin" if settings.ADMIN_WALLET_ADDRESS and body.address.lower() == settings.ADMIN_WALLET_ADDRESS.lower() else "user"
        user = User(wallet_address=body.address.lower(), role=role)
        db.add(user)
        await db.flush()
        db.add(Wallet(user_id=user.id, asset="USDT", balance=0))
        await db.commit()
        await db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "wallet_address": user.wallet_address,
        "role": user.role,
        "is_subscribed": user.is_subscribed,
    }
```

**Step 7: Run tests**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/test_auth.py -v`
Expected: All 4 tests PASS

**Step 8: Commit**
```bash
git add app/core/security.py app/core/deps.py app/routers/auth.py app/schemas/auth.py tests/test_auth.py
git commit -m "feat: replace email/password auth with MetaMask EIP-191"
```

---

## Task 4: Backend - Binance live trading service

**Files:**
- Create: `backend/app/services/binance_trader.py`
- Create: `backend/tests/test_binance_trader.py`

**Step 1: Write tests for BinanceTrader**

Create `backend/tests/test_binance_trader.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from app.services.binance_trader import BinanceTrader, pair_to_binance_symbol

def test_pair_to_binance_symbol():
    assert pair_to_binance_symbol("BTC_USDT") == "BTCUSDT"
    assert pair_to_binance_symbol("ETH_USDT") == "ETHUSDT"
    assert pair_to_binance_symbol("SOL_USDT") == "SOLUSDT"

@pytest.mark.asyncio
async def test_place_market_buy():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "orderId": 123456,
        "status": "FILLED",
        "fills": [
            {"price": "50000.00", "qty": "0.001", "commission": "0.0000001", "commissionAsset": "BTC"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    trader = BinanceTrader.__new__(BinanceTrader)
    trader.api_key = "test_key"
    trader.api_secret = "test_secret"
    trader.base_url = "https://api.binance.com"
    trader.client = mock_client

    result = await trader.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))
    assert result["orderId"] == 123456
    assert result["status"] == "FILLED"
    assert len(result["fills"]) == 1

@pytest.mark.asyncio
async def test_place_market_order_error():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"code":-1013,"msg":"Filter failure: LOT_SIZE"}'
    mock_response.json.return_value = {"code": -1013, "msg": "Filter failure: LOT_SIZE"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    trader = BinanceTrader.__new__(BinanceTrader)
    trader.api_key = "test_key"
    trader.api_secret = "test_secret"
    trader.base_url = "https://api.binance.com"
    trader.client = mock_client

    with pytest.raises(Exception, match="Binance order failed"):
        await trader.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/test_binance_trader.py -v`
Expected: FAIL (module not found)

**Step 3: Implement BinanceTrader**

Create `backend/app/services/binance_trader.py`:
```python
import hashlib
import hmac
import time
from decimal import Decimal
from urllib.parse import urlencode
import httpx
from app.config import settings

def pair_to_binance_symbol(pair: str) -> str:
    return pair.replace("_", "")

class BinanceTrader:
    def __init__(self):
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.base_url = settings.BINANCE_BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()

    async def place_market_order(self, symbol: str, side: str, quantity: Decimal) -> dict:
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)
        resp = await self.client.post(
            f"{self.base_url}/api/v3/order",
            params=params,
            headers={"X-MBX-APIKEY": self.api_key},
        )
        if resp.status_code != 200:
            raise Exception(f"Binance order failed: {resp.text}")
        return resp.json()

    async def get_account_balance(self) -> dict:
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        resp = await self.client.get(
            f"{self.base_url}/api/v3/account",
            params=params,
            headers={"X-MBX-APIKEY": self.api_key},
        )
        if resp.status_code != 200:
            raise Exception(f"Binance account query failed: {resp.text}")
        data = resp.json()
        return {b["asset"]: float(b["free"]) for b in data.get("balances", []) if float(b["free"]) > 0}

    async def close(self):
        await self.client.aclose()
```

**Step 4: Run tests**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/test_binance_trader.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**
```bash
git add app/services/binance_trader.py tests/test_binance_trader.py
git commit -m "feat: add BinanceTrader service for live market orders"
```

---

## Task 5: Backend - Update bot_runner for live trading

**Files:**
- Modify: `backend/app/services/matching_engine.py`
- Modify: `backend/app/services/bot_runner.py`

**Step 1: Add live trading path to matching_engine.py**

Add this function to `backend/app/services/matching_engine.py` (after the existing `try_fill_order`):
```python
async def try_fill_order_live(db: AsyncSession, order: Order) -> dict:
    """Fill order via real Binance API."""
    from app.services.binance_trader import BinanceTrader, pair_to_binance_symbol

    trader = BinanceTrader()
    try:
        symbol = pair_to_binance_symbol(order.pair)
        side = "BUY" if order.side == OrderSide.buy else "SELL"
        result = await trader.place_market_order(symbol, side, order.quantity)

        fills = result.get("fills", [])
        if not fills:
            return {"filled": False, "fill_price": 0}

        total_qty = sum(Decimal(f["qty"]) for f in fills)
        total_cost = sum(Decimal(f["price"]) * Decimal(f["qty"]) for f in fills)
        avg_price = total_cost / total_qty if total_qty > 0 else Decimal("0")

        base, quote = _base_quote(order.pair)

        if order.side == OrderSide.buy:
            quote_wallet = await get_wallet(db, order.user_id, quote)
            base_wallet = await get_wallet(db, order.user_id, base)
            if quote_wallet:
                quote_wallet.balance -= total_cost
            if base_wallet:
                base_wallet.balance += total_qty
            else:
                db.add(Wallet(user_id=order.user_id, asset=base, balance=total_qty))
        else:
            base_wallet = await get_wallet(db, order.user_id, base)
            quote_wallet = await get_wallet(db, order.user_id, quote)
            if base_wallet:
                base_wallet.balance -= total_qty
            if quote_wallet:
                quote_wallet.balance += total_cost
            else:
                db.add(Wallet(user_id=order.user_id, asset=quote, balance=total_cost))

        order.filled_quantity = total_qty
        order.status = OrderStatus.filled
        order.price = avg_price
        db.add(Trade(order_id=order.id, price=avg_price, quantity=total_qty))
        await db.commit()

        print(f"[LIVE] Order {order.id} filled: {side} {total_qty} {symbol} @ avg {avg_price}")
        return {"filled": True, "fill_price": float(avg_price)}
    except Exception as e:
        print(f"[LIVE] Order {order.id} failed: {e}")
        return {"filled": False, "fill_price": 0, "error": str(e)}
    finally:
        await trader.close()
```

**Step 2: Update bot_runner.py to use live or simulated trading**

In `backend/app/services/bot_runner.py`, change the import and the `try_fill_order` call inside `run_bot()`.

Replace the line:
```python
from app.services.matching_engine import try_fill_order
```
at the top with:
```python
from app.services.matching_engine import try_fill_order, try_fill_order_live
from app.config import settings
```

Then in the `run_bot` function, replace:
```python
            await try_fill_order(db, order)
```
with:
```python
            if settings.BINANCE_LIVE_TRADING:
                await try_fill_order_live(db, order)
            else:
                await try_fill_order(db, order)
```

Also add the same check in the subscription check part. Find the `generate_signal` function - it also needs to consider subscription expiry. Add this check at the beginning of the `for sub in sub_list:` loop in `run_bot()`:

After `for sub in sub_list:`, add:
```python
            # Skip expired subscriptions
            if sub.expires_at and sub.expires_at.replace(tzinfo=None) < datetime.utcnow():
                sub.is_active = False
                await db.commit()
                continue
```

(Add `from datetime import datetime` at top of file if not present)

**Step 3: Run existing tests to verify nothing broke**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**
```bash
git add app/services/matching_engine.py app/services/bot_runner.py
git commit -m "feat: add live Binance trading path in bot runner"
```

---

## Task 6: Backend - Payment verification service

**Files:**
- Create: `backend/app/services/payment_verifier.py`
- Create: `backend/tests/test_payment_verifier.py`

**Step 1: Write test**

Create `backend/tests/test_payment_verifier.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.payment_verifier import verify_polygon_usdt_payment, USDT_CONTRACT_ADDRESS

@pytest.mark.asyncio
async def test_verify_valid_payment():
    # Mock a successful Polygon RPC response with USDT Transfer event
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    to_addr_padded = "0x" + "0" * 24 + "abcdef1234567890abcdef1234567890abcdef12"
    from_addr_padded = "0x" + "0" * 24 + "1234567890abcdef1234567890abcdef12345678"
    # USDT has 6 decimals, so 50 USDT = 50_000_000 = 0x2FAF080
    amount_hex = hex(50_000_000)

    mock_receipt = {
        "result": {
            "status": "0x1",
            "logs": [
                {
                    "address": USDT_CONTRACT_ADDRESS.lower(),
                    "topics": [transfer_topic, from_addr_padded, to_addr_padded],
                    "data": "0x0000000000000000000000000000000000000000000000000000000002faf080",
                }
            ]
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_receipt

    with patch("app.services.payment_verifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        result = await verify_polygon_usdt_payment(
            tx_hash="0x1234567890abcdef",
            expected_to="0xabcdef1234567890abcdef1234567890abcdef12",
            expected_amount=50.0,
        )
        assert result["verified"] is True
        assert result["amount"] >= 50.0

@pytest.mark.asyncio
async def test_verify_wrong_recipient():
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    wrong_addr_padded = "0x" + "0" * 24 + "9999999999999999999999999999999999999999"
    from_addr_padded = "0x" + "0" * 24 + "1234567890abcdef1234567890abcdef12345678"

    mock_receipt = {
        "result": {
            "status": "0x1",
            "logs": [
                {
                    "address": USDT_CONTRACT_ADDRESS.lower(),
                    "topics": [transfer_topic, from_addr_padded, wrong_addr_padded],
                    "data": "0x0000000000000000000000000000000000000000000000000000000002faf080",
                }
            ]
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_receipt

    with patch("app.services.payment_verifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        result = await verify_polygon_usdt_payment(
            tx_hash="0xabc",
            expected_to="0xabcdef1234567890abcdef1234567890abcdef12",
            expected_amount=50.0,
        )
        assert result["verified"] is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/test_payment_verifier.py -v`
Expected: FAIL

**Step 3: Implement payment verifier**

Create `backend/app/services/payment_verifier.py`:
```python
import httpx
from app.config import settings

USDT_CONTRACT_ADDRESS = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
USDT_DECIMALS = 6
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

async def verify_polygon_usdt_payment(
    tx_hash: str,
    expected_to: str,
    expected_amount: float,
) -> dict:
    client = httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.post(
            settings.POLYGON_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
                "id": 1,
            },
        )
        if resp.status_code != 200:
            return {"verified": False, "error": "RPC request failed"}

        data = resp.json()
        receipt = data.get("result")
        if not receipt:
            return {"verified": False, "error": "Transaction not found"}

        if receipt.get("status") != "0x1":
            return {"verified": False, "error": "Transaction failed"}

        for log in receipt.get("logs", []):
            if log["address"].lower() != USDT_CONTRACT_ADDRESS.lower():
                continue
            topics = log.get("topics", [])
            if len(topics) < 3 or topics[0] != TRANSFER_EVENT_TOPIC:
                continue

            to_addr = "0x" + topics[2][-40:]
            if to_addr.lower() != expected_to.lower():
                continue

            raw_amount = int(log["data"], 16)
            amount = raw_amount / (10 ** USDT_DECIMALS)

            if amount >= expected_amount:
                from_addr = "0x" + topics[1][-40:]
                return {
                    "verified": True,
                    "amount": amount,
                    "from_address": from_addr,
                    "to_address": to_addr,
                }

        return {"verified": False, "error": "No matching USDT transfer found"}
    finally:
        await client.aclose()
```

**Step 4: Run tests**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/test_payment_verifier.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**
```bash
git add app/services/payment_verifier.py tests/test_payment_verifier.py
git commit -m "feat: add Polygon USDT payment verification service"
```

---

## Task 7: Backend - Update bots router with payment flow

**Files:**
- Modify: `backend/app/routers/bots.py`

**Step 1: Update SubscribeRequest and subscribe endpoint**

In `backend/app/routers/bots.py`, update the `SubscribeRequest`:
```python
class SubscribeRequest(BaseModel):
    allocated_usdt: float = Field(default=100.0, gt=0)
    tx_hash: str
```

Replace the `subscribe_bot` function with:
```python
@router.post("/{bot_id}/subscribe")
async def subscribe_bot(
    bot_id: int,
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot or bot.status != BotStatus.active:
        raise HTTPException(404, "Bot not found")
    existing = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
            BotSubscription.is_active == True,
        )
    )
    if existing:
        raise HTTPException(400, "Already subscribed")

    # Verify payment
    from app.services.payment_verifier import verify_polygon_usdt_payment
    from app.models.payment import PaymentHistory
    from app.config import settings

    # Check tx_hash not already used
    existing_payment = await db.scalar(
        select(PaymentHistory).where(PaymentHistory.tx_hash == body.tx_hash)
    )
    if existing_payment:
        raise HTTPException(400, "Transaction already used")

    monthly_fee = float(bot.monthly_fee) if bot.monthly_fee else 0
    if monthly_fee > 0:
        result = await verify_polygon_usdt_payment(
            tx_hash=body.tx_hash,
            expected_to=settings.ADMIN_WALLET_ADDRESS,
            expected_amount=monthly_fee,
        )
        if not result["verified"]:
            raise HTTPException(400, f"Payment verification failed: {result.get('error', 'unknown')}")

    from datetime import datetime, timedelta
    expires_at = datetime.utcnow() + timedelta(days=30)

    sub = BotSubscription(
        user_id=user.id,
        bot_id=bot_id,
        allocated_usdt=body.allocated_usdt,
        tx_hash=body.tx_hash,
        payment_amount=monthly_fee,
        expires_at=expires_at,
    )
    db.add(sub)

    if monthly_fee > 0:
        db.add(PaymentHistory(
            user_id=user.id,
            bot_id=bot_id,
            tx_hash=body.tx_hash,
            amount=monthly_fee,
            network="polygon",
        ))

    await db.commit()
    return {"message": "subscribed", "expires_at": expires_at.isoformat()}
```

**Step 2: Add renewal endpoint**

Add this new endpoint to `backend/app/routers/bots.py`:
```python
@router.post("/{bot_id}/renew")
async def renew_subscription(
    bot_id: int,
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
        ).order_by(BotSubscription.started_at.desc()).limit(1)
    )
    if not sub:
        raise HTTPException(404, "No subscription found")

    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")

    from app.services.payment_verifier import verify_polygon_usdt_payment
    from app.models.payment import PaymentHistory
    from app.config import settings

    existing_payment = await db.scalar(
        select(PaymentHistory).where(PaymentHistory.tx_hash == body.tx_hash)
    )
    if existing_payment:
        raise HTTPException(400, "Transaction already used")

    monthly_fee = float(bot.monthly_fee) if bot.monthly_fee else 0
    if monthly_fee > 0:
        result = await verify_polygon_usdt_payment(
            tx_hash=body.tx_hash,
            expected_to=settings.ADMIN_WALLET_ADDRESS,
            expected_amount=monthly_fee,
        )
        if not result["verified"]:
            raise HTTPException(400, f"Payment verification failed: {result.get('error', 'unknown')}")

    from datetime import datetime, timedelta
    sub.is_active = True
    sub.expires_at = datetime.utcnow() + timedelta(days=30)
    sub.tx_hash = body.tx_hash
    sub.payment_amount = monthly_fee
    sub.ended_at = None

    if monthly_fee > 0:
        db.add(PaymentHistory(
            user_id=user.id,
            bot_id=bot_id,
            tx_hash=body.tx_hash,
            amount=monthly_fee,
            network="polygon",
        ))

    await db.commit()
    return {"message": "renewed", "expires_at": sub.expires_at.isoformat()}
```

**Step 3: Commit**
```bash
git add app/routers/bots.py
git commit -m "feat: add payment verification to bot subscription flow"
```

---

## Task 8: Backend - Admin subscription management endpoints

**Files:**
- Modify: `backend/app/routers/admin.py`

**Step 1: Add subscription management endpoints**

Add these imports to the top of `backend/app/routers/admin.py`:
```python
from app.models.payment import PaymentHistory
```

Add these endpoints at the end of the file (before the closing of the module):

```python
@router.get("/subscriptions")
async def list_subscriptions(
    status: str = "all",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(BotSubscription)
    if status == "active":
        query = query.where(BotSubscription.is_active == True)
    elif status == "expired":
        query = query.where(BotSubscription.is_active == False)

    subs = list(await db.scalars(query.order_by(BotSubscription.started_at.desc())))
    result = []
    for sub in subs:
        user = await db.get(User, sub.user_id)
        bot = await db.get(Bot, sub.bot_id)
        result.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "wallet_address": user.wallet_address if user else None,
            "bot_id": sub.bot_id,
            "bot_name": bot.name if bot else None,
            "is_active": sub.is_active,
            "allocated_usdt": float(sub.allocated_usdt) if sub.allocated_usdt else 0,
            "payment_amount": float(sub.payment_amount) if sub.payment_amount else 0,
            "tx_hash": sub.tx_hash,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "ended_at": sub.ended_at.isoformat() if sub.ended_at else None,
        })
    return result

@router.get("/subscriptions/stats")
async def subscription_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active_count = await db.scalar(
        select(func.count(BotSubscription.id)).where(BotSubscription.is_active == True)
    )
    expired_count = await db.scalar(
        select(func.count(BotSubscription.id)).where(BotSubscription.is_active == False)
    )
    total_revenue = await db.scalar(
        select(func.sum(PaymentHistory.amount))
    )
    return {
        "active_subscriptions": active_count or 0,
        "expired_subscriptions": expired_count or 0,
        "total_revenue_usdt": float(total_revenue) if total_revenue else 0,
    }

@router.put("/subscriptions/{sub_id}")
async def update_subscription(
    sub_id: int,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub = await db.get(BotSubscription, sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if "is_active" in body:
        sub.is_active = body["is_active"]
        if not body["is_active"]:
            sub.ended_at = datetime.utcnow()
    if "expires_at" in body:
        from datetime import datetime as dt
        sub.expires_at = dt.fromisoformat(body["expires_at"])

    await db.commit()
    return {"message": "subscription updated"}

@router.get("/payments")
async def list_payments(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    payments = list(await db.scalars(
        select(PaymentHistory).order_by(PaymentHistory.verified_at.desc()).limit(200)
    ))
    result = []
    for p in payments:
        user = await db.get(User, p.user_id)
        bot = await db.get(Bot, p.bot_id)
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "wallet_address": user.wallet_address if user else None,
            "bot_id": p.bot_id,
            "bot_name": bot.name if bot else None,
            "tx_hash": p.tx_hash,
            "amount": float(p.amount),
            "network": p.network,
            "verified_at": p.verified_at.isoformat() if p.verified_at else None,
        })
    return result
```

**Step 2: Run tests**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**
```bash
git add app/routers/admin.py
git commit -m "feat: add admin subscription and payment management endpoints"
```

---

## Task 9: Backend - Subscription expiry scheduler

**Files:**
- Modify: `backend/app/services/bot_eviction.py`
- Modify: `backend/app/main.py`

**Step 1: Add expiry check job to bot_eviction.py**

Add this function to the end of `backend/app/services/bot_eviction.py`:
```python
async def check_subscription_expiry():
    """Deactivate expired subscriptions and notify users."""
    from datetime import datetime, timedelta
    async with AsyncSessionLocal() as db:
        # Find subscriptions expiring in 3 days (for notification)
        warning_date = datetime.utcnow() + timedelta(days=3)
        expiring_subs = await db.scalars(
            select(BotSubscription).where(
                BotSubscription.is_active == True,
                BotSubscription.expires_at != None,
                BotSubscription.expires_at <= warning_date,
                BotSubscription.expires_at > datetime.utcnow(),
            )
        )
        for sub in expiring_subs:
            bot = await db.get(Bot, sub.bot_id)
            bot_name = bot.name if bot else "Unknown"
            existing = await db.scalar(
                select(Notification).where(
                    Notification.user_id == sub.user_id,
                    Notification.type == "subscription_expiring",
                    Notification.title == f"{bot_name} 구독 만료 임박",
                    Notification.is_read == False,
                )
            )
            if not existing:
                db.add(Notification(
                    user_id=sub.user_id,
                    type="subscription_expiring",
                    title=f"{bot_name} 구독 만료 임박",
                    body=f"{bot_name} 봇 구독이 곧 만료됩니다. 갱신해주세요.",
                ))

        # Deactivate expired subscriptions
        expired_subs = await db.scalars(
            select(BotSubscription).where(
                BotSubscription.is_active == True,
                BotSubscription.expires_at != None,
                BotSubscription.expires_at <= datetime.utcnow(),
            )
        )
        for sub in expired_subs:
            sub.is_active = False
            sub.ended_at = datetime.utcnow()
            bot = await db.get(Bot, sub.bot_id)
            bot_name = bot.name if bot else "Unknown"
            db.add(Notification(
                user_id=sub.user_id,
                type="subscription_expired",
                title=f"{bot_name} 구독 만료",
                body=f"{bot_name} 봇 구독이 만료되었습니다. 갱신하려면 봇 마켓에서 다시 결제해주세요.",
            ))

        await db.commit()
```

Make sure these imports exist at the top of `bot_eviction.py`:
```python
from app.models.notification import Notification
```

**Step 2: Register scheduler job in main.py**

In `backend/app/main.py`, add to the imports:
```python
from app.services.bot_eviction import daily_drawdown_check, monthly_evaluation, daily_performance_update, check_subscription_expiry
```

Add to the `lifespan` function, after the existing scheduler jobs:
```python
    scheduler.add_job(check_subscription_expiry, "cron", hour=6, minute=0)
```

**Step 3: Commit**
```bash
git add app/services/bot_eviction.py app/main.py
git commit -m "feat: add subscription expiry checker with notifications"
```

---

## Task 10: Frontend - MetaMask auth store and login page

**Files:**
- Rewrite: `frontend/stores/authStore.ts`
- Rewrite: `frontend/app/(auth)/login/page.tsx`
- Delete: `frontend/app/(auth)/register/page.tsx`

**Step 1: Rewrite authStore.ts**

Replace `frontend/stores/authStore.ts` with:
```typescript
import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface UserInfo {
  id: number;
  wallet_address: string;
  role: string;
  is_subscribed: boolean;
}

interface AuthStore {
  token: string | null;
  user: UserInfo | null;
  walletAddress: string | null;
  connecting: boolean;
  setToken: (token: string | null) => void;
  connectWallet: () => Promise<void>;
  logout: () => void;
  hydrate: () => Promise<void>;
}

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      isMetaMask?: boolean;
    };
  }
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  user: null,
  walletAddress: null,
  connecting: false,

  setToken: (token) => set({ token }),

  hydrate: async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      set({ token: null, user: null });
      return;
    }
    set({ token });
    try {
      const user = await apiFetch("/api/auth/me");
      set({ user, walletAddress: user.wallet_address });
    } catch {
      localStorage.removeItem("token");
      set({ token: null, user: null });
    }
  },

  connectWallet: async () => {
    if (!window.ethereum) {
      throw new Error("MetaMask가 설치되어 있지 않습니다.");
    }

    set({ connecting: true });
    try {
      const accounts = (await window.ethereum.request({
        method: "eth_requestAccounts",
      })) as string[];
      const address = accounts[0];
      set({ walletAddress: address });

      // Get nonce
      const { nonce } = await apiFetch(`/api/auth/nonce?address=${address}`);

      // Sign message
      const message = `ForLabsEX Login\nNonce: ${nonce}`;
      const signature = (await window.ethereum.request({
        method: "personal_sign",
        params: [message, address],
      })) as string;

      // Verify
      const data = await apiFetch("/api/auth/verify", {
        method: "POST",
        body: JSON.stringify({ address, signature }),
      });

      localStorage.setItem("token", data.access_token);
      set({ token: data.access_token });

      const user = await apiFetch("/api/auth/me");
      set({ user });
    } finally {
      set({ connecting: false });
    }
  },

  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null, walletAddress: null });
  },
}));
```

**Step 2: Rewrite login page**

Replace `frontend/app/(auth)/login/page.tsx` with:
```tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const [error, setError] = useState("");
  const { connectWallet, connecting } = useAuthStore();
  const router = useRouter();

  const handleConnect = async () => {
    setError("");
    try {
      await connectWallet();
      router.push("/exchange/BTC_USDT");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "연결에 실패했습니다.";
      setError(message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
      <div className="w-full max-w-sm p-8 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>ForLabsEX</h1>
        <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
          MetaMask 지갑을 연결하여 시작하세요
        </p>
        {error && <p className="text-sm mb-4" style={{ color: "var(--red)" }}>{error}</p>}
        <button
          type="button"
          onClick={handleConnect}
          disabled={connecting}
          className="w-full py-3 rounded font-semibold text-white flex items-center justify-center gap-2"
          style={{ background: connecting ? "#666" : "#f6851b" }}
        >
          {connecting ? "연결 중..." : "MetaMask 연결"}
        </button>
        <p className="mt-4 text-xs text-center" style={{ color: "var(--text-secondary)" }}>
          MetaMask가 없으신가요?{" "}
          <a href="https://metamask.io/download/" target="_blank" rel="noopener noreferrer" style={{ color: "var(--blue)" }}>
            설치하기
          </a>
        </p>
      </div>
    </div>
  );
}
```

**Step 3: Delete register page**

Delete `frontend/app/(auth)/register/page.tsx`.

**Step 4: Update Navbar**

In `frontend/components/Navbar.tsx`, replace the non-logged-in section:

Replace:
```tsx
          <>
            <Link href="/login" style={{ color: "var(--text-secondary)" }} className="hover:text-white transition-colors">로그인</Link>
            <Link href="/register"
              className="px-4 py-1.5 rounded text-sm font-medium text-white"
              style={{ background: "var(--blue)" }}>회원가입</Link>
          </>
```
with:
```tsx
          <Link href="/login"
            className="px-4 py-1.5 rounded text-sm font-medium text-white"
            style={{ background: "#f6851b" }}>
            지갑 연결
          </Link>
```

Also update the logged-in section to show wallet address. Replace:
```tsx
          <>
            <Link href="/wallet" style={{ color: "var(--text-secondary)" }} className="hover:text-white transition-colors">자산</Link>
            <button
              type="button"
              onClick={handleLogout}
              className="px-4 py-1.5 rounded text-sm"
              style={{ background: "var(--bg-panel)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
              로그아웃
            </button>
          </>
```
with:
```tsx
          <>
            <Link href="/wallet" style={{ color: "var(--text-secondary)" }} className="hover:text-white transition-colors">자산</Link>
            <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
              {user?.wallet_address ? `${user.wallet_address.slice(0, 6)}...${user.wallet_address.slice(-4)}` : ""}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="px-4 py-1.5 rounded text-sm"
              style={{ background: "var(--bg-panel)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
              로그아웃
            </button>
          </>
```

**Step 5: Verify frontend builds**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**
```bash
git add stores/authStore.ts app/\(auth\)/login/page.tsx components/Navbar.tsx
git rm app/\(auth\)/register/page.tsx
git commit -m "feat: replace email/password login with MetaMask wallet connect"
```

---

## Task 11: Frontend - Bot subscription with Polygon USDT payment

**Files:**
- Modify: `frontend/app/bot-market/page.tsx`

**Step 1: Update SubscribeModal with MetaMask payment**

In `frontend/app/bot-market/page.tsx`, the `SubscribeModal` component needs to:
1. Show the bot's monthly fee
2. Switch MetaMask to Polygon network
3. Send USDT to operator wallet
4. Submit txHash to backend

Replace the `handleSubscribe` function and modal body. The key changes are:

Add these constants at the top of the file:
```typescript
const POLYGON_CHAIN_ID = "0x89"; // 137
const USDT_CONTRACT = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F";
const ADMIN_WALLET = process.env.NEXT_PUBLIC_ADMIN_WALLET || "";
```

Update `SubscribeModal` to include a payment step. The modal should:
1. Show monthly fee and allocated USDT input
2. On confirm, call `window.ethereum` to switch to Polygon
3. Send ERC-20 transfer via `eth_sendTransaction` with USDT contract data
4. Wait for txHash
5. POST to `/api/bots/{id}/subscribe` with `{ tx_hash, allocated_usdt }`

The exact implementation should replace the subscribe handler with:
```typescript
const handleSubscribe = async () => {
  if (!window.ethereum) {
    alert("MetaMask가 필요합니다.");
    return;
  }
  setLoading(true);
  try {
    // Switch to Polygon
    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: POLYGON_CHAIN_ID }],
      });
    } catch (switchError: unknown) {
      // If Polygon not added, add it
      const err = switchError as { code?: number };
      if (err.code === 4902) {
        await window.ethereum.request({
          method: "wallet_addEthereumChain",
          params: [{
            chainId: POLYGON_CHAIN_ID,
            chainName: "Polygon Mainnet",
            nativeCurrency: { name: "MATIC", symbol: "MATIC", decimals: 18 },
            rpcUrls: ["https://polygon-rpc.com"],
            blockExplorerUrls: ["https://polygonscan.com"],
          }],
        });
      }
    }

    const accounts = await window.ethereum.request({ method: "eth_accounts" }) as string[];
    const from = accounts[0];

    // Encode ERC-20 transfer: transfer(address,uint256)
    const fee = bot.monthly_fee || 0;
    if (fee <= 0) {
      // Free bot - no payment needed
      await apiFetch(`/api/bots/${bot.id}/subscribe`, {
        method: "POST",
        body: JSON.stringify({ allocated_usdt: allocation, tx_hash: "free_" + Date.now() }),
      });
      onClose();
      return;
    }

    const amountHex = (BigInt(Math.round(fee * 1e6))).toString(16).padStart(64, "0");
    const toHex = ADMIN_WALLET.slice(2).toLowerCase().padStart(64, "0");
    const data = "0xa9059cbb" + toHex + amountHex;

    const txHash = await window.ethereum.request({
      method: "eth_sendTransaction",
      params: [{
        from,
        to: USDT_CONTRACT,
        data,
        value: "0x0",
      }],
    }) as string;

    await apiFetch(`/api/bots/${bot.id}/subscribe`, {
      method: "POST",
      body: JSON.stringify({ allocated_usdt: allocation, tx_hash: txHash }),
    });

    onClose();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "결제에 실패했습니다.";
    alert(message);
  } finally {
    setLoading(false);
  }
};
```

Also add monthly fee display in the modal UI, before the allocation input:
```tsx
{bot.monthly_fee > 0 && (
  <div className="mb-4 p-3 rounded" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
    <p className="text-sm" style={{ color: "var(--text-secondary)" }}>월 구독료</p>
    <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{bot.monthly_fee} USDT</p>
    <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>Polygon 네트워크에서 USDT로 결제됩니다</p>
  </div>
)}
```

**Step 2: Add `NEXT_PUBLIC_ADMIN_WALLET` to frontend env**

Add to `frontend/.env.local`:
```
NEXT_PUBLIC_ADMIN_WALLET=0x...
```

**Step 3: Verify build**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**
```bash
git add app/bot-market/page.tsx
git commit -m "feat: add Polygon USDT payment to bot subscription flow"
```

---

## Task 12: Frontend - Admin subscription management page

**Files:**
- Create: `frontend/app/admin/subscriptions/page.tsx`
- Modify: `frontend/components/Navbar.tsx`

**Step 1: Create admin subscriptions page**

Create `frontend/app/admin/subscriptions/page.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { apiFetch } from "@/lib/api";

interface Subscription {
  id: number;
  user_id: number;
  wallet_address: string | null;
  bot_id: number;
  bot_name: string | null;
  is_active: boolean;
  allocated_usdt: number;
  payment_amount: number;
  tx_hash: string | null;
  started_at: string | null;
  expires_at: string | null;
  ended_at: string | null;
}

interface Payment {
  id: number;
  wallet_address: string | null;
  bot_name: string | null;
  tx_hash: string;
  amount: number;
  network: string;
  verified_at: string | null;
}

interface Stats {
  active_subscriptions: number;
  expired_subscriptions: number;
  total_revenue_usdt: number;
}

export default function AdminSubscriptionsPage() {
  const { user, hydrate } = useAuthStore();
  const router = useRouter();
  const [tab, setTab] = useState<"subscriptions" | "payments">("subscriptions");
  const [filter, setFilter] = useState("all");
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => { hydrate(); }, []);

  useEffect(() => {
    if (user && user.role !== "admin") router.push("/exchange/BTC_USDT");
    if (user?.role === "admin") {
      fetchData();
    }
  }, [user, filter]);

  const fetchData = async () => {
    try {
      const [subsData, statsData, paymentsData] = await Promise.all([
        apiFetch(`/api/admin/subscriptions?status=${filter}`),
        apiFetch("/api/admin/subscriptions/stats"),
        apiFetch("/api/admin/payments"),
      ]);
      setSubs(subsData);
      setStats(statsData);
      setPayments(paymentsData);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleSubscription = async (subId: number, isActive: boolean) => {
    try {
      await apiFetch(`/api/admin/subscriptions/${subId}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !isActive }),
      });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const isExpiringSoon = (expiresAt: string | null) => {
    if (!expiresAt) return false;
    const diff = new Date(expiresAt).getTime() - Date.now();
    return diff > 0 && diff < 3 * 24 * 60 * 60 * 1000;
  };

  const filtered = subs.filter((s) =>
    !search || (s.wallet_address?.toLowerCase().includes(search.toLowerCase()) ||
      s.bot_name?.toLowerCase().includes(search.toLowerCase()))
  );

  if (!user || user.role !== "admin") return null;

  return (
    <div className="p-6 max-w-7xl mx-auto" style={{ color: "var(--text-primary)" }}>
      <h1 className="text-2xl font-bold mb-6">구독 관리</h1>

      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>활성 구독</p>
            <p className="text-2xl font-bold" style={{ color: "var(--green)" }}>{stats.active_subscriptions}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>만료 구독</p>
            <p className="text-2xl font-bold" style={{ color: "var(--red)" }}>{stats.expired_subscriptions}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>총 수익</p>
            <p className="text-2xl font-bold" style={{ color: "var(--blue)" }}>{stats.total_revenue_usdt.toFixed(2)} USDT</p>
          </div>
        </div>
      )}

      <div className="flex gap-4 mb-4">
        <button onClick={() => setTab("subscriptions")}
          className="px-4 py-2 rounded text-sm font-medium"
          style={{ background: tab === "subscriptions" ? "var(--blue)" : "var(--bg-panel)", color: tab === "subscriptions" ? "#fff" : "var(--text-secondary)" }}>
          구독 목록
        </button>
        <button onClick={() => setTab("payments")}
          className="px-4 py-2 rounded text-sm font-medium"
          style={{ background: tab === "payments" ? "var(--blue)" : "var(--bg-panel)", color: tab === "payments" ? "#fff" : "var(--text-secondary)" }}>
          결제 내역
        </button>
      </div>

      {tab === "subscriptions" && (
        <>
          <div className="flex gap-4 mb-4">
            <input
              type="text" placeholder="지갑 주소 또는 봇 이름 검색..."
              value={search} onChange={(e) => setSearch(e.target.value)}
              className="flex-1 px-4 py-2 rounded text-sm outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
            <select value={filter} onChange={(e) => setFilter(e.target.value)}
              className="px-4 py-2 rounded text-sm"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              <option value="all">전체</option>
              <option value="active">활성</option>
              <option value="expired">만료</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>지갑</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>봇</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>상태</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>배정 USDT</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>결제액</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>만료일</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>액션</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.id} style={{
                    borderBottom: "1px solid var(--border)",
                    background: isExpiringSoon(s.expires_at) ? "rgba(245, 158, 11, 0.1)" : undefined,
                  }}>
                    <td className="p-3 font-mono text-xs">
                      {s.wallet_address ? `${s.wallet_address.slice(0, 6)}...${s.wallet_address.slice(-4)}` : "-"}
                    </td>
                    <td className="p-3">{s.bot_name || "-"}</td>
                    <td className="p-3">
                      <span className="px-2 py-1 rounded text-xs" style={{
                        background: s.is_active ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
                        color: s.is_active ? "var(--green)" : "var(--red)",
                      }}>
                        {s.is_active ? (isExpiringSoon(s.expires_at) ? "만료 임박" : "활성") : "만료"}
                      </span>
                    </td>
                    <td className="p-3">{s.allocated_usdt}</td>
                    <td className="p-3">{s.payment_amount} USDT</td>
                    <td className="p-3 text-xs">
                      {s.expires_at ? new Date(s.expires_at).toLocaleDateString("ko-KR") : "-"}
                    </td>
                    <td className="p-3">
                      <button
                        onClick={() => toggleSubscription(s.id, s.is_active)}
                        className="px-3 py-1 rounded text-xs"
                        style={{
                          background: s.is_active ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)",
                          color: s.is_active ? "var(--red)" : "var(--green)",
                        }}>
                        {s.is_active ? "비활성화" : "활성화"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "payments" && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>지갑</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>봇</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>금액</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>네트워크</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>TX Hash</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>검증일</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="p-3 font-mono text-xs">
                    {p.wallet_address ? `${p.wallet_address.slice(0, 6)}...${p.wallet_address.slice(-4)}` : "-"}
                  </td>
                  <td className="p-3">{p.bot_name || "-"}</td>
                  <td className="p-3">{p.amount} USDT</td>
                  <td className="p-3 text-xs uppercase">{p.network}</td>
                  <td className="p-3 font-mono text-xs">
                    <a href={`https://polygonscan.com/tx/${p.tx_hash}`} target="_blank" rel="noopener noreferrer"
                      style={{ color: "var(--blue)" }}>
                      {p.tx_hash.slice(0, 10)}...
                    </a>
                  </td>
                  <td className="p-3 text-xs">
                    {p.verified_at ? new Date(p.verified_at).toLocaleDateString("ko-KR") : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Add admin subscriptions link to Navbar**

In `frontend/components/Navbar.tsx`, replace the admin link:
```tsx
          {user?.role === "admin" && (
            <Link href="/admin/bots" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
              관리자
            </Link>
          )}
```
with:
```tsx
          {user?.role === "admin" && (
            <>
              <Link href="/admin/bots" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
                봇 관리
              </Link>
              <Link href="/admin/subscriptions" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
                구독 관리
              </Link>
            </>
          )}
```

**Step 3: Verify build**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**
```bash
git add app/admin/subscriptions/page.tsx components/Navbar.tsx
git commit -m "feat: add admin subscription management page"
```

---

## Task 13: Backend - Remove unused email dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Remove email-validator and passlib**

Remove these lines from `backend/requirements.txt`:
```
passlib[bcrypt]==1.7.4
bcrypt==4.2.1
email-validator==2.1.0
```

These are no longer needed since we removed email/password auth.

**Step 2: Verify tests still pass**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && pip install -r requirements.txt && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**
```bash
git add requirements.txt
git commit -m "chore: remove unused email/password auth dependencies"
```

---

## Task 14: Railway deployment configuration

**Files:**
- Modify: `backend/.env` (template)
- Modify: `frontend/.env.local` (template)
- Create: `frontend/railway.toml`

**Step 1: Create frontend railway.toml**

Create `frontend/railway.toml`:
```toml
[build]
builder = "nixpacks"
buildCommand = "npm install && npm run build"

[deploy]
startCommand = "npm start"
healthcheckPath = "/"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
```

**Step 2: Document required Railway environment variables**

Create `RAILWAY_ENV_TEMPLATE.md` in project root:
```markdown
# Railway Environment Variables

## Backend Service
```
DATABASE_URL=<Railway PostgreSQL URL>
REDIS_URL=<Railway Redis URL>
SECRET_KEY=<random 32+ char string>
BINANCE_API_KEY=<your Binance API key>
BINANCE_API_SECRET=<your Binance API secret>
BINANCE_LIVE_TRADING=true
ADMIN_WALLET_ADDRESS=<your MetaMask wallet address>
POLYGON_RPC_URL=https://polygon-rpc.com
CORS_ORIGINS=<frontend Railway URL>
```

## Frontend Service
```
NEXT_PUBLIC_API_URL=<backend Railway URL>
NEXT_PUBLIC_WS_URL=<backend Railway WS URL>
NEXT_PUBLIC_ADMIN_WALLET=<same as ADMIN_WALLET_ADDRESS>
```

## Railway Settings
- Region: asia-southeast1 (Singapore)
- Both services in same project
```

**Step 3: Commit**
```bash
git add frontend/railway.toml RAILWAY_ENV_TEMPLATE.md
git commit -m "feat: add frontend Railway config and env template"
```

---

## Task 15: Run all migrations and full test suite

**Step 1: Run Alembic migration**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && alembic upgrade head`

**Step 2: Run full backend tests**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/backend && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Build frontend**

Run: `cd /Users/heesangchae/forlabs-auto-exchange/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Final commit**
```bash
cd /Users/heesangchae/forlabs-auto-exchange
git add -A
git commit -m "feat: ForLabsEX production upgrade complete - MetaMask auth, live Binance trading, Polygon USDT payments"
```

---

## Summary of All Tasks

| # | Task | Files Changed |
|---|------|--------------|
| 1 | Add deps + config | requirements.txt, config.py |
| 2 | Migrate User model | models/user.py, bot.py, payment.py, migration |
| 3 | MetaMask auth backend | security.py, deps.py, auth.py, schemas/auth.py, tests |
| 4 | Binance trader service | binance_trader.py, test |
| 5 | Bot runner live trading | matching_engine.py, bot_runner.py |
| 6 | Payment verifier | payment_verifier.py, test |
| 7 | Bot subscription + payment | bots.py |
| 8 | Admin subscription endpoints | admin.py |
| 9 | Expiry scheduler | bot_eviction.py, main.py |
| 10 | Frontend MetaMask login | authStore.ts, login page, Navbar |
| 11 | Frontend USDT payment | bot-market/page.tsx |
| 12 | Frontend admin subscriptions | admin/subscriptions/page.tsx, Navbar |
| 13 | Remove unused deps | requirements.txt |
| 14 | Railway deployment | railway.toml, env template |
| 15 | Integration test + build | All |

**DO NOT MODIFY**: ChartWidget.tsx, market_data.py, exchange UI, WebSocket streams
