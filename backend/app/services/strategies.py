"""
strategies.py - 5 Advanced Trading Strategy Classes
Each strategy generates optional buy/sell signals with ATR-based risk management.
"""

import json
from typing import Optional

from app.services.market_data import fetch_klines
from app.services.indicators import (
    calc_rsi,
    calc_ma,
    calc_bollinger,
    calc_atr,
    calc_adx,
    calc_donchian,
    calc_ma_slope,
    calc_bandwidth,
)
from app.core.redis import get_redis


# ---------------------------------------------------------------------------
# Strategy 1: TrendMA200Strategy
# ---------------------------------------------------------------------------

class TrendMA200Strategy:
    """Trend-following strategy using 200-period MA with slope confirmation.

    BUY:  last N closes ALL above MA AND slope > 0
    SELL: last N closes ALL below MA AND slope < 0
    Uses trailing stop only (no take-profit).
    """

    TYPE = "trend_ma200"

    def __init__(self, config: dict):
        self.ma_period = config.get("ma_period", 200)
        self.confirmation = config.get("confirmation", 3)
        self.ma_slope_lookback = config.get("ma_slope_lookback", 10)
        self.stop_loss_atr = config.get("stop_loss_atr", 2.0)
        self.risk_per_trade = config.get("risk_per_trade", 0.7)
        self.trailing_atr = config.get("trailing_atr", 2.0)

    async def generate(self, pair: str) -> Optional[dict]:
        limit = self.ma_period + self.ma_slope_lookback + 5
        klines = await fetch_klines(pair, interval="1h", limit=limit)
        if len(klines) < limit:
            return None

        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]

        ma = calc_ma(closes, self.ma_period)
        slope = calc_ma_slope(closes, self.ma_period, self.ma_slope_lookback)
        atr = calc_atr(highs, lows, closes)

        if atr == 0:
            return None

        recent_closes = closes[-self.confirmation:]

        # BUY signal
        if all(c > ma for c in recent_closes) and slope > 0:
            return {
                "side": "buy",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": None,
                "trailing_atr": self.trailing_atr,
                "atr": atr,
                "ma": ma,
                "slope": slope,
            }

        # SELL signal
        if all(c < ma for c in recent_closes) and slope < 0:
            return {
                "side": "sell",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": None,
                "trailing_atr": self.trailing_atr,
                "atr": atr,
                "ma": ma,
                "slope": slope,
            }

        return None


# ---------------------------------------------------------------------------
# Strategy 2: RSITrendStrategy
# ---------------------------------------------------------------------------

class RSITrendStrategy:
    """RSI mean-reversion within a confirmed trend.

    BUY:  RSI < rsi_buy AND price > MA200 AND slope > 0
    SELL: RSI > rsi_sell AND price < MA200 AND slope < 0
    """

    TYPE = "rsi_trend"

    def __init__(self, config: dict):
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_buy = config.get("rsi_buy", 35)
        self.rsi_sell = config.get("rsi_sell", 65)
        self.ma_long = config.get("ma_long", 200)
        self.ma_slope_lookback = config.get("ma_slope_lookback", 10)
        self.atr_period = config.get("atr_period", 14)
        self.stop_loss_atr = config.get("stop_loss_atr", 1.2)
        self.take_profit_atr = config.get("take_profit_atr", 2.0)
        self.risk_per_trade = config.get("risk_per_trade", 1.0)

    async def generate(self, pair: str) -> Optional[dict]:
        limit = self.ma_long + self.ma_slope_lookback + 5
        klines = await fetch_klines(pair, interval="1h", limit=limit)
        if len(klines) < limit:
            return None

        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]

        rsi = calc_rsi(closes, self.rsi_period)
        ma = calc_ma(closes, self.ma_long)
        slope = calc_ma_slope(closes, self.ma_long, self.ma_slope_lookback)
        atr = calc_atr(highs, lows, closes, self.atr_period)
        price = closes[-1]

        if atr == 0:
            return None

        # BUY signal
        if rsi < self.rsi_buy and price > ma and slope > 0:
            return {
                "side": "buy",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": self.take_profit_atr,
                "trailing_atr": None,
                "atr": atr,
                "rsi": rsi,
                "ma": ma,
                "slope": slope,
            }

        # SELL signal
        if rsi > self.rsi_sell and price < ma and slope < 0:
            return {
                "side": "sell",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": self.take_profit_atr,
                "trailing_atr": None,
                "atr": atr,
                "rsi": rsi,
                "ma": ma,
                "slope": slope,
            }

        return None


# ---------------------------------------------------------------------------
# Strategy 3: BollingerADXStrategy
# ---------------------------------------------------------------------------

class BollingerADXStrategy:
    """Mean-reversion on Bollinger Bands in low-trend (range) markets.

    SKIP if ADX > adx_threshold (trending market).
    SKIP if bandwidth outside [bw_min, bw_max].
    BUY:  price <= lower band
    SELL: price >= upper band
    """

    TYPE = "boll_adx"

    def __init__(self, config: dict):
        self.bb_period = config.get("bb_period", 20)
        self.bb_std = config.get("bb_std", 2.0)
        self.adx_period = config.get("adx_period", 14)
        self.adx_threshold = config.get("adx_threshold", 25)
        self.bandwidth_min = config.get("bandwidth_min", 0.03)
        self.bandwidth_max = config.get("bandwidth_max", 0.15)
        self.stop_loss_atr = config.get("stop_loss_atr", 1.2)
        self.take_profit_atr = config.get("take_profit_atr", 1.5)
        self.risk_per_trade = config.get("risk_per_trade", 0.7)

    async def generate(self, pair: str) -> Optional[dict]:
        # Need enough data for ADX (2*period+1) and Bollinger
        limit = max(self.bb_period, 2 * self.adx_period + 1) + 20
        klines = await fetch_klines(pair, interval="1h", limit=limit)
        if len(klines) < limit:
            return None

        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]

        adx = calc_adx(highs, lows, closes, self.adx_period)
        if adx > self.adx_threshold:
            return None  # Skip trending market

        bw = calc_bandwidth(closes, self.bb_period, self.bb_std)
        if bw < self.bandwidth_min or bw > self.bandwidth_max:
            return None  # Skip outside bandwidth range

        lower, upper = calc_bollinger(closes, self.bb_period, self.bb_std)
        atr = calc_atr(highs, lows, closes)
        price = closes[-1]

        if atr == 0:
            return None

        # BUY signal
        if price <= lower:
            return {
                "side": "buy",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": self.take_profit_atr,
                "trailing_atr": None,
                "atr": atr,
                "adx": adx,
                "bandwidth": bw,
                "bb_lower": lower,
                "bb_upper": upper,
            }

        # SELL signal
        if price >= upper:
            return {
                "side": "sell",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": self.take_profit_atr,
                "trailing_atr": None,
                "atr": atr,
                "adx": adx,
                "bandwidth": bw,
                "bb_lower": lower,
                "bb_upper": upper,
            }

        return None


# ---------------------------------------------------------------------------
# Strategy 4: AdaptiveGridStrategy
# ---------------------------------------------------------------------------

class AdaptiveGridStrategy:
    """Grid trading with trend filter.

    Uses Redis key ``grid:{pair}:state`` to persist grid state.
    PAUSE if MA50 < MA200 AND ADX > 30 (confirmed downtrend).
    BUY at next grid level when price drops to it.
    SELL (close_all) when max_levels reached OR price hits recovery target.
    """

    TYPE = "adaptive_grid"

    def __init__(self, config: dict):
        self.grid_gap = config.get("grid_gap", 1.2)  # percent
        self.max_levels = config.get("max_levels", 5)
        self.max_exposure = config.get("max_exposure", 15)  # percent
        self.risk_total = config.get("risk_total", 2)  # percent
        self.trend_filter_fast = config.get("trend_filter_fast", 50)
        self.trend_filter_slow = config.get("trend_filter_slow", 200)
        self.trend_stop_adx = config.get("trend_stop_adx", 30)

    async def generate(self, pair: str) -> Optional[dict]:
        limit = self.trend_filter_slow + 10
        klines = await fetch_klines(pair, interval="1h", limit=limit)
        if len(klines) < limit:
            return None

        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]
        price = closes[-1]

        ma_fast = calc_ma(closes, self.trend_filter_fast)
        ma_slow = calc_ma(closes, self.trend_filter_slow)
        adx = calc_adx(highs, lows, closes)
        atr = calc_atr(highs, lows, closes)

        if atr == 0:
            return None

        # PAUSE in confirmed downtrend
        if ma_fast < ma_slow and adx > self.trend_stop_adx:
            return None

        # Load grid state from Redis
        redis = await get_redis()
        state_key = f"grid:{pair}:state"
        raw_state = await redis.get(state_key)

        if raw_state:
            state = json.loads(raw_state)
            base_price = state["base_price"]
            filled_levels = state["filled_levels"]
        else:
            # Initialize grid with current price as base
            base_price = price
            filled_levels = 0

        gap_mult = self.grid_gap / 100.0

        # SELL (close_all): max levels reached OR price recovers above base + gap
        if filled_levels > 0:
            recovery_target = base_price * (1 + gap_mult)
            if filled_levels >= self.max_levels or price >= recovery_target:
                # Reset grid state
                await redis.set(state_key, json.dumps({
                    "base_price": price,
                    "filled_levels": 0,
                }))
                return {
                    "side": "sell",
                    "risk_pct": self.risk_total,
                    "stop_loss_atr": None,
                    "take_profit_atr": None,
                    "trailing_atr": None,
                    "atr": atr,
                    "grid_level": filled_levels,
                    "action": "close_all",
                }

        # BUY at next grid level
        next_level_price = base_price * (1 - gap_mult * (filled_levels + 1))
        if price <= next_level_price:
            new_filled = filled_levels + 1
            await redis.set(state_key, json.dumps({
                "base_price": base_price,
                "filled_levels": new_filled,
            }))
            return {
                "side": "buy",
                "risk_pct": self.risk_total / self.max_levels,
                "stop_loss_atr": None,
                "take_profit_atr": None,
                "trailing_atr": None,
                "atr": atr,
                "grid_level": new_filled,
            }

        # Save initial state if first time
        if not raw_state:
            await redis.set(state_key, json.dumps({
                "base_price": base_price,
                "filled_levels": filled_levels,
            }))

        return None


# ---------------------------------------------------------------------------
# Strategy 5: BreakoutLiteStrategy
# ---------------------------------------------------------------------------

class BreakoutLiteStrategy:
    """Donchian channel breakout with volume and ADX confirmation.

    SKIP if ADX < adx_min (no trend).
    Uses Donchian of highs[:-1] / lows[:-1] (exclude current bar).
    BUY:  price > donchian_upper AND volume > avg_vol * vol_mult AND RSI < rsi_max
    SELL: price < donchian_lower AND volume > avg_vol * vol_mult AND RSI > (100 - rsi_max)
    """

    TYPE = "breakout_lite"

    def __init__(self, config: dict):
        self.donchian_period = config.get("donchian_period", 20)
        self.volume_multiplier = config.get("volume_multiplier", 1.5)
        self.adx_min = config.get("adx_min", 25)
        self.rsi_max = config.get("rsi_max", 70)
        self.stop_loss_atr = config.get("stop_loss_atr", 2.0)
        self.trailing_atr = config.get("trailing_atr", 1.5)
        self.risk_per_trade = config.get("risk_per_trade", 0.5)
        self.atr_period = config.get("atr_period", 14)

    async def generate(self, pair: str) -> Optional[dict]:
        limit = max(self.donchian_period, 2 * self.atr_period + 1) + 20
        klines = await fetch_klines(pair, interval="1h", limit=limit)
        if len(klines) < limit:
            return None

        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]
        volumes = [k["volume"] for k in klines]

        adx = calc_adx(highs, lows, closes, self.atr_period)
        if adx < self.adx_min:
            return None  # No trend

        # Donchian on all bars except current
        don_highs = highs[:-1]
        don_lows = lows[:-1]
        donchian_upper, donchian_lower = calc_donchian(
            don_highs, don_lows, self.donchian_period
        )

        atr = calc_atr(highs, lows, closes, self.atr_period)
        rsi = calc_rsi(closes)
        price = closes[-1]
        current_vol = volumes[-1]

        if atr == 0:
            return None

        # Average volume (exclude current bar)
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0
        if avg_vol == 0:
            return None

        vol_ok = current_vol > avg_vol * self.volume_multiplier

        # BUY breakout
        if price > donchian_upper and vol_ok and rsi < self.rsi_max:
            return {
                "side": "buy",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": None,
                "trailing_atr": self.trailing_atr,
                "atr": atr,
                "rsi": rsi,
                "donchian_upper": donchian_upper,
                "donchian_lower": donchian_lower,
                "volume_ratio": current_vol / avg_vol,
            }

        # SELL breakout
        if price < donchian_lower and vol_ok and rsi > (100 - self.rsi_max):
            return {
                "side": "sell",
                "risk_pct": self.risk_per_trade,
                "stop_loss_atr": self.stop_loss_atr,
                "take_profit_atr": None,
                "trailing_atr": self.trailing_atr,
                "atr": atr,
                "rsi": rsi,
                "donchian_upper": donchian_upper,
                "donchian_lower": donchian_lower,
                "volume_ratio": current_vol / avg_vol,
            }

        return None


# ---------------------------------------------------------------------------
# STRATEGIES registry
# ---------------------------------------------------------------------------

STRATEGIES = {
    "trend_ma200": TrendMA200Strategy,
    "rsi_trend": RSITrendStrategy,
    "boll_adx": BollingerADXStrategy,
    "adaptive_grid": AdaptiveGridStrategy,
    "breakout_lite": BreakoutLiteStrategy,
}
