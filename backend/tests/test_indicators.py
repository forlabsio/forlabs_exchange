import math
import pytest
from app.services.indicators import calc_rsi, calc_ma, calc_bollinger

def test_calc_rsi_oversold():
    # Steadily declining prices → RSI should be low
    prices = [float(100 - i) for i in range(16)]
    rsi = calc_rsi(prices, period=14)
    assert rsi < 30

def test_calc_rsi_overbought():
    # Steadily rising prices → RSI should be high
    prices = [float(100 + i) for i in range(16)]
    rsi = calc_rsi(prices, period=14)
    assert rsi > 70

def test_calc_rsi_neutral_returns_50_on_insufficient_data():
    prices = [100.0, 101.0]
    rsi = calc_rsi(prices, period=14)
    assert rsi == 50.0

def test_calc_ma():
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert calc_ma(prices, period=3) == pytest.approx(4.0)  # avg of last 3: 3,4,5

def test_calc_ma_insufficient_data_returns_last():
    prices = [42.0]
    assert calc_ma(prices, period=5) == 42.0

def test_calc_bollinger_buy_signal():
    # Price well below lower band → should be at or below lower band
    prices = [100.0] * 19 + [70.0]
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert prices[-1] <= lower

def test_calc_bollinger_sell_signal():
    # Price well above upper band → should be at or above upper band
    prices = [100.0] * 19 + [130.0]
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert prices[-1] >= upper

def test_calc_bollinger_normal_price_is_inside_bands():
    prices = [100.0] * 20
    lower, upper = calc_bollinger(prices, period=20, std_dev=2.0)
    assert lower <= 100.0 <= upper


# === New indicator tests ===

from app.services.indicators import calc_atr, calc_adx, calc_donchian, calc_ma_slope, calc_bandwidth


# ATR
def test_calc_atr_basic():
    highs =  [110, 112, 111, 113, 115, 114, 116, 118, 117, 119, 120, 121, 122, 123, 125]
    lows =   [100, 101, 100, 102, 104, 103, 105, 107, 106, 108, 109, 110, 111, 112, 114]
    closes = [105, 106, 105, 107, 109, 108, 110, 112, 111, 113, 114, 115, 116, 117, 119]
    atr = calc_atr(highs, lows, closes, period=14)
    assert atr > 0 and isinstance(atr, float)


def test_calc_atr_insufficient_data():
    assert calc_atr([110], [100], [105], period=14) == 0.0


# ADX
def test_calc_adx_trending():
    n = 30
    highs =  [100 + i * 2.0 + 1 for i in range(n)]
    lows =   [100 + i * 2.0 - 1 for i in range(n)]
    closes = [100 + i * 2.0 for i in range(n)]
    assert calc_adx(highs, lows, closes, period=14) > 25


def test_calc_adx_ranging():
    n = 30
    highs =  [101 if i % 2 == 0 else 100 for i in range(n)]
    lows =   [99 if i % 2 == 0 else 98 for i in range(n)]
    closes = [100 if i % 2 == 0 else 99 for i in range(n)]
    assert calc_adx(highs, lows, closes, period=14) < 25


def test_calc_adx_insufficient_data():
    assert calc_adx([110], [100], [105], period=14) == 0.0


# Donchian
def test_calc_donchian():
    upper, lower = calc_donchian([10, 12, 11, 15, 13], [8, 9, 7, 10, 11], period=5)
    assert upper == 15.0 and lower == 7.0


def test_calc_donchian_insufficient_data():
    upper, lower = calc_donchian([10], [8], period=5)
    assert upper == 10.0 and lower == 8.0


# MA Slope
def test_calc_ma_slope_rising():
    closes = [100 + i for i in range(210)]
    assert calc_ma_slope(closes, ma_period=200, lookback=10) > 0


def test_calc_ma_slope_falling():
    closes = [300 - i for i in range(210)]
    assert calc_ma_slope(closes, ma_period=200, lookback=10) < 0


def test_calc_ma_slope_insufficient_data():
    assert calc_ma_slope([100, 101], ma_period=200, lookback=10) == 0.0


# Bandwidth
def test_calc_bandwidth_normal():
    prices = [100.0] * 19 + [105.0]
    assert calc_bandwidth(prices, period=20, std_dev=2.0) > 0


def test_calc_bandwidth_flat():
    assert calc_bandwidth([100.0] * 20, period=20, std_dev=2.0) == 0.0


def test_calc_bandwidth_insufficient_data():
    assert calc_bandwidth([100.0], period=20, std_dev=2.0) == 0.0
