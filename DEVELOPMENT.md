# ForLabsEX - 암호화폐 페이퍼 트레이딩 거래소

> 개발 전체 기록 문서 (2026년 2월 기준)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [아키텍처](#4-아키텍처)
5. [데이터베이스 모델](#5-데이터베이스-모델)
6. [백엔드 API](#6-백엔드-api)
7. [프론트엔드 페이지 & 컴포넌트](#7-프론트엔드-페이지--컴포넌트)
8. [핵심 서비스](#8-핵심-서비스)
9. [자동매매 봇 시스템](#9-자동매매-봇-시스템)
10. [실시간 시장 데이터](#10-실시간-시장-데이터)
11. [개발 이슈 & 해결 기록](#11-개발-이슈--해결-기록)
12. [실행 방법](#12-실행-방법)

---

## 1. 프로젝트 개요

**ForLabsEX**는 실제 자금 없이 암호화폐 거래를 체험할 수 있는 **페이퍼 트레이딩 플랫폼**이다.

### 주요 기능
- 실시간 시세 기반 현물 거래 (BTC, ETH, BNB, SOL / USDT 마켓)
- 자동매매 봇 구독 및 전략 실행
- 지갑 잔액 및 자산 현황 조회
- 봇 성과 추적 (수익률, 승률, 최대낙폭, 샤프비율)
- 관리자 봇 생성/관리 패널

### 페이퍼 트레이딩 규칙
- 신규 가입 시 **10,000 USDT** 지급
- 실제 Binance 시세 연동 (WebSocket 실시간)
- 모든 주문은 현재 시장가 기준 즉시 체결

---

## 2. 기술 스택

| 영역 | 기술 | 버전 |
|------|------|------|
| Frontend | Next.js | 16.1.6 |
| Frontend | React | 19.2.3 |
| Frontend | TypeScript | 5.x |
| Frontend | Tailwind CSS | v4 |
| Frontend 상태관리 | Zustand | 5.x |
| Frontend 차트 | lightweight-charts | 5.x |
| Backend | FastAPI | 0.115.0 |
| Backend | Python | 3.9+ |
| Backend | uvicorn | 0.32.0 |
| ORM | SQLAlchemy | 2.0 (async) |
| DB 드라이버 | asyncpg | 0.30.0 |
| DB | PostgreSQL | 14+ |
| 캐시 | Redis | 5.x |
| 인증 | JWT (python-jose) + bcrypt | - |
| 스케줄러 | APScheduler | 3.10 |
| 마켓 데이터 | Binance REST + WebSocket | - |

---

## 3. 디렉토리 구조

```
crypto-exchange/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 앱, lifespan 이벤트
│   │   ├── config.py               # 환경변수 설정 (pydantic-settings)
│   │   ├── database.py             # SQLAlchemy async 엔진 & 세션
│   │   ├── models/
│   │   │   ├── user.py             # User 모델
│   │   │   ├── wallet.py           # Wallet 모델
│   │   │   ├── order.py            # Order, Trade 모델
│   │   │   ├── bot.py              # Bot, BotSubscription, BotPerformance 모델
│   │   │   └── notification.py    # Notification 모델
│   │   ├── routers/
│   │   │   ├── auth.py             # 인증 API
│   │   │   ├── market.py           # 시장 데이터 API
│   │   │   ├── orders.py           # 주문 API
│   │   │   ├── wallet.py           # 지갑 API
│   │   │   ├── bots.py             # 봇 API
│   │   │   ├── admin.py            # 관리자 API
│   │   │   └── ws.py               # WebSocket 엔드포인트
│   │   ├── services/
│   │   │   ├── market_data.py      # Binance WS 연결, Redis 캐싱
│   │   │   ├── bot_runner.py       # 봇 신호 생성 & 주문 실행
│   │   │   ├── bot_eviction.py     # 봇 성과 기반 퇴출
│   │   │   ├── matching_engine.py  # 주문 체결 엔진
│   │   │   └── indicators.py       # 기술적 지표 (RSI, MA, Bollinger)
│   │   └── core/
│   │       ├── deps.py             # FastAPI 의존성 주입
│   │       ├── security.py         # JWT, bcrypt
│   │       └── redis.py            # Redis 연결 풀
│   ├── alembic/                    # DB 마이그레이션
│   ├── tests/                      # pytest 테스트
│   └── requirements.txt
│
└── frontend/
    ├── app/
    │   ├── layout.tsx              # Root 레이아웃 (Navbar 포함)
    │   ├── globals.css             # CSS 변수, 글로벌 스타일
    │   ├── (auth)/
    │   │   ├── login/page.tsx      # 로그인 페이지
    │   │   └── register/page.tsx   # 회원가입 페이지
    │   ├── exchange/[pair]/page.tsx # 현물 거래소
    │   ├── futures/[pair]/page.tsx # 선물 거래소
    │   ├── wallet/page.tsx         # 지갑/자산 페이지
    │   ├── bot-market/page.tsx     # 봇 마켓
    │   ├── my-bots/page.tsx        # 내 봇 관리
    │   ├── otc/page.tsx            # OTC 거래
    │   ├── announcements/page.tsx  # 공지사항
    │   └── admin/bots/page.tsx     # 관리자 패널
    ├── components/
    │   ├── Navbar.tsx              # 내비게이션 바
    │   └── exchange/               # 거래소 컴포넌트들
    ├── stores/
    │   ├── authStore.ts            # 인증 상태
    │   ├── marketStore.ts          # 실시간 시장 데이터
    │   ├── orderStore.ts           # 주문 상태
    │   ├── botStore.ts             # 봇 상태
    │   └── pairListStore.ts        # 페어 목록
    └── lib/
        └── api.ts                  # API 요청 헬퍼 (apiFetch)
```

---

## 4. 아키텍처

```
브라우저 (Next.js)
    │
    ├─ REST API ──────────────► FastAPI (localhost:8000)
    │                               │
    └─ WebSocket ────────────────►  │
                                    ├─ PostgreSQL (영속 데이터)
                                    ├─ Redis (캐시, 봇 상태)
                                    └─ Binance WS (실시간 시세)
```

### 실시간 데이터 흐름
```
Binance WebSocket
    │  btcusdt@ticker / @depth20 / @trade
    ▼
market_data.py (백그라운드 루프)
    │  Redis 저장: market:{pair}:ticker, :orderbook, :trades
    ▼
ConnectionManager.broadcast()
    │  연결된 모든 브라우저 클라이언트에게 push
    ▼
marketStore.ts (Zustand)
    │  throttle 적용 (~5 FPS)
    ▼
React 컴포넌트 렌더링
```

### 봇 실행 흐름
```
bot_runner_loop() (10초마다 실행)
    │
    ├─ generate_signal(bot, pair)    // Redis 쿨다운 체크 → 전략별 신호
    │
    └─ 구독자별 주문 생성
           │
           ▼
        try_fill_order(order)         // Redis 현재가 조회
           │
           ▼
        Wallet 잔액 업데이트           // buy: USDT↓ BTC↑ / sell: BTC↓ USDT↑
           │
           ▼
        Trade 레코드 생성              // 실제 체결가 저장
```

---

## 5. 데이터베이스 모델

### User
```python
id, email, password_hash, role (user/admin)
is_subscribed, subscription_expires_at, created_at
```

### Wallet
```python
id, user_id FK, asset (USDT/BTC/ETH/...), balance, locked_balance
```

### Order
```python
id, user_id FK, pair (BTC_USDT 등), side (buy/sell), type (market/limit)
price, quantity, filled_quantity, status (open/filled/cancelled)
is_bot_order, bot_id FK, created_at
```

### Trade
```python
id, order_id FK, price, quantity, executed_at
# 주문 체결 시 실제 체결가/수량 기록 (시장가 주문의 경우 Order.price = NULL이므로
# Trade.price가 실제 체결가의 정확한 출처)
```

### Bot
```python
id, name, description, strategy_type (alternating/rsi/ma_cross/boll)
strategy_config (JSON), status (active/evicted), monthly_fee, created_at
```

### BotSubscription
```python
id, user_id FK, bot_id FK, is_active, started_at, ended_at, allocated_usdt
```

### BotPerformance
```python
id, bot_id FK, period (YYYY-MM), win_rate, monthly_return_pct
max_drawdown_pct, sharpe_ratio, total_trades
```

---

## 6. 백엔드 API

### 인증 `/api/auth`
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/register` | 회원가입 (USDT 10,000 자동 지급) |
| POST | `/login` | 로그인 → JWT 반환 |
| GET | `/me` | 현재 유저 정보 |

### 시장 데이터 `/api/market`
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/{pair}/ticker` | 현재가, 변동률, 거래량 |
| GET | `/{pair}/orderbook` | 매수/매도 호가창 |
| GET | `/{pair}/trades` | 최근 체결 내역 |
| GET | `/{pair}/klines` | 캔들 차트 데이터 |

### 주문 `/api/orders`
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/` | 주문 생성 (시장가/지정가) |
| DELETE | `/{order_id}` | 주문 취소 |
| GET | `/open` | 미체결 주문 목록 |
| GET | `/history` | 주문 내역 (최근 100건) |

### 지갑 `/api/wallet`
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 자산별 잔액 + 현재 시세 환산 USDT 가치 |
| POST | `/deposit` | (관리자) 유저에게 자산 입금 |

### 봇 `/api/bots`
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 전체 봇 목록 |
| GET | `/my` | 내 구독 봇 목록 (실시간 P&L 포함) |
| POST | `/{id}/subscribe` | 봇 구독 (allocated_usdt 지정) |
| DELETE | `/{id}/subscribe` | 봇 연동 해제 (`?settle=true`로 포지션 정산 가능) |
| GET | `/{id}/position` | 봇의 현재 보유 포지션 |
| GET | `/{id}/trades` | 봇 거래 내역 (체결가 포함) |

### WebSocket `/ws/market/{pair}`
- 연결 즉시 스냅샷 전송 (ticker + orderbook + trades)
- 이후 Binance WS 업데이트 시마다 브로드캐스트

---

## 7. 프론트엔드 페이지 & 컴포넌트

### 거래소 `/exchange/[pair]`
- `ChartWidget`: lightweight-charts 기반 캔들차트 (1m/5m/15m/1h/4h/1d)
- `Orderbook`: 매수/매도 호가 실시간 표시
- `OrderForm`: 시장가/지정가 주문 입력폼
- `OpenOrders`: 미체결 주문 목록 + 취소 버튼
- `RecentTrades`: 최근 체결 내역
- `PairList`: 거래 페어 전환 (Binance API로 전체 USDT 페어 조회)

### 지갑 `/wallet`
- 보유 자산별 카드 (자산 아이콘, 현재 시세, USDT 환산 가치)
- 총 자산 합계 (USDT 기준)
- 비USDT 자산의 포트폴리오 비중 바

### 봇 마켓 `/bot-market`
- 봇 카드 그리드 (전략 타입, 수익률, 승률, 구독자 수)
- 구독 모달 (투자 금액 입력)

### 내 봇 `/my-bots`
- 요약 바: 연동된 봇 수, 운영 중 봇 수, 총 투자 금액
- 봇 카드:
  - 투자 금액 + 수익/손실 (USDT 절대값 + %)
  - 통계 그리드: 승률, 최대낙폭(MDD), 샤프 비율
  - 최근 거래 내역 토글 (체결가 포함)
  - 연동 해제 버튼 → 포지션 정산 모달
    - 전량 매도 후 해제 (보유 BTC → USDT 전환)
    - 그냥 해제 (BTC 그대로 보유)

### 관리자 패널 `/admin/bots`
- 봇 목록, 상태, 구독자 수
- 봇 생성/수정/삭제/킬스위치

---

## 8. 핵심 서비스

### matching_engine.py - 주문 체결 엔진

```python
async def try_fill_order(db, order):
    # Redis에서 현재가 조회
    # 시장가: 즉시 체결
    # 지정가: 조건 충족 시 체결
    # 지갑 잔액 업데이트 (원자적)
    # Trade 레코드 생성 (실제 체결가 저장)
```

**중요**: 시장가 주문은 `Order.price = NULL`이며, 실제 체결가는 **`Trade.price`에만 저장**된다.

### indicators.py - 기술적 지표

```python
calc_rsi(closes, period=14)         # 과매도 <30, 과매수 >70
calc_ma(closes, period)             # 단순 이동평균
calc_bollinger(closes, period, std) # (lower_band, upper_band)
```

### bot_runner.py - 봇 실행 루프

- 10초 간격으로 모든 `active` 상태 봇 순회
- 각 봇마다 `generate_signal()` 호출
- 신호 발생 시 구독자별 시장가 주문 생성 및 즉시 체결
- Redis 쿨다운 키 (`bot:{id}:last_trade_time`) 로 신호 간격 제어

### _calc_live_stats() - 실시간 성과 계산

`/api/bots/my` 엔드포인트에서 호출. 정적 `BotPerformance` 테이블 대신 **실제 체결 기록에서 직접 계산**:

```
P&L = (매도 수익 합계 + 미실현 포지션 가치) - 매수 비용 합계
수익률 = P&L / 투자금액 × 100
승률 = 평균 매수 원가보다 높은 가격에 매도한 건수 / 전체 매도 건수
최대낙폭 = 거래 시점별 포트폴리오 가치 추적 → 최고점 대비 최대 낙폭
샤프비율 = 거래별 수익률의 평균 / 표준편차 (2건 이상일 때 계산)
```

---

## 9. 자동매매 봇 시스템

### 지원 전략

| 전략 | strategy_type | 신호 로직 |
|------|--------------|----------|
| 교차매매 | `alternating` | 매수/매도 교대 반복 (쿨다운: `signal_interval`초) |
| RSI | `rsi` | RSI < `oversold`(30) → 매수, RSI > `overbought`(70) → 매도 |
| MA 크로스 | `ma_cross` | 골든크로스(단기 MA > 장기 MA) → 매수, 데드크로스 → 매도 |
| 볼린저밴드 | `boll` | 하단밴드 터치 → 매수, 상단밴드 터치 → 매도 |

### strategy_config 예시

```json
{
  "pair": "BTC_USDT",
  "signal_interval": 300,
  "trade_pct": 10,

  // RSI 전략:
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,

  // MA 크로스 전략:
  "fast_period": 5,
  "slow_period": 20,

  // 볼린저밴드 전략:
  "period": 20,
  "deviation": 2.0
}
```

### 봇 구독 & 자금 관리

- 구독 시 `allocated_usdt` 설정 (기본 100 USDT)
- 봇은 할당 금액 내에서만 거래 (`trade_pct`% 씩 분할 매매)
- 이미 배포된 자금이 할당금액을 초과하면 추가 매수 중단
- 매도 시 보유 잔액의 `trade_pct`% 매도

### 봇 퇴출 시스템 (bot_eviction.py)

자동 퇴출 조건:
- 월 수익률 < 0%
- 승률 < 70%
- 최대낙폭 > `max_drawdown_limit`

퇴출 시 동작:
1. Redis `bot:{id}:kill_switch` 플래그 설정
2. 미체결 주문 전량 취소
3. 구독자 구독 비활성화
4. 구독자에게 알림 발송

---

## 10. 실시간 시장 데이터

### Binance WebSocket 스트림

```
{pair}@ticker          → 가격, 변동률, 고가, 저가, 거래량
{pair}@depth20@100ms   → 호가창 상위 20레벨 (100ms 간격)
{pair}@trade           → 개별 체결 내역
```

**중요**: `@ticker` 스트림 사용 (`@miniTicker`는 `P` 필드 없음 → KeyError 버그)

### Redis 캐시 키

```
market:{pair}:ticker      # JSON: last_price, change_pct, high, low, volume
market:{pair}:orderbook   # JSON: {bids: [[price, qty],...], asks: [[price, qty],...]}
market:{pair}:trades      # JSON array: 최근 체결 내역
```

### 봇 관련 Redis 키

```
bot:{id}:last_trade_time  # Unix timestamp: 마지막 신호 시간 (쿨다운)
bot:{id}:last_side        # buy/sell: 교차매매 마지막 방향
bot:{id}:kill_switch      # 퇴출된 봇 플래그
```

---

## 11. 개발 이슈 & 해결 기록

### 이슈 1: 봇 자동매매 미작동 (2026-02)

**증상**: 봇 러너가 실행되고 있었으나 16분 이상 주문이 발생하지 않음

**원인**: `@miniTicker` 스트림은 `P` 필드(가격 변동률)가 없어서 `data["P"]` 접근 시 `KeyError` 발생. 예외가 모두 catch되어 Redis에 ticker 데이터가 저장되지 않음. 봇 러너는 `if not ticker: continue`로 스킵.

**해결**:
```python
# 수정 전
stream = f"{sym}@miniTicker/{sym}@depth20@100ms/{sym}@trade"
if "@miniTicker" in stream_name:  # KeyError 발생

# 수정 후
stream = f"{sym}@ticker/{sym}@depth20@100ms/{sym}@trade"
if "@ticker" in stream_name and "@depth" not in stream_name:  # 정상
```

---

### 이슈 2: 거래 내역 가격 표시 안 됨 (2026-02)

**증상**: 내 봇 페이지 거래 내역에서 가격 컬럼이 `-`로 표시

**원인**: 봇 주문은 시장가(`OrderType.market`)로 생성되어 `Order.price = NULL`. 기존 코드는 `float(o.price) if o.price else None`을 반환했음. 실제 체결가는 `Trade` 테이블의 `trade.price`에 저장됨.

**해결**:
```python
# bot_trades 엔드포인트에서 Trade 테이블 조인
trade = await db.scalar(select(Trade).where(Trade.order_id == o.id))
fill_price = float(trade.price) if trade else (float(o.price) if o.price else None)
```

---

### 이슈 3: 봇 통계 전부 0.0% (2026-02)

**증상**: 내 봇 카드에 승률/수익률/MDD 모두 0.0%

**원인**: `BotPerformance` 테이블이 실제 거래 후 업데이트되지 않음. `/api/bots/my`는 `BotPerformance` 테이블을 조회하는 `_bot_dict()`를 사용했으나, 해당 테이블에 실제 거래 반영 로직이 없었음.

**해결**: `_calc_live_stats()` 함수 추가. `Order` + `Trade` 테이블에서 직접 계산:
- P&L, 수익률: 매수비용 vs (매도수익 + 미실현 포지션 가치)
- 승률: 평균 매수 원가 대비 수익 매도 비율
- MDD: 거래 시점별 포트폴리오 가치 시계열로 최대낙폭 계산
- 샤프비율: 거래별 수익률의 평균/표준편차

---

### 이슈 4: 봇 연동 해제 시 포지션 처리 (2026-02)

**요구사항**: 봇이 BTC를 보유 중일 때 연동 해제하면 어떻게 처리할지 정책 결정

**결정**: 팝업으로 두 가지 옵션 제공
- **전량 매도 후 해제**: `?settle=true` → 순매수 수량 계산 → 시장가 매도 → 구독 비활성화
- **그냥 해제**: `?settle=false` → BTC 보유 유지, 구독만 비활성화

**구현**:
```python
# DELETE /api/bots/{id}/subscribe?settle=true
if settle and net_qty > 0:
    sell_order = Order(type=OrderType.market, side=OrderSide.sell, quantity=net_qty, ...)
    await try_fill_order(db, sell_order)
sub.is_active = False
```

---

## 12. 실행 방법

### 사전 준비
```bash
# PostgreSQL 실행 (포트 5432)
# Redis 실행 (포트 6379)
```

### 백엔드

```bash
cd crypto-exchange/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env 파일 생성
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://user:password@localhost/forlab
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
EOF

# DB 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 프론트엔드

```bash
cd crypto-exchange/frontend
npm install

# .env.local 파일 생성 (선택)
# NEXT_PUBLIC_API_URL=http://localhost:8000

# 개발 서버
npm run dev
# → http://localhost:3000
```

### 관리자 설정

1. DB에서 유저 role을 `admin`으로 변경
2. `/admin/bots`에서 봇 생성
3. `/api/wallet/deposit`으로 테스트 유저에게 USDT 지급

---

## 부록: 지원 트레이딩 페어

| 페어 | Binance 심볼 |
|------|-------------|
| BTC/USDT | BTCUSDT |
| ETH/USDT | ETHUSDT |
| BNB/USDT | BNBUSDT |
| SOL/USDT | SOLUSDT |

## 부록: CSS 변수 (globals.css)

```css
--bg-base       /* 최외곽 배경 */
--bg-secondary  /* 네비게이션 바 배경 */
--bg-panel      /* 카드/패널 배경 */
--border        /* 구분선 색상 */
--text-primary  /* 주요 텍스트 */
--text-secondary /* 보조 텍스트 */
--blue          /* 강조 색상 (버튼, 링크) */
--green         /* 양수/매수 색상 */
--red           /* 음수/매도 색상 */
```
