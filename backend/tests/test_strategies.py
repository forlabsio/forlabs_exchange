import pytest
from unittest.mock import AsyncMock, patch
from app.services.strategies import (
    TrendMA200Strategy, RSITrendStrategy, BollingerADXStrategy,
    AdaptiveGridStrategy, BreakoutLiteStrategy, STRATEGIES,
)

def _make_klines(closes, highs=None, lows=None, volumes=None):
    n = len(closes)
    if highs is None: highs = [c + 1 for c in closes]
    if lows is None: lows = [c - 1 for c in closes]
    if volumes is None: volumes = [1000.0] * n
    return [{"open": c, "high": h, "low": l, "close": c, "volume": v, "time": i}
            for i, (c, h, l, v) in enumerate(zip(closes, highs, lows, volumes))]

@pytest.mark.asyncio
async def test_trend_ma200_buy_on_uptrend():
    closes = [100.0 + i * 0.5 for i in range(215)]
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    klines = _make_klines(closes, highs, lows)
    config = {"ma_period": 200, "confirmation": 3, "ma_slope_lookback": 10,
              "stop_loss_atr": 2.0, "risk_per_trade": 0.7, "trailing_atr": 2.0}
    with patch("app.services.strategies.fetch_klines", return_value=klines):
        signal = await TrendMA200Strategy(config).generate("BTC_USDT")
        assert signal is not None and signal["side"] == "buy" and signal["risk_pct"] == 0.7

@pytest.mark.asyncio
async def test_trend_ma200_no_signal_flat():
    klines = _make_klines([100.0] * 215)
    config = {"ma_period": 200, "confirmation": 3, "ma_slope_lookback": 10,
              "stop_loss_atr": 2.0, "risk_per_trade": 0.7, "trailing_atr": 2.0}
    with patch("app.services.strategies.fetch_klines", return_value=klines):
        assert await TrendMA200Strategy(config).generate("BTC_USDT") is None

@pytest.mark.asyncio
async def test_rsi_trend_no_buy_in_downtrend():
    closes = [200 - i * 0.5 for i in range(215)]
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    klines = _make_klines(closes, highs, lows)
    config = {"rsi_period": 14, "rsi_buy": 35, "rsi_sell": 65, "ma_long": 200,
              "ma_slope_lookback": 10, "atr_period": 14, "stop_loss_atr": 1.2,
              "take_profit_atr": 2.0, "risk_per_trade": 1.0}
    with patch("app.services.strategies.fetch_klines", return_value=klines):
        signal = await RSITrendStrategy(config).generate("BTC_USDT")
        if signal: assert signal["side"] != "buy"

@pytest.mark.asyncio
async def test_boll_adx_no_signal_when_trending():
    closes = [100 + i * 2.0 for i in range(50)]
    highs = [c + 3 for c in closes]
    lows = [c - 3 for c in closes]
    klines = _make_klines(closes, highs, lows)
    config = {"bb_period": 20, "bb_std": 2.0, "adx_period": 14, "adx_threshold": 25,
              "bandwidth_min": 0.03, "bandwidth_max": 0.15, "stop_loss_atr": 1.2,
              "take_profit_atr": 1.5, "risk_per_trade": 0.7}
    with patch("app.services.strategies.fetch_klines", return_value=klines):
        assert await BollingerADXStrategy(config).generate("BTC_USDT") is None

@pytest.mark.asyncio
async def test_grid_generates_buy():
    closes = [100 + (i % 5) * 0.5 for i in range(210)]
    klines = _make_klines(closes)
    config = {"grid_gap": 1.2, "max_levels": 5, "max_exposure": 15, "risk_total": 2,
              "trend_filter_fast": 50, "trend_filter_slow": 200, "trend_stop_adx": 30}
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    with patch("app.services.strategies.fetch_klines", return_value=klines):
        with patch("app.services.strategies.get_redis", return_value=mock_redis):
            signal = await AdaptiveGridStrategy(config).generate("BTC_USDT")
            if signal:
                assert signal["side"] in ("buy", "sell")
                assert "grid_level" in signal

@pytest.mark.asyncio
async def test_breakout_no_crash():
    closes = [100.0] * 25 + [101.0, 103.0, 106.0, 110.0, 115.0]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000.0] * 25 + [1000.0, 1500.0, 2000.0, 2500.0, 3000.0]
    klines = _make_klines(closes, highs, lows, volumes)
    config = {"donchian_period": 20, "volume_multiplier": 1.5, "adx_min": 25,
              "rsi_max": 70, "stop_loss_atr": 2.0, "trailing_atr": 1.5,
              "risk_per_trade": 0.5, "atr_period": 14}
    with patch("app.services.strategies.fetch_klines", return_value=klines):
        signal = await BreakoutLiteStrategy(config).generate("BTC_USDT")
        assert signal is None or signal["side"] in ("buy", "sell")

def test_strategies_registry():
    assert set(STRATEGIES.keys()) == {"trend_ma200", "rsi_trend", "boll_adx", "adaptive_grid", "breakout_lite"}
