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
