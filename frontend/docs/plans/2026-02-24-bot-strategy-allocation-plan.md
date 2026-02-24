# Bot Strategy & User Allocation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement RSI/MA/Bollinger strategy execution in bot_runner, add per-subscription capital allocation, and wire the subscription modal to pass allocation amount.

**Architecture:** Extract pure indicator math to `app/services/indicators.py` for testability. Add `allocated_usdt` to `BotSubscription` via Alembic. Update subscribe endpoint + bot_runner to use allocation. Add allocation input to the frontend subscription modal.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest, Next.js/React/Zustand

**Note:** Admin panel strategy config UI is already complete. `/api/wallet` returns `[{"asset":"USDT","balance":"10000","locked":"0"}]`.

---

### Task 1: Add allocated_usdt to BotSubscription model + migration

**Files:**
- Modify: `backend/app/models/bot.py`
- Create: `backend/alembic/versions/b2c3d4e5f6a7_add_allocated_usdt.py`

**Step 1: Add column to BotSubscription in `app/models/bot.py`**

After the `ended_at` column, add:
```python
allocated_usdt = Column(Numeric(18, 2), nullable=False, server_default="100")
```

**Step 2: Create migration file manually**

Create `alembic/versions/b2c3d4e5f6a7_add_allocated_usdt.py`:
```python
"""add allocated_usdt to bot_subscriptions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Branch Labels: None
Depends On: None
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('bot_subscriptions',
        sa.Column('allocated_usdt', sa.Numeric(18, 2), nullable=False, server_default='100'))

def downgrade():
    op.drop_column('bot_subscriptions', 'allocated_usdt')
```

**Step 3: Run migration**

```bash
cd /Users/heesangchae/crypto-exchange/backend
venv/bin/alembic upgrade head
```
Expected: no errors

**Step 4: Commit**
```bash
git add app/models/bot.py alembic/versions/b2c3d4e5f6a7_add_allocated_usdt.py
git commit -m "feat: add allocated_usdt to BotSubscription"
```

---

### Task 2: Update subscribe endpoint to accept allocated_usdt

**Files:**
- Modify: `backend/app/routers/bots.py`

**Step 1: Add SubscribeRequest schema and update subscribe_bot**

At the top of `bots.py` import section, add: `from pydantic import BaseModel`

After the imports, add:
```python
class SubscribeRequest(BaseModel):
    allocated_usdt: float = 100.0
```

Change `subscribe_bot` signature to:
```python
@router.post("/{bot_id}/subscribe")
async def subscribe_bot(
    bot_id: int,
    body: SubscribeRequest = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body is None:
        body = SubscribeRequest()
```

Change the `db.add(BotSubscription(...))` line to:
```python
db.add(BotSubscription(user_id=user.id, bot_id=bot_id, allocated_usdt=body.allocated_usdt))
```

**Step 2: Restart backend and manually verify**
```bash
pkill -f "uvicorn app.main:app"
cd /Users/heesangchae/crypto-exchange/backend
nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 2 && curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`

**Step 3: Commit**
```bash
git add app/routers/bots.py
git commit -m "feat: subscribe endpoint accepts allocated_usdt"
```

---

### Task 3: Create indicators.py with pure math functions

**Files:**
- Create: `backend/app/services/indicators.py`
- Create: `backend/tests/test_indicators.py`

**Step 1: Write failing tests**

Create `tests/test_indicators.py`:
```python
import math
import pytest
from app.services.indicators import calc_rsi, calc_ma, calc_bollinger

def test_calc_rsi_oversold():
    # Steadily declining prices → RSI should be low
    prices = [float(100 - i) for i in range(16)]
    rsi = calc_rsi(prices, period=14)
    assert rsi < 30

def test_calc_rsi_overbought():
    # Steadily rising prices → RSI should be high
    prices = [float(100 + i) for i in range(16)]
    rsi = calc_rsi(prices, period=14)
    assert rsi > 70

def test_calc_rsi_neutral_returns_50_on_insufficient_data():
    prices = [100.0, 101.0]
    rsi = calc_rsi(prices, period=14)
    assert rsi == 50.0

def test_calc_ma():
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert calc_ma(prices, period=3) == pytest.approx(4.0)  # avg of last 3: 3,4,5

def test_calc_ma_insufficient_data_returns_last():
    prices = [42.0]
    assert calc_ma(prices, period=5) == 42.0

def test_calc_bollinger_buy_signal():
    # Price well below lower band → should be at or below lower band
    prices = [100.0] * 19 + [70.0]
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert prices[-1] <= lower

def test_calc_bollinger_sell_signal():
    # Price well above upper band → should be at or above upper band
    prices = [100.0] * 19 + [130.0]
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert prices[-1] >= upper

def test_calc_bollinger_normal_price_is_inside_bands():
    prices = [100.0] * 20
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert lower <= 100.0 <= upper
```

**Step 2: Run to verify they fail**
```bash
cd /Users/heesangchae/crypto-exchange/backend
venv/bin/pytest tests/test_indicators.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

**Step 3: Implement `app/services/indicators.py`**
```python
import math
from typing import List, Tuple


def calc_rsi(closes: List[float], period: int = 14) -> float:
    """Compute RSI from a list of closing prices. Returns 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [max(d, 0.0) for d in recent]
    losses = [abs(min(d, 0.0)) for d in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_ma(closes: List[float], period: int) -> float:
    """Simple moving average of the last `period` prices."""
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    return sum(closes[-period:]) / period


def calc_bollinger(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> Tuple[float, float]:
    """Return (lower_band, upper_band). Falls back to ±5% if insufficient data."""
    if len(closes) < period:
        last = closes[-1] if closes else 100.0
        return (last * 0.95, last * 1.05)
    window = closes[-period:]
    ma = sum(window) / period
    variance = sum((p - ma) ** 2 for p in window) / period
    std = math.sqrt(variance)
    return (ma - std_dev * std, ma + std_dev * std)
```

**Step 4: Run tests to verify they pass**
```bash
venv/bin/pytest tests/test_indicators.py -v
```
Expected: 8 PASS

**Step 5: Commit**
```bash
git add app/services/indicators.py tests/test_indicators.py
git commit -m "feat: add indicator math (RSI, MA, Bollinger) with tests"
```

---

### Task 4: Implement RSI/MA/Bollinger signals in bot_runner.py

**Files:**
- Modify: `backend/app/services/bot_runner.py`

**Step 1: Replace `generate_signal()` with strategy-aware version**

Full replacement of `generate_signal` function in `bot_runner.py`:
```python
from typing import Optional
from app.services.indicators import calc_rsi, calc_ma, calc_bollinger
from app.services.market_data import fetch_klines

async def generate_signal(bot: Bot, pair: str) -> Optional[str]:
    redis = await get_redis()
    config = bot.strategy_config or {}
    interval = config.get("signal_interval", 300)

    last_trade_key = f"bot:{bot.id}:last_trade_time"
    last_trade = await redis.get(last_trade_key)
    now = int(time.time())
    if last_trade and now - int(last_trade) < interval:
        return None

    strategy = bot.strategy_type or "alternating"
    signal: Optional[str] = None

    if strategy == "alternating":
        last_side_key = f"bot:{bot.id}:last_side"
        last_side = await redis.get(last_side_key)
        signal = "sell" if last_side == "buy" else "buy"
        await redis.set(last_side_key, signal)

    elif strategy == "rsi":
        period = int(config.get("rsi_period", 14))
        oversold = float(config.get("oversold", 30))
        overbought = float(config.get("overbought", 70))
        try:
            klines = await fetch_klines(pair, "1h", period + 5)
            closes = [float(k["close"]) for k in klines]
            rsi = calc_rsi(closes, period)
            if rsi < oversold:
                signal = "buy"
            elif rsi > overbought:
                signal = "sell"
        except Exception as e:
            print(f"RSI signal error bot {bot.id}: {e}")

    elif strategy == "ma_cross":
        fast = int(config.get("fast_period", 5))
        slow = int(config.get("slow_period", 20))
        try:
            klines = await fetch_klines(pair, "1h", slow + 5)
            closes = [float(k["close"]) for k in klines]
            fast_ma = calc_ma(closes, fast)
            slow_ma = calc_ma(closes, slow)
            prev_fast = calc_ma(closes[:-1], fast)
            prev_slow = calc_ma(closes[:-1], slow)
            if prev_fast <= prev_slow and fast_ma > slow_ma:
                signal = "buy"   # golden cross
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                signal = "sell"  # death cross
        except Exception as e:
            print(f"MA cross signal error bot {bot.id}: {e}")

    elif strategy == "boll":
        period = int(config.get("period", 20))
        std_dev = float(config.get("deviation", 2.0))
        try:
            klines = await fetch_klines(pair, "1h", period + 5)
            closes = [float(k["close"]) for k in klines]
            lower, upper = calc_bollinger(closes, period, std_dev)
            current = closes[-1]
            if current <= lower:
                signal = "buy"
            elif current >= upper:
                signal = "sell"
        except Exception as e:
            print(f"Bollinger signal error bot {bot.id}: {e}")

    if signal:
        await redis.set(last_trade_key, now)
    return signal
```

**Step 2: Commit**
```bash
git add app/services/bot_runner.py
git commit -m "feat: implement RSI/MA cross/Bollinger signals in bot_runner"
```

---

### Task 5: Update run_bot() to respect allocated_usdt per subscription

**Files:**
- Modify: `backend/app/services/bot_runner.py`

**Step 1: Replace the per-subscription trading block in `run_bot()`**

The current block iterates over `sub_list` and trades `trade_pct` of the full wallet.
Replace the entire inner `for sub in sub_list:` block:

```python
        for sub in sub_list:
            from app.models.wallet import Wallet
            from sqlalchemy import select as sel

            base, quote = pair.split("_")
            allocated = Decimal(str(sub.allocated_usdt or 100))

            # Estimate how much USDT the bot has already deployed for this user
            bot_orders_result = await db.scalars(
                sel(Order).where(
                    Order.user_id == sub.user_id,
                    Order.bot_id == bot.id,
                    Order.status == "filled",
                )
            )
            deployed = Decimal("0")
            for o in bot_orders_result:
                price_val = Decimal(str(o.price or 0))
                qty_val = Decimal(str(o.filled_quantity or 0))
                if o.side == "buy":
                    deployed += qty_val * price_val
                else:
                    deployed -= qty_val * price_val

            redis = await get_redis()
            ticker = await redis.get(f"market:{pair}:ticker")
            if not ticker:
                continue
            price = Decimal(json.loads(ticker)["last_price"])

            if signal == "buy":
                available = allocated - deployed
                if available <= Decimal("0"):
                    continue  # allocation fully deployed
                wallet = await db.scalar(
                    sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == quote)
                )
                if not wallet or wallet.balance <= 0:
                    continue
                spend = min(
                    wallet.balance * Decimal(str(trade_pct / 100)),
                    available,
                )
                quantity = (spend / price).quantize(Decimal("0.00001"))
            else:  # sell
                wallet = await db.scalar(
                    sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == base)
                )
                if not wallet or wallet.balance <= 0:
                    continue
                quantity = (wallet.balance * Decimal(str(trade_pct / 100))).quantize(
                    Decimal("0.00001")
                )

            if quantity <= 0:
                continue

            order = Order(
                user_id=sub.user_id,
                pair=pair,
                side=OrderSide(signal),
                type=OrderType.market,
                quantity=quantity,
                is_bot_order=True,
                bot_id=bot.id,
            )
            db.add(order)
            await db.flush()
            await try_fill_order(db, order)
```

**Step 2: Commit**
```bash
git add app/services/bot_runner.py
git commit -m "feat: bot runner respects per-subscription allocated_usdt"
```

---

### Task 6: Add allocation input to SubscribeModal + botStore

**Files:**
- Modify: `frontend/app/bot-market/page.tsx`
- Modify: `frontend/stores/botStore.ts`

**Step 1: Update botStore `subscribe` to accept and pass `allocated_usdt`**

In `stores/botStore.ts`, change the `BotStore` interface:
```typescript
subscribe: (botId: number, allocatedUsdt?: number) => Promise<void>;
```

Change the `subscribe` implementation:
```typescript
subscribe: async (botId, allocatedUsdt = 100) => {
    await apiFetch(`/api/bots/${botId}/subscribe`, {
        method: "POST",
        body: JSON.stringify({ allocated_usdt: allocatedUsdt }),
    });
},
```

**Step 2: Add state to `BotMarketPage` for usdtBalance and pendingAllocation**

In `BotMarketPage`, add these state variables:
```typescript
const [usdtBalance, setUsdtBalance] = useState<number>(0);
const [pendingAllocation, setPendingAllocation] = useState<number>(100);
```

In the `useEffect`, after `fetchBots`, fetch wallet balance:
```typescript
useEffect(() => {
    hydrate().then(() => {
        fetchBots().catch(() => {});
        if (token) {
            apiFetch("/api/wallet")
                .then((data: Array<{ asset: string; balance: string }>) => {
                    const usdt = data.find((w) => w.asset === "USDT");
                    setUsdtBalance(usdt ? parseFloat(usdt.balance) : 0);
                })
                .catch(() => {});
        }
    });
}, []);
```

Note: also run wallet fetch after token is known. Add a second `useEffect`:
```typescript
useEffect(() => {
    if (!token) return;
    apiFetch("/api/wallet")
        .then((data: Array<{ asset: string; balance: string }>) => {
            const usdt = data.find((w) => w.asset === "USDT");
            setUsdtBalance(usdt ? parseFloat(usdt.balance) : 0);
        })
        .catch(() => {});
}, [token]);
```

**Step 3: Update `handleSubscribeClick` to reset allocation**

```typescript
const handleSubscribeClick = (bot: Bot) => {
    if (!token) { router.push("/login"); return; }
    setPendingAllocation(100);
    setPendingBot(bot);
};
```

**Step 4: Update `handleConfirmSubscribe` to pass allocation**

```typescript
const handleConfirmSubscribe = async () => {
    if (!pendingBot) return;
    setSubscribing(true);
    try {
        await subscribe(pendingBot.id, pendingAllocation);
        ...
```

**Step 5: Update `SubscribeModal` component signature and UI**

Change `SubscribeModal` props:
```typescript
function SubscribeModal({ bot, allocation, onAllocationChange, onConfirm, onCancel, loading, usdtBalance }: {
    bot: Bot;
    allocation: number;
    onAllocationChange: (v: number) => void;
    onConfirm: () => void;
    onCancel: () => void;
    loading: boolean;
    usdtBalance: number;
})
```

Inside the modal, after the fee row, add the allocation input:
```tsx
<div className="border-t pt-3 mt-1" style={{ borderColor: "var(--border)" }}>
    <div className="flex items-center justify-between mb-2">
        <span className="text-sm" style={{ color: "var(--text-secondary)" }}>할당 금액 (USDT)</span>
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            보유: {usdtBalance.toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT
        </span>
    </div>
    <input
        type="number"
        min={1}
        max={usdtBalance}
        step={10}
        value={allocation}
        onChange={(e) => onAllocationChange(Math.max(1, Number(e.target.value)))}
        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
        style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
    />
</div>
```

**Step 6: Update `SubscribeModal` usage in `BotMarketPage`**

```tsx
{pendingBot && (
    <SubscribeModal
        bot={pendingBot}
        allocation={pendingAllocation}
        onAllocationChange={setPendingAllocation}
        onConfirm={handleConfirmSubscribe}
        onCancel={() => setPendingBot(null)}
        loading={subscribing}
        usdtBalance={usdtBalance}
    />
)}
```

**Step 7: Restart backend and verify**
```bash
pkill -f "uvicorn app.main:app"
cd /Users/heesangchae/crypto-exchange/backend
nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 2 && curl -s http://localhost:8000/health
```

**Step 8: Commit**
```bash
git add frontend/app/bot-market/page.tsx frontend/stores/botStore.ts
git commit -m "feat: allocation input in subscribe modal, pass to API"
```

---

### Task 7: Run all backend tests

**Step 1: Run full test suite**
```bash
cd /Users/heesangchae/crypto-exchange/backend
venv/bin/pytest tests/ -v
```
Expected: all tests PASS (test_indicators + existing tests)

**Step 2: Commit if any fixes needed**
```bash
git add .
git commit -m "fix: resolve any failing tests"
```
