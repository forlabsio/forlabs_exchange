import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from app.services.binance_trader import BinanceTrader, pair_to_binance_symbol


def test_pair_to_binance_symbol():
    assert pair_to_binance_symbol("BTC_USDT") == "BTCUSDT"
    assert pair_to_binance_symbol("ETH_USDT") == "ETHUSDT"
    assert pair_to_binance_symbol("SOL_USDT") == "SOLUSDT"


@pytest.mark.asyncio
async def test_place_market_buy():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "orderId": 123456,
        "status": "FILLED",
        "fills": [
            {"price": "50000.00", "qty": "0.001", "commission": "0.0000001", "commissionAsset": "BTC"}
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    trader = BinanceTrader.__new__(BinanceTrader)
    trader.api_key = "test_key"
    trader.api_secret = "test_secret"
    trader.base_url = "https://api.binance.com"
    trader.client = mock_client

    result = await trader.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))
    assert result["orderId"] == 123456
    assert result["status"] == "FILLED"
    assert len(result["fills"]) == 1


@pytest.mark.asyncio
async def test_place_market_order_error():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"code":-1013,"msg":"Filter failure: LOT_SIZE"}'

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    trader = BinanceTrader.__new__(BinanceTrader)
    trader.api_key = "test_key"
    trader.api_secret = "test_secret"
    trader.base_url = "https://api.binance.com"
    trader.client = mock_client

    with pytest.raises(Exception, match="Binance order failed"):
        await trader.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))
