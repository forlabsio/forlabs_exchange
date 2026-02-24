# Bot Market & Admin Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 봇 마켓 카드 그리드 업그레이드 + 관리자 봇 등록 UI + 유저 내 봇 대시보드 구현

**Tech Stack:** Next.js 16, React 19, TypeScript, FastAPI, SQLAlchemy async, Alembic, Redis

---

## Architecture

### DB Changes (single Alembic migration)

**`bots` table — add 2 columns:**
- `monthly_fee` Numeric(10,2) default 0 (display only, no payment logic)
- `strategy_type` String(20) — one of: `alternating` | `rsi` | `ma_cross` | `boll`

**`bot_performance` table — add 1 column:**
- `sharpe_ratio` Numeric(8,4) default 0

`subscriber_count` and `operation_period` are computed at query time (no extra columns).

### strategy_config JSON shape per strategy type

```json
// alternating
{ "pair": "BTC_USDT", "trade_pct": 10, "signal_interval": 300 }

// rsi
{ "pair": "BTC_USDT", "trade_pct": 10, "signal_interval": 300,
  "rsi_period": 14, "overbought": 70, "oversold": 30 }

// ma_cross
{ "pair": "BTC_USDT", "trade_pct": 10, "signal_interval": 300,
  "fast_period": 5, "slow_period": 20 }

// boll
{ "pair": "BTC_USDT", "trade_pct": 10, "signal_interval": 300,
  "period": 20, "deviation": 2.0 }
```

---

## Backend API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/bots` | public | 봇 마켓 리스트 (성과+구독자수+기간 포함) |
| `GET` | `/api/bots/my` | user | 내가 구독한 봇 + 성과 |
| `GET` | `/api/bots/{id}/trades` | user | 특정 봇의 내 거래내역 |
| `GET` | `/api/admin/bots` | admin | 전체 봇 목록 (퇴출 포함) |
| `POST` | `/api/admin/bots` | admin | 봇 생성 |
| `PUT` | `/api/admin/bots/{id}` | admin | 봇 수정 |
| `DELETE` | `/api/admin/bots/{id}` | admin | 봇 퇴출 |

Admin auth: `get_current_user` + `user.email == "admin@forlabs.io"` guard.

### GET /api/bots response shape
```json
[{
  "id": 1,
  "name": "Alpha RSI Bot",
  "description": "...",
  "strategy_type": "rsi",
  "status": "active",
  "monthly_fee": 9.99,
  "subscriber_count": 42,
  "operation_days": 87,
  "performance": {
    "win_rate": 72.5,
    "monthly_return_pct": 3.4,
    "max_drawdown_pct": 8.2,
    "sharpe_ratio": 1.35
  },
  "is_subscribed": false
}]
```

---

## Frontend Pages

### 1. `/bot-market` — upgrade existing page

Card grid (1/2/3 cols responsive). Each card:
- **Top:** bot name + strategy type badge + Active/Evicted status pill
- **Stats grid (2×2):** 수익률 / MDD / 샤프비율 / 승률
- **Footer row:** 운용기간 · 구독자 수 · 월 구독료 + 구독/해지 버튼

`botStore.ts` — add `is_subscribed` field to `Bot` interface.

### 2. `/my-bots` — new page

- Header: "내 봇" + subscribed count
- Per-bot card:
  - Status badge (Active 🟢 / Evicted 🔴)
  - Performance stats: 수익률, 승률, MDD, 샤프
  - Asset allocation bar (trade_pct from strategy_config)
  - Recent trades table: time, side (BUY/SELL), quantity, price

### 3. `/admin/bots` — new page (admin only)

- Bot list table: name, strategy type, status, subscriber count, fee, created date + edit/delete buttons
- "새 봇 등록" button → modal
- Modal form fields:
  - 이름 (text)
  - 설명 (textarea)
  - 전략 타입 (select: alternating / RSI / MA Cross / Bollinger)
  - 전략 파라미터 (dynamic based on type):
    - All types: pair, trade_pct, signal_interval
    - RSI adds: rsi_period, overbought, oversold
    - MA Cross adds: fast_period, slow_period
    - Boll adds: period, deviation
  - max_drawdown_limit (number)
  - monthly_fee (number)
- Edit opens same modal pre-filled

### Navigation changes
- Add "내 봇" link for logged-in users
- Add "관리자" link visible only when `user.email === "admin@forlabs.io"`

---

## Task List

### Task 1: Alembic migration — add bot columns
**Files:** `backend/alembic/versions/xxxx_add_bot_fields.py`, `backend/app/models/bot.py`

Add `monthly_fee`, `strategy_type` to `Bot` model and `sharpe_ratio` to `BotPerformance`. Generate and apply migration.

### Task 2: Backend — admin router
**Files:** `backend/app/routers/admin_bots.py`, `backend/app/main.py`

New file `routers/admin_bots.py` with CRUD endpoints. Guard with `require_admin` dependency (email check). Register router in `main.py`.

### Task 3: Backend — enhance GET /api/bots + add /my and /trades endpoints
**Files:** `backend/app/routers/bots.py`

- `GET /api/bots`: join with `BotPerformance`, count subscriptions, compute operation_days, include `is_subscribed` if authenticated
- `GET /api/bots/my`: subscribed bots for current user with same stats
- `GET /api/bots/{id}/trades`: paginated orders where `bot_id=id AND user_id=current_user.id`

### Task 4: Frontend — upgrade `/bot-market`
**Files:** `frontend/app/bot-market/page.tsx`, `frontend/stores/botStore.ts`

Rewrite card UI with full stats. Update `botStore.ts` `Bot` interface to include all new fields.

### Task 5: Frontend — `/my-bots` page
**Files:** `frontend/app/my-bots/page.tsx`, `frontend/stores/botStore.ts`

New page. Add `fetchMyBots`, `fetchBotTrades` to store.

### Task 6: Frontend — `/admin/bots` page
**Files:** `frontend/app/admin/bots/page.tsx`

Admin-only page with table + modal form. Client-side redirect if not admin.

### Task 7: Navigation — add links
**Files:** `frontend/components/Navbar.tsx` (or equivalent)

Add "내 봇" for authenticated users, "관리자" for admin email.
