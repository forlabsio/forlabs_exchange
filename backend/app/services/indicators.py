import math
from typing import List, Tuple


def calc_rsi(closes: List[float], period: int = 14) -> float:
    """Compute RSI (Cutler's simple-average variant) from closing prices.
    Uses simple mean of gains/losses over the last `period` deltas, not
    Wilder's exponential smoothing. Returns 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [max(d, 0.0) for d in recent]
    losses = [abs(min(d, 0.0)) for d in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_ma(closes: List[float], period: int) -> float:
    """Simple moving average of the last `period` prices."""
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    return sum(closes[-period:]) / period


def calc_bollinger(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> Tuple[float, float]:
    """Return (lower_band, upper_band). Falls back to +-5% if insufficient data."""
    if len(closes) < period:
        last = closes[-1] if closes else 100.0
        return (last * 0.95, last * 1.05)
    window = closes[-period:]
    ma = sum(window) / period
    variance = sum((p - ma) ** 2 for p in window) / period  # population std dev (Bollinger standard)
    std = math.sqrt(variance)
    return (ma - std_dev * std, ma + std_dev * std)


# ── New indicators ──────────────────────────────────────────────────────────


def calc_atr(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> float:
    """Average True Range.

    TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
    ATR = SMA of last `period` TRs.
    Returns 0.0 if insufficient data (need >= period + 1 bars).
    """
    n = len(closes)
    if n < period + 1:
        return 0.0

    trs: List[float] = []
    for i in range(1, n):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])
        trs.append(max(high_low, high_prev_close, low_prev_close))

    recent_trs = trs[-period:]
    return float(sum(recent_trs) / period)


def calc_adx(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> float:
    """Average Directional Index with Wilder smoothing.

    +DM, -DM, TR -> Wilder smooth -> +DI, -DI -> DX -> Wilder smooth -> ADX.
    Returns 0.0 if insufficient data (need >= 2 * period + 1 bars).
    """
    n = len(closes)
    if n < 2 * period + 1:
        return 0.0

    # Step 1: Compute raw +DM, -DM, TR series (length n-1)
    plus_dm_list: List[float] = []
    minus_dm_list: List[float] = []
    tr_list: List[float] = []

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])
        tr = max(high_low, high_prev_close, low_prev_close)

        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)

    # Step 2: Wilder smoothing for first `period` values (seed with SMA)
    smoothed_plus_dm = sum(plus_dm_list[:period])
    smoothed_minus_dm = sum(minus_dm_list[:period])
    smoothed_tr = sum(tr_list[:period])

    dx_list: List[float] = []

    # First DX value
    if smoothed_tr != 0:
        plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
        minus_di = 100.0 * smoothed_minus_dm / smoothed_tr
    else:
        plus_di = 0.0
        minus_di = 0.0
    di_sum = plus_di + minus_di
    dx_list.append(abs(plus_di - minus_di) / di_sum * 100.0 if di_sum != 0 else 0.0)

    # Step 3: Continue Wilder smoothing and accumulate DX values
    for i in range(period, len(plus_dm_list)):
        smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm_list[i]
        smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm_list[i]
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_list[i]

        if smoothed_tr != 0:
            plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
            minus_di = 100.0 * smoothed_minus_dm / smoothed_tr
        else:
            plus_di = 0.0
            minus_di = 0.0
        di_sum = plus_di + minus_di
        dx = abs(plus_di - minus_di) / di_sum * 100.0 if di_sum != 0 else 0.0
        dx_list.append(dx)

    # Step 4: Wilder smooth the DX series to get ADX
    if len(dx_list) < period:
        return 0.0

    adx = sum(dx_list[:period]) / period  # seed ADX with SMA of first `period` DX values
    for i in range(period, len(dx_list)):
        adx = (adx * (period - 1) + dx_list[i]) / period

    return float(adx)


def calc_donchian(
    highs: List[float], lows: List[float], period: int = 20
) -> Tuple[float, float]:
    """Donchian Channel: (upper, lower).

    upper = max of highs over last `period` bars.
    lower = min of lows over last `period` bars.
    Falls back to (highs[-1], lows[-1]) if insufficient data.
    """
    if not highs or not lows:
        return (0.0, 0.0)
    if len(highs) < period or len(lows) < period:
        return (float(highs[-1]), float(lows[-1]))
    upper = float(max(highs[-period:]))
    lower = float(min(lows[-period:]))
    return (upper, lower)


def calc_ma_slope(
    closes: List[float], ma_period: int = 200, lookback: int = 10
) -> float:
    """Slope of the MA: current_ma - past_ma.

    current_ma = SMA of all closes over ma_period.
    past_ma    = SMA of closes[:-lookback] over ma_period.
    Returns 0.0 if len(closes) < ma_period + lookback.
    """
    if len(closes) < ma_period + lookback:
        return 0.0
    current_ma = sum(closes[-ma_period:]) / ma_period
    past_closes = closes[:-lookback]
    past_ma = sum(past_closes[-ma_period:]) / ma_period
    return float(current_ma - past_ma)


def calc_bandwidth(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> float:
    """Bollinger Bandwidth: (upper - lower) / middle.

    Returns 0.0 if insufficient data or flat prices (zero bandwidth).
    """
    if len(closes) < period:
        return 0.0
    lower, upper = calc_bollinger(closes, period, std_dev)
    middle = sum(closes[-period:]) / period
    if middle == 0:
        return 0.0
    return float((upper - lower) / middle)
