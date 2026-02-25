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
