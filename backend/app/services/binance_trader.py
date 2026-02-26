import hashlib
import hmac
import math
import time
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode
import httpx
from app.config import settings


def pair_to_binance_symbol(pair: str) -> str:
    return pair.replace("_", "")


# Cache exchange info per symbol to avoid repeated API calls
_symbol_filters_cache: dict[str, dict] = {}


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

    async def get_symbol_filters(self, symbol: str) -> dict:
        """Fetch and cache LOT_SIZE / MIN_NOTIONAL filters for a symbol."""
        if symbol in _symbol_filters_cache:
            return _symbol_filters_cache[symbol]

        resp = await self.client.get(
            f"{self.base_url}/api/v3/exchangeInfo",
            params={"symbol": symbol},
        )
        if resp.status_code != 200:
            raise Exception(f"Binance exchangeInfo failed: {resp.text}")

        data = resp.json()
        symbols = data.get("symbols", [])
        if not symbols:
            raise Exception(f"Symbol {symbol} not found on Binance")

        filters = {}
        for f in symbols[0].get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                filters["step_size"] = Decimal(f["stepSize"])
                filters["min_qty"] = Decimal(f["minQty"])
                filters["max_qty"] = Decimal(f["maxQty"])
            elif f["filterType"] == "NOTIONAL":
                filters["min_notional"] = Decimal(f.get("minNotional", "0"))
            elif f["filterType"] == "MIN_NOTIONAL":
                filters["min_notional"] = Decimal(f.get("minNotional", "0"))

        _symbol_filters_cache[symbol] = filters
        return filters

    def round_step_size(self, quantity: Decimal, step_size: Decimal) -> Decimal:
        """Round quantity down to nearest step_size."""
        if step_size <= 0:
            return quantity
        precision = int(round(-math.log10(float(step_size))))
        return quantity.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

    async def validate_quantity(self, symbol: str, quantity: Decimal, price: Decimal) -> Decimal:
        """Validate and adjust quantity to meet Binance LOT_SIZE and MIN_NOTIONAL."""
        filters = await self.get_symbol_filters(symbol)

        step_size = filters.get("step_size", Decimal("0.00001"))
        min_qty = filters.get("min_qty", Decimal("0"))
        min_notional = filters.get("min_notional", Decimal("0"))

        # Round to step size
        adjusted = self.round_step_size(quantity, step_size)

        # Check minimum quantity
        if adjusted < min_qty:
            raise Exception(
                f"Quantity {adjusted} below minimum {min_qty} for {symbol}"
            )

        # Check minimum notional (quantity * price)
        if min_notional > 0 and price > 0:
            notional = adjusted * price
            if notional < min_notional:
                raise Exception(
                    f"Notional {notional} USDT below minimum {min_notional} for {symbol}"
                )

        return adjusted

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
