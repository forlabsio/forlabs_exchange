import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from app.services.bot_runner import generate_signal, calc_quantity_from_risk


@pytest.mark.asyncio
async def test_generate_signal_uses_strategy_class():
    bot = MagicMock()
    bot.id = 1
    bot.strategy_type = "rsi_trend"
    bot.strategy_config = {"pair": "BTC_USDT", "signal_interval": 0}

    mock_signal = {"side": "buy", "risk_pct": 1.0, "stop_loss_atr": 1.2,
                   "take_profit_atr": 2.0, "trailing_atr": None, "atr": 500.0}
    mock_strategy = AsyncMock()
    mock_strategy.generate = AsyncMock(return_value=mock_signal)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    with patch("app.services.bot_runner.get_redis", return_value=mock_redis):
        with patch("app.services.bot_runner.STRATEGIES", {"rsi_trend": lambda cfg: mock_strategy}):
            signal = await generate_signal(bot, "BTC_USDT")
            assert signal is not None
            assert signal["side"] == "buy"


@pytest.mark.asyncio
async def test_generate_signal_respects_cooldown():
    bot = MagicMock()
    bot.id = 1
    bot.strategy_type = "rsi_trend"
    bot.strategy_config = {"signal_interval": 300}

    mock_redis = AsyncMock()
    import time
    mock_redis.get = AsyncMock(return_value=str(int(time.time())))  # just traded
    mock_redis.set = AsyncMock()

    with patch("app.services.bot_runner.get_redis", return_value=mock_redis):
        signal = await generate_signal(bot, "BTC_USDT")
        assert signal is None  # should be cooled down


@pytest.mark.asyncio
async def test_generate_signal_unknown_strategy():
    bot = MagicMock()
    bot.id = 1
    bot.strategy_type = "nonexistent"
    bot.strategy_config = {"signal_interval": 0}

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    with patch("app.services.bot_runner.get_redis", return_value=mock_redis):
        signal = await generate_signal(bot, "BTC_USDT")
        assert signal is None


def test_calc_quantity_from_risk_normal():
    qty = calc_quantity_from_risk(
        allocated_usdt=Decimal("10000"), price=Decimal("50000"),
        risk_pct=1.0, atr=500.0, stop_loss_atr=1.2,
    )
    assert qty > 0
    # risk=100, stop_dist=600, qty=100/600=0.16667
    assert float(qty) == pytest.approx(0.16667, abs=0.001)


def test_calc_quantity_from_risk_zero_atr():
    qty = calc_quantity_from_risk(
        allocated_usdt=Decimal("10000"), price=Decimal("50000"),
        risk_pct=1.0, atr=0, stop_loss_atr=1.2,
    )
    assert qty > 0  # fallback: 100/50000 = 0.002


def test_calc_quantity_from_risk_no_sl():
    qty = calc_quantity_from_risk(
        allocated_usdt=Decimal("10000"), price=Decimal("50000"),
        risk_pct=1.0, atr=500.0, stop_loss_atr=None,
    )
    assert qty > 0  # fallback
