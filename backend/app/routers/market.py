import json
from fastapi import APIRouter, HTTPException, Query
from app.core.redis import get_redis
from app.services.market_data import fetch_klines, sync_market_to_redis

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("/{pair}/ticker")
async def get_ticker(pair: str):
    redis = await get_redis()
    data = await redis.get(f"market:{pair}:ticker")
    if not data:
        try:
            await sync_market_to_redis(pair)
            data = await redis.get(f"market:{pair}:ticker")
        except Exception:
            raise HTTPException(404, "Pair not found or market data unavailable")
    if not data:
        raise HTTPException(404, "Pair not found")
    return json.loads(data)

@router.get("/{pair}/orderbook")
async def get_orderbook(pair: str):
    redis = await get_redis()
    data = await redis.get(f"market:{pair}:orderbook")
    if not data:
        raise HTTPException(404, "Orderbook not available")
    return json.loads(data)

@router.get("/{pair}/trades")
async def get_recent_trades(pair: str):
    redis = await get_redis()
    data = await redis.get(f"market:{pair}:trades")
    if not data:
        raise HTTPException(404, "Trades not available")
    return json.loads(data)

@router.get("/{pair}/klines")
async def get_klines(pair: str, interval: str = Query("1m"), limit: int = Query(500)):
    return await fetch_klines(pair, interval, limit)
