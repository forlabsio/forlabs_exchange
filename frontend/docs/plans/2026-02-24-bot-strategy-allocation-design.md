# Bot Strategy & User Allocation Design
Date: 2026-02-24

## Problem
1. Bot runner only implements "alternating" strategy — RSI, MA Cross, Bollinger are defined in DB but have no execution logic
2. Users subscribing to bots have no way to set capital allocation — bot uses % of full wallet

## Design

### 1. Strategy Config (Admin Side)

Admin sets `strategy_config` JSON when creating/editing a bot. Each strategy type has its own parameter schema:

```json
// alternating (already implemented)
{"pair": "BTC_USDT", "signal_interval": 300, "trade_pct": 10}

// rsi
{"pair": "BTC_USDT", "period": 14, "oversold": 30, "overbought": 70}

// ma_cross
{"pair": "BTC_USDT", "short_period": 7, "long_period": 25}

// boll
{"pair": "BTC_USDT", "period": 20, "std_dev": 2.0}
```

Admin panel shows a JSON editor/file upload for strategy config. The execution logic for each type is hardcoded in the backend.

### 2. Strategy Execution (Backend)

`bot_runner.py` `generate_signal()` branches by `strategy_type`:

- **alternating**: buy/sell alternating on timer (existing)
- **rsi**: fetch recent N klines → compute RSI → buy if RSI < oversold, sell if RSI > overbought
- **ma_cross**: compute short/long moving averages → buy on golden cross, sell on death cross
- **boll**: compute Bollinger Bands → buy at lower band, sell at upper band

Signal computation uses `fetch_klines()` (already available) for historical price data.

### 3. User Allocation (Subscription Side)

`BotSubscription` table gets new column: `allocated_usdt NUMERIC(18, 2) DEFAULT 100`

Subscription confirmation popup adds an allocation input:
- Shows current USDT balance
- User enters how much USDT to allocate to this bot
- Stored in `allocated_usdt` on subscription record

### 4. Bot Execution with Allocation

`bot_runner.py` execution changes:
- For each subscription, bot only trades within `allocated_usdt`
- Position tracking: sum of `is_bot_order=True, bot_id=X, user_id=Y` buy/sell orders to estimate current BTC held
- On buy signal: spend up to `trade_pct` % of allocated_usdt, stop if allocation exhausted
- On sell signal: sell position held from bot orders only (not user's other holdings)

## Files to Change

### Backend
- `app/models/bot.py` — add `allocated_usdt` to `BotSubscription`
- `app/services/bot_runner.py` — implement RSI/MA/Bollinger signals, respect allocation
- `app/routers/bots.py` — accept `allocated_usdt` in subscribe endpoint
- `app/routers/admin.py` — strategy_config JSON editor support (already supports it via UpdateBotRequest)
- DB migration — add `allocated_usdt` column

### Frontend
- `app/bot-market/page.tsx` — allocation input in SubscribeModal
- `stores/botStore.ts` — pass `allocated_usdt` in subscribe call
- `app/admin/bots/page.tsx` — JSON editor for strategy_config
