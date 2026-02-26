# ForLabsEX — 프로젝트 종합 가이드

> **목적**: AI(Claude 등)가 다른 세션에서도 이 프로젝트를 완전히 이해하고 유지보수할 수 있도록 작성된 문서.
> **최종 업데이트**: 2026-02-26

---

## 1. 프로젝트 개요

**ForLabsEX**는 암호화폐 자동매매 봇 플랫폼이다.

- 사용자는 MetaMask로 로그인하고, Polygon USDT를 입금한 뒤, 자동매매 봇을 구독한다.
- 봇은 Binance에서 실제로 코인을 사고 팔며, 수익/손실이 사용자 계정에 반영된다.
- 관리자(운영자)가 봇을 생성·관리하고, 출금 요청을 승인한다.
- **거래소 차트 페이지**(`/exchange/[pair]`)는 실시간 Binance 데이터를 보여주며, 절대 건들지 말 것.

**GitHub**: `https://github.com/forlabsio/forlabs_exchange.git` (main)
**배포**: Railway (싱가포르 리전)

---

## 2. 기술 스택

### Backend
| 항목 | 기술 |
|------|------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| DB | PostgreSQL + asyncpg |
| Cache | Redis |
| 스케줄러 | APScheduler |
| 인증 | JWT (python-jose) + MetaMask EIP-191 |
| Web3 | web3.py, eth-account |
| 실시간 | Binance WebSocket |

### Frontend
| 항목 | 기술 |
|------|------|
| Framework | Next.js 16 |
| Language | TypeScript |
| Styling | Tailwind CSS v4 |
| State | Zustand |
| Charts | lightweight-charts |
| Icons | lucide-react |

### 인프라
| 항목 | 기술 |
|------|------|
| Hosting | Railway.app (싱가포르) |
| DB | PostgreSQL (Railway managed) |
| Cache | Redis (Railway managed) |
| Build | Nixpacks |

---

## 3. 자금 흐름 (핵심 아키텍처)

```
┌─────────────────────────────────────────────────────────┐
│                    사용자 자금 순환                        │
│                                                         │
│  ① 입금: MetaMask → Polygon USDT → 관리자 지갑           │
│     └→ POST /api/wallet/deposit/verify (tx_hash 검증)    │
│     └→ DB: wallet.balance += amount                     │
│                                                         │
│  ② 봇 구독: wallet.balance → wallet.locked_balance       │
│     └→ POST /api/bots/{id}/subscribe                    │
│     └→ 잔액 부족 시 차단 (balance < allocated_usdt)       │
│     └→ monthly_fee > 0 이면 Polygon USDT 결제 검증       │
│                                                         │
│  ③ 자동매매: bot_runner → Binance 매수/매도               │
│     └→ Order + Trade 기록 (per user, per bot)            │
│     └→ BINANCE_LIVE_TRADING=true → 실제 거래             │
│     └→ BINANCE_LIVE_TRADING=false → 시뮬레이션           │
│                                                         │
│  ④ 정산 (구독 해지 시):                                   │
│     └→ DELETE /api/bots/{id}/subscribe?settle=true       │
│     └→ 잔여 포지션 시장가 매도                             │
│     └→ calc_bot_stats() → PnL 계산                      │
│     └→ locked_balance -= allocated                      │
│     └→ balance += allocated + pnl (원금 + 수익)          │
│                                                         │
│  ⑤ 출금:                                                │
│     └→ POST /api/wallet/withdraw (사용자 요청)            │
│     └→ 관리자 승인 → Polygon USDT 송금 → tx_hash 입력     │
│     └→ PUT /api/admin/withdrawals/{id}/approve           │
└─────────────────────────────────────────────────────────┘
```

### 잔액 구조
- `wallet.balance`: 출금 가능한 잔액 (unlocked)
- `wallet.locked_balance`: 봇에 투자 중인 잔액 (locked)
- 출금 가능 금액 = `balance - pending_withdrawals`
- 봇 수익은 구독 해지 전까지 locked 상태

---

## 4. 디렉토리 구조

```
forlabs-auto-exchange/
├── backend/
│   ├── alembic/versions/       # DB 마이그레이션 (6개)
│   ├── app/
│   │   ├── main.py             # FastAPI 앱, 라우터 등록, 백그라운드 태스크
│   │   ├── config.py           # 환경변수 설정 (pydantic)
│   │   ├── database.py         # SQLAlchemy async engine
│   │   ├── core/
│   │   │   ├── deps.py         # 인증 의존성 (get_current_user, require_admin)
│   │   │   ├── security.py     # JWT 생성/검증
│   │   │   └── redis.py        # Redis 연결
│   │   ├── models/
│   │   │   ├── user.py         # User (wallet_address, role)
│   │   │   ├── wallet.py       # Wallet (balance, locked_balance)
│   │   │   ├── order.py        # Order, Trade
│   │   │   ├── bot.py          # Bot, BotSubscription, BotPerformance
│   │   │   ├── payment.py      # PaymentHistory (tx_hash 중복 방지)
│   │   │   ├── withdrawal.py   # Withdrawal (출금 요청)
│   │   │   └── notification.py # Notification
│   │   ├── routers/
│   │   │   ├── auth.py         # /api/auth (nonce, verify, me)
│   │   │   ├── market.py       # /api/market (ticker, orderbook, klines)
│   │   │   ├── ws.py           # /ws/market/{pair} (WebSocket)
│   │   │   ├── orders.py       # /api/orders (place, cancel, history)
│   │   │   ├── wallet.py       # /api/wallet (balance, deposit, withdraw)
│   │   │   ├── bots.py         # /api/bots (list, subscribe, trades)
│   │   │   └── admin.py        # /api/admin (봇/구독/출금 관리)
│   │   ├── schemas/
│   │   │   ├── auth.py         # NonceResponse, VerifyRequest
│   │   │   ├── bot.py          # CreateBotRequest, UpdateBotRequest
│   │   │   └── order.py        # PlaceOrderRequest
│   │   └── services/
│   │       ├── market_data.py  # Binance WebSocket → Redis 캐싱
│   │       ├── bot_runner.py   # 봇 실행 루프 (10초 간격)
│   │       ├── strategies.py   # 5개 전략 클래스
│   │       ├── indicators.py   # RSI, MA, Bollinger, ATR, ADX, Donchian
│   │       ├── matching_engine.py  # 주문 체결 (시뮬 + 실거래)
│   │       ├── binance_trader.py   # Binance API 실거래
│   │       ├── payment_verifier.py # Polygon USDT 트랜잭션 검증
│   │       ├── bot_eviction.py     # 봇 자동 퇴출 + 성과 집계
│   │       ├── position_manager.py # SL/TP/Trailing 관리 (Redis)
│   │       └── stats.py           # 사용자별 봇 PnL 계산
│   ├── tests/                  # 10개 테스트 모듈 (55+ tests)
│   ├── requirements.txt
│   └── railway.toml
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx          # Root 레이아웃 (Navbar)
│   │   ├── globals.css         # CSS 변수, 다크 테마
│   │   ├── (auth)/login/       # MetaMask 로그인
│   │   ├── exchange/[pair]/    # ⚠️ 거래소 차트 (절대 수정 금지)
│   │   ├── wallet/             # 자산 관리 (입금/출금)
│   │   ├── bot-market/         # 봇 마켓 (구독)
│   │   ├── my-bots/            # 내 봇 (관리/정산)
│   │   ├── admin/bots/         # 관리자: 봇 CRUD
│   │   ├── admin/subscriptions/# 관리자: 구독 관리
│   │   └── admin/withdrawals/  # 관리자: 출금 승인
│   ├── components/
│   │   ├── Navbar.tsx
│   │   └── exchange/           # ChartWidget, OrderForm, Orderbook 등
│   ├── stores/                 # Zustand (auth, market, order, bot, pairList)
│   ├── lib/
│   │   ├── api.ts              # apiFetch() 헬퍼
│   │   └── indicators.ts       # 프론트엔드 기술적 지표
│   └── railway.toml
│
└── docs/
    ├── PROJECT_GUIDE.md        # ← 이 파일
    └── plans/                  # 구현 계획 문서들
```

---

## 5. 데이터베이스 모델

### users
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| wallet_address | String, unique | MetaMask 주소 |
| role | Enum(user/admin) | 기본값: user |
| is_subscribed | Boolean | 구독 상태 |
| subscription_expires_at | DateTime | |
| created_at | DateTime | |

### wallets
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| user_id | FK → users | |
| asset | String(20) | "USDT", "BTC", "ETH" 등 |
| balance | Numeric(20,8) | 출금 가능 잔액 |
| locked_balance | Numeric(20,8) | 봇에 투자 중인 잔액 |

### bots
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| name | String(100) | |
| description | String(500) | |
| strategy_type | String(30) | trend_ma200, rsi_trend, boll_adx, adaptive_grid, breakout_lite |
| strategy_config | JSON | 전략 파라미터 (pair, risk_pct 등) |
| status | Enum(active/evicted) | |
| max_drawdown_limit | Numeric(5,2) | 최대 허용 MDD (기본 20%) |
| monthly_fee | Numeric(10,2) | 월 구독료 (0 = 무료) |
| created_at, evicted_at | DateTime | |

### bot_subscriptions
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| user_id | FK → users | |
| bot_id | FK → bots | |
| is_active | Boolean | |
| allocated_usdt | Numeric(18,2) | 투자 원금 |
| tx_hash | String | 결제 증명 (Polygon) |
| payment_amount | Numeric(18,6) | 지불한 수수료 |
| expires_at | DateTime | 30일 후 만료 |
| started_at, ended_at | DateTime | |

### orders
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| user_id | FK → users | |
| pair | String(20) | "BTC_USDT" |
| side | Enum(buy/sell) | |
| type | Enum(limit/market) | |
| price | Numeric(20,8) | limit 주문 가격 |
| quantity | Numeric(20,8) | |
| filled_quantity | Numeric(20,8) | |
| status | Enum(open/filled/cancelled) | |
| is_bot_order | Boolean | 봇이 생성한 주문 여부 |
| bot_id | FK → bots, nullable | |
| created_at | DateTime | |

### trades
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| order_id | FK → orders | |
| price | Numeric(20,8) | 체결가 |
| quantity | Numeric(20,8) | |
| executed_at | DateTime | |

### payment_history
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| user_id | FK → users | |
| bot_id | FK → bots | 0 = 입금, >0 = 봇 구독료 |
| tx_hash | String, unique | 중복 사용 방지 |
| amount | Numeric(18,6) | |
| network | String(20) | "polygon" |
| verified_at | DateTime | |

### withdrawals
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| user_id | FK → users | |
| amount | Numeric(18,6) | |
| to_address | String | 수령 지갑 주소 |
| status | Enum(pending/approved/completed/rejected) | |
| tx_hash | String, nullable | 관리자가 입력 |
| admin_note | String(500) | |
| created_at, processed_at | DateTime | |

### bot_performance
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| bot_id | FK → bots | |
| period | String(7) | "YYYY-MM" |
| win_rate, monthly_return_pct, max_drawdown_pct, sharpe_ratio | Numeric | |
| total_trades | Integer | |
| calculated_at | DateTime | |

### notifications
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| user_id | FK → users | |
| type | String(50) | |
| title | String(200) | |
| body | String(1000) | |
| is_read | Boolean | |
| created_at | DateTime | |

---

## 6. API 엔드포인트

### 인증 (`/api/auth`)
| Method | Path | Auth | 설명 |
|--------|------|------|------|
| GET | `/nonce` | - | MetaMask 서명용 nonce 생성 (Redis에 5분 TTL) |
| POST | `/verify` | - | EIP-191 서명 검증 → JWT 발급 |
| GET | `/me` | JWT | 현재 사용자 정보 |

### 시장 데이터 (`/api/market`)
| Method | Path | Auth | 설명 |
|--------|------|------|------|
| GET | `/{pair}/ticker` | - | 현재가, 24h 변동, 거래량 |
| GET | `/{pair}/orderbook` | - | 호가창 |
| GET | `/{pair}/trades` | - | 최근 체결 |
| GET | `/{pair}/klines` | - | 캔들 차트 데이터 |

### WebSocket
| Path | 설명 |
|------|------|
| `/ws/market/{pair}` | 실시간 시세 스트림 (ticker, orderbook, trade) |

### 주문 (`/api/orders`)
| Method | Path | Auth | 설명 |
|--------|------|------|------|
| POST | `/` | JWT | 주문 생성 (limit/market) |
| DELETE | `/{id}` | JWT | 주문 취소 |
| GET | `/open` | JWT | 미체결 주문 |
| GET | `/history` | JWT | 주문 내역 (최근 100건) |

### 지갑 (`/api/wallet`)
| Method | Path | Auth | 설명 |
|--------|------|------|------|
| GET | `/` | JWT | 자산 목록 + 시세 |
| POST | `/deposit/verify` | JWT | Polygon USDT 입금 검증 |
| GET | `/withdrawable` | JWT | 출금 가능 금액 계산 |
| POST | `/withdraw` | JWT | 출금 요청 |
| GET | `/withdrawals` | JWT | 출금 이력 |
| POST | `/deposit` | Admin | 관리자 수동 입금 |

### 봇 (`/api/bots`)
| Method | Path | Auth | 설명 |
|--------|------|------|------|
| GET | `/` | Optional | 전체 봇 목록 (마켓) |
| GET | `/my` | JWT | 내 구독 봇 (실시간 PnL) |
| POST | `/{id}/subscribe` | JWT | 봇 구독 (잔액 lock) |
| DELETE | `/{id}/subscribe` | JWT | 구독 해지 (정산) |
| POST | `/{id}/renew` | JWT | 구독 갱신 |
| GET | `/{id}/position` | JWT | 현재 포지션 |
| GET | `/{id}/trades` | JWT | 거래 내역 |

### 관리자 (`/api/admin`) — 모두 Admin 전용
| Method | Path | 설명 |
|--------|------|------|
| GET | `/bots` | 전체 봇 목록 (모든 상태) |
| POST | `/bots` | 봇 생성 |
| PUT | `/bots/{id}` | 봇 수정 |
| DELETE | `/bots/{id}` | 봇 삭제 (evict) |
| POST | `/bots/{id}/kill` | 긴급 정지 |
| GET | `/subscriptions` | 전체 구독 목록 |
| GET | `/subscriptions/stats` | 구독 통계 |
| PUT | `/subscriptions/{id}` | 구독 상태 변경 |
| GET | `/payments` | 결제 내역 |
| GET | `/withdrawals` | 출금 요청 목록 |
| GET | `/withdrawals/stats` | 출금 통계 |
| PUT | `/withdrawals/{id}/approve` | 출금 승인 (tx_hash 필수) |
| PUT | `/withdrawals/{id}/reject` | 출금 거절 |

---

## 7. 서비스 계층 상세

### market_data.py — Binance 실시간 데이터
- **WebSocket 스트림**: ticker, depth20, trade → Redis 캐싱
- **REST fallback**: `fetch_ticker()`, `fetch_klines()` (캐시 10~30초)
- **24개 페어** 지원 (BTC, ETH, SOL, XRP 등)
- Redis 키: `market:{pair}:ticker`, `market:{pair}:orderbook`, `market:{pair}:trades`

### bot_runner.py — 봇 실행 엔진
- **10초 간격** 루프 (`bot_runner_loop`)
- 각 봇별 활성 구독자에 대해:
  1. 만료 체크 → 비활성화
  2. 현재가 조회 (Redis)
  3. **SL/TP/Trailing 체크** → 조건 충족 시 반대 주문 (PositionManager)
  4. **시그널 생성** → 전략 클래스 호출
  5. **포지션 크기 계산** (ATR 기반 리스크 관리)
  6. **지갑 잔액 검증** → 주문 생성 → 체결
- Redis 키: `bot:{id}:last_trade_time`, `bot:{id}:kill_switch`

### strategies.py — 5개 전략

| 전략 | strategy_type | 매매 방식 |
|------|---------------|----------|
| **Trend MA200** | `trend_ma200` | 200일 이평선 위/아래 + 기울기 확인 |
| **RSI + Trend** | `rsi_trend` | RSI 과매수/과매도 + MA200 트렌드 필터 |
| **Bollinger + ADX** | `boll_adx` | 볼린저밴드 터치 + ADX 횡보 확인 (mean reversion) |
| **Adaptive Grid** | `adaptive_grid` | 격자 매수 + 트렌드 필터 (MA50/200 + ADX) |
| **Breakout Lite** | `breakout_lite` | 돈치안 채널 돌파 + 거래량/ADX 확인 |

각 전략은 `strategy_config` JSON으로 파라미터 조정 가능.

### matching_engine.py — 주문 체결
- **시뮬레이션 모드** (`try_fill_order`): Redis 시세로 즉시 체결
- **실거래 모드** (`try_fill_order_live`): Binance API 실제 주문
  - `BINANCE_LIVE_TRADING=true`일 때만 활성
  - 실패 시 시뮬레이션으로 fallback

### bot_eviction.py — 자동 퇴출
- **일일 MDD 체크** (00:00): MDD > 15% → 퇴출
- **일일 성과 집계** (00:05): BotPerformance 테이블 업데이트
- **월간 평가**: win_rate < 70% OR return < 0% → 퇴출
- **구독 만료 체크** (06:00): 3일 전 알림, 만료 시 비활성화

### payment_verifier.py — Polygon 결제 검증
- Polygon RPC로 `eth_getTransactionReceipt` 호출
- USDT 컨트랙트 Transfer 이벤트 파싱
- 수신자(관리자 지갑), 금액, 상태 검증
- USDT 컨트랙트: `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` (6 decimals)

### position_manager.py — 포지션 관리
- Redis에 포지션 상태 저장: `pos:{bot_id}:{user_id}`
- ATR 기반 SL/TP/Trailing Stop 계산
- Trailing Stop: 유리한 방향 이동 시 자동 조정 (ratcheting)

### stats.py — PnL 계산
- `calc_bot_stats(db, user_id, bot_id, allocated, pair)`:
  - 체결된 주문에서 실현 PnL 계산
  - 미실현 PnL = 현재 포지션 × (현재가 - 평균단가)
  - win_rate, max_drawdown, sharpe_ratio 계산

---

## 8. 프론트엔드 페이지

| 경로 | 설명 | 비고 |
|------|------|------|
| `/(auth)/login` | MetaMask 로그인 | EIP-191 서명 |
| `/exchange/[pair]` | 거래소 (차트 + 호가 + 주문) | **⚠️ 수정 금지** |
| `/wallet` | 내 자산 (입금/출금) | Polygon USDT |
| `/bot-market` | 봇 마켓 (구독) | 잔액 검증 |
| `/my-bots` | 내 봇 (PnL/정산) | 10초 자동 갱신 |
| `/admin/bots` | 관리자: 봇 CRUD | 전략별 설정 |
| `/admin/subscriptions` | 관리자: 구독 관리 | 통계 + 검색 |
| `/admin/withdrawals` | 관리자: 출금 승인 | tx_hash 입력 |

### Zustand 스토어
- **authStore**: 토큰, 사용자 정보, MetaMask 연결
- **marketStore**: WebSocket 실시간 데이터 (throttled 5/sec)
- **orderStore**: 주문 관리
- **botStore**: 봇 목록/구독/거래 내역
- **pairListStore**: 20개 거래 페어 (6개 카테고리)

---

## 9. 인증 시스템

```
MetaMask (브라우저)
  ↓
GET /api/auth/nonce → 랜덤 nonce (Redis, 5분 TTL)
  ↓
personal_sign: "ForLabsEX Login\nNonce: {nonce}"
  ↓
POST /api/auth/verify → EIP-191 서명 검증
  ↓
eth_account.recover_message() → wallet_address 복원
  ↓
User 생성/조회 (wallet_address로)
  ↓
JWT 발급 (HS256, 1440분 만료)
  ↓
localStorage 저장 → apiFetch() 헤더에 자동 첨부
```

### 관리자 판별
- `require_admin` 의존성: `user.wallet_address == ADMIN_WALLET_ADDRESS`
- 최초 로그인 시 ADMIN_WALLET_ADDRESS와 일치하면 `role="admin"` 설정

---

## 10. Redis 키 패턴

| 패턴 | 용도 | TTL |
|------|------|-----|
| `market:{pair}:ticker` | 현재 시세 | 30s |
| `market:{pair}:orderbook` | 호가창 | 10s |
| `market:{pair}:trades` | 최근 체결 | 60s |
| `nonce:{wallet_address}` | 인증 nonce | 5분 |
| `bot:{bot_id}:kill_switch` | 퇴출 플래그 | - |
| `bot:{bot_id}:last_trade_time` | 쿨다운 | - |
| `bot:{bot_id}:last_side` | 마지막 매매 방향 | - |
| `bot:{bot_id}:daily_mdd` | 일일 MDD | - |
| `pos:{bot_id}:{user_id}` | 포지션 상태 (SL/TP) | - |
| `grid:{pair}:state` | 그리드 전략 상태 | - |

---

## 11. 환경 변수

### Backend (.env)
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
REDIS_URL=redis://host:6379
SECRET_KEY=<32자 이상 랜덤 문자열>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Binance
BINANCE_BASE_URL=https://api.binance.com
BINANCE_API_KEY=<실거래 시 필수>
BINANCE_API_SECRET=<실거래 시 필수>
BINANCE_LIVE_TRADING=false          # true = 실제 Binance 거래

# Polygon / 결제
ADMIN_WALLET_ADDRESS=<운영자 MetaMask 주소>
POLYGON_RPC_URL=https://polygon-rpc.com

# CORS
CORS_ORIGINS=http://localhost:3000,https://your-frontend.railway.app
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_ADMIN_WALLET=<운영자 MetaMask 주소>
```

---

## 12. 배포 (Railway)

### Backend railway.toml
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
```

### Frontend railway.toml
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

### DB 마이그레이션 (6개)
1. `52e1f826084e` — 초기 스키마 (users, wallets, orders, trades, bots)
2. `a1b2c3d4e5f6` — 봇 필드 추가 (strategy_config, max_drawdown_limit 등)
3. `b2c3d4e5f6a7` — allocated_usdt 추가
4. `c3d4e5f6a7b8` — calculated_at 추가
5. `d4e5f6a7b8c9` — MetaMask 인증 + payment_history
6. `e5f6a7b8c9d0` — withdrawals 테이블

---

## 13. 지원 거래 페어

**20개 페어** (Binance 실시간):

| 카테고리 | 페어 |
|----------|------|
| Market Anchor | BTC, ETH |
| High Liquidity | SOL, XRP, BNB, AVAX, ADA, DOGE, DOT, LINK |
| L2/Scaling | ARB, OP, POL |
| AI/Infra | RENDER, FET, GRT |
| DeFi | UNI, AAVE |
| High Beta | SUI, APT |

모든 페어는 `/USDT` 기준.

---

## 14. 테스트

```bash
cd backend
pytest                          # 전체 (55+ tests)
pytest tests/test_strategies.py # 전략만
pytest -v                       # 상세 출력
```

**테스트 모듈**:
- test_auth.py — 인증/JWT
- test_indicators.py — 기술적 지표
- test_strategies.py — 전략 시그널
- test_bot_runner.py — 봇 실행 루프
- test_bot_eviction.py — 퇴출 로직
- test_position_manager.py — 포지션 관리
- test_payment_verifier.py — Polygon 검증
- test_binance_trader.py — Binance 실거래
- test_matching_engine.py — 주문 체결

---

## 15. 주의사항

### ⚠️ 절대 수정 금지
- `/exchange/[pair]` 페이지와 관련 컴포넌트 (ChartWidget, Orderbook, OrderForm 등)
- 실시간 차트와 호가창은 현재 상태가 최적

### ⚠️ 실거래 주의
- `BINANCE_LIVE_TRADING=true` 설정 시 실제 Binance에서 매매 발생
- 반드시 API 키 설정 후 활성화
- 여러 사용자가 동시 구독 시 Binance 계좌에 충분한 잔액 필요

### ⚠️ Binance 잔액 과다배분
- 현재 DB 잔액만 검증하고, 실제 Binance 잔액은 체크하지 않음
- 사용자 수 증가 시 관리자가 Binance에 충분한 자금 유지 필요

### ⚠️ 출금 프로세스
- 출금은 수동 — 관리자가 Polygon에서 USDT 송금 후 tx_hash 입력
- Binance ↔ Polygon 자동 브릿지 없음

---

## 16. 로컬 개발

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# .env 설정 후:
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

**필수 외부 서비스**: PostgreSQL, Redis (Docker 권장)

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=pass -p 5432:5432 postgres:14
docker run -d --name redis -p 6379:6379 redis:7
```
