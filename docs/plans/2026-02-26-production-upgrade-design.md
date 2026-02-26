# ForLabsEX Production Upgrade Design

## Overview

Upgrade ForLabsEX from a paper-trading platform to a production auto-trading system with real Binance execution, MetaMask authentication, and Polygon USDT subscription payments.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Authentication | MetaMask EIP-191 only (replace email/password) |
| Trading | Operator single Binance account |
| Payment | Polygon USDT monthly manual payment |
| Capital | Operator capital pool, user P&L tracked in DB |
| Admin | Hardcoded wallet address in env var |
| Deployment | Railway (Singapore region) |
| Chart | DO NOT MODIFY |

## 1. MetaMask Authentication (EIP-191)

### Flow
1. Frontend: "Connect Wallet" → `eth_requestAccounts`
2. `GET /api/auth/nonce?address=0x...` → random nonce in Redis (5min TTL)
3. Frontend: `personal_sign` message: `"ForLabsEX Login\nNonce: {nonce}"`
4. `POST /api/auth/verify` → `eth_account.recover_message` verification
5. Success → create/get User → JWT (24h)

### DB Changes
```python
class User:
    # REMOVE: email, password_hash
    # ADD:
    wallet_address: str  # 0x... unique, indexed
    # KEEP: role, is_subscribed, subscription_expires_at, created_at
```

### Admin Detection
```python
# config.py
ADMIN_WALLET_ADDRESS: str  # env var

# deps.py
if user.wallet_address.lower() != settings.ADMIN_WALLET_ADDRESS.lower():
    raise HTTPException(403)
```

### Packages
- Backend: `eth-account`, `web3`
- Frontend: browser `window.ethereum` (no package needed)

## 2. Real Binance Trading

### New Service: `services/binance_trader.py`
```python
class BinanceTrader:
    async def place_market_order(symbol, side, quantity)  # POST /api/v3/order
    async def get_order_status(symbol, order_id)          # GET /api/v3/order
    async def get_account_balance()                       # GET /api/v3/account
```

### Bot Runner Changes
- Replace simulated `try_fill_order()` with real Binance API calls
- Use actual fill prices from Binance response for Trade records
- Check Binance balance before placing orders

### Environment Variables
```
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BINANCE_LIVE_TRADING=true  # false = simulation mode (dev)
```

### Safety
- `BINANCE_LIVE_TRADING=false` default
- Pre-order balance check on Binance
- Full order logging
- Existing eviction system maintained (drawdown > 20%)

## 3. Bot Subscription Payment (Polygon USDT)

### Payment Flow
1. User selects bot → "Subscribe"
2. Frontend: MetaMask sends Polygon USDT to `ADMIN_WALLET_ADDRESS`
   - Network: Polygon (chainId: 137)
   - Token: USDT (`0xc2132D05D31c914a87C6611C10748AEb04B58e8F`)
   - Amount: bot's `monthly_fee`
3. Get txHash
4. `POST /api/bots/{id}/subscribe` with `{ tx_hash, allocated_usdt }`
5. Backend verifies via Polygon RPC: recipient, amount, token
6. Verification OK → activate subscription, `expires_at` = +30 days

### New Service: `services/payment_verifier.py`
- Fetch transaction receipt via Polygon RPC
- Parse ERC-20 Transfer event
- Verify to == admin, amount >= expected
- Check tx_hash not already used (dedup)

### Subscription Renewal
- APScheduler: 3 days before expiry → notification
- On expiry: `is_active = False`, bot stops trading
- User pays again → same flow → renew

### DB Changes
```python
class BotSubscription:
    # ADD: tx_hash, payment_amount, expires_at

class PaymentHistory:  # NEW
    id, user_id, bot_id, tx_hash, amount, network, verified_at
```

## 4. Admin Subscription Management

### New Page: `/admin/subscriptions`

| Feature | Description |
|---------|-------------|
| Subscription list | All active/expired (wallet, bot, expiry, status) |
| Payment history | PaymentHistory table (txHash, amount, date) |
| Manual toggle | Admin can activate/deactivate subscriptions |
| Expiry alerts | Highlight subscriptions expiring within 3 days |
| Filter/search | By wallet address, bot name, status |

### New API Endpoints
```
GET    /api/admin/subscriptions         # List all (paginated)
GET    /api/admin/subscriptions/stats   # Stats (active, expired, revenue)
PUT    /api/admin/subscriptions/{id}    # Manual activate/deactivate
GET    /api/admin/payments              # Payment history
```

## 5. Railway Deployment (Singapore)

- Backend + Frontend as separate Railway services
- Region: `asia-southeast1` (Singapore)
- PostgreSQL + Redis via Railway add-ons
- Environment variables:
  - `BINANCE_API_KEY`, `BINANCE_API_SECRET`
  - `ADMIN_WALLET_ADDRESS`
  - `BINANCE_LIVE_TRADING=true`
  - `POLYGON_RPC_URL`
  - `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`

## 6. DO NOT MODIFY

- `ChartWidget.tsx` and all chart-related code
- `market_data.py` WebSocket streams
- Exchange UI layout
- 28 coin pair list
- Indicator calculations
- Orderbook/trade display components

## Migration Notes

- Alembic migration: drop email/password_hash columns, add wallet_address
- Existing test users will be invalid (MetaMask-only going forward)
- Seed admin user with `ADMIN_WALLET_ADDRESS` on first login
