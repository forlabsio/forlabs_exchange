import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.position_manager import PositionManager


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.delete = AsyncMock()
    return r


@pytest.mark.asyncio
async def test_open_position(mock_redis):
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        await pm.open_position(side="buy", entry_price=50000.0, atr=500.0, stop_loss_atr=1.2, take_profit_atr=2.0)
        mock_redis.set.assert_called_once()
        key = mock_redis.set.call_args[0][0]
        assert key == "pos:1:10"


@pytest.mark.asyncio
async def test_check_stop_loss_buy(mock_redis):
    pos = json.dumps({"side": "buy", "entry": 50000.0, "stop_loss": 49400.0,
                       "take_profit": 51000.0, "trailing_stop": None, "trailing_active": False})
    mock_redis.get = AsyncMock(return_value=pos)
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        assert await pm.check_exit(current_price=49300.0) == "stop_loss"


@pytest.mark.asyncio
async def test_check_take_profit_buy(mock_redis):
    pos = json.dumps({"side": "buy", "entry": 50000.0, "stop_loss": 49400.0,
                       "take_profit": 51000.0, "trailing_stop": None, "trailing_active": False})
    mock_redis.get = AsyncMock(return_value=pos)
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        assert await pm.check_exit(current_price=51100.0) == "take_profit"


@pytest.mark.asyncio
async def test_no_exit_in_range(mock_redis):
    pos = json.dumps({"side": "buy", "entry": 50000.0, "stop_loss": 49400.0,
                       "take_profit": 51000.0, "trailing_stop": None, "trailing_active": False})
    mock_redis.get = AsyncMock(return_value=pos)
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        assert await pm.check_exit(current_price=50500.0) is None


@pytest.mark.asyncio
async def test_trailing_stop_updates(mock_redis):
    pos = json.dumps({"side": "buy", "entry": 50000.0, "stop_loss": 49400.0,
                       "take_profit": None, "trailing_stop": 49500.0, "trailing_active": True,
                       "trailing_atr_mult": 1.5, "current_atr": 500.0})
    mock_redis.get = AsyncMock(return_value=pos)
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        result = await pm.check_exit(current_price=51500.0)
        assert result is None
        saved_data = json.loads(mock_redis.set.call_args[0][1])
        assert saved_data["trailing_stop"] == pytest.approx(50750.0)  # 51500 - 1.5*500


@pytest.mark.asyncio
async def test_sell_position_stop_loss(mock_redis):
    pos = json.dumps({"side": "sell", "entry": 50000.0, "stop_loss": 50600.0,
                       "take_profit": 49000.0, "trailing_stop": None, "trailing_active": False})
    mock_redis.get = AsyncMock(return_value=pos)
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        assert await pm.check_exit(current_price=50700.0) == "stop_loss"


@pytest.mark.asyncio
async def test_no_position_returns_none(mock_redis):
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        assert await pm.check_exit(current_price=50000.0) is None


@pytest.mark.asyncio
async def test_close_position(mock_redis):
    with patch("app.services.position_manager.get_redis", return_value=mock_redis):
        pm = PositionManager(bot_id=1, user_id=10)
        await pm.close_position()
        mock_redis.delete.assert_called_once_with("pos:1:10")
