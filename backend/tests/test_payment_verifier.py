import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.payment_verifier import verify_polygon_usdt_payment, USDT_CONTRACT_ADDRESS


@pytest.mark.asyncio
async def test_verify_valid_payment():
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    to_addr_padded = "0x" + "0" * 24 + "abcdef1234567890abcdef1234567890abcdef12"
    from_addr_padded = "0x" + "0" * 24 + "1234567890abcdef1234567890abcdef12345678"

    mock_receipt = {
        "result": {
            "status": "0x1",
            "logs": [
                {
                    "address": USDT_CONTRACT_ADDRESS.lower(),
                    "topics": [transfer_topic, from_addr_padded, to_addr_padded],
                    "data": "0x0000000000000000000000000000000000000000000000000000000002faf080",
                }
            ],
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_receipt

    with patch("app.services.payment_verifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        result = await verify_polygon_usdt_payment(
            tx_hash="0x1234567890abcdef",
            expected_to="0xabcdef1234567890abcdef1234567890abcdef12",
            expected_amount=50.0,
        )
        assert result["verified"] is True
        assert result["amount"] >= 50.0


@pytest.mark.asyncio
async def test_verify_wrong_recipient():
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    wrong_addr_padded = "0x" + "0" * 24 + "9999999999999999999999999999999999999999"
    from_addr_padded = "0x" + "0" * 24 + "1234567890abcdef1234567890abcdef12345678"

    mock_receipt = {
        "result": {
            "status": "0x1",
            "logs": [
                {
                    "address": USDT_CONTRACT_ADDRESS.lower(),
                    "topics": [transfer_topic, from_addr_padded, wrong_addr_padded],
                    "data": "0x0000000000000000000000000000000000000000000000000000000002faf080",
                }
            ],
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_receipt

    with patch("app.services.payment_verifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        result = await verify_polygon_usdt_payment(
            tx_hash="0xabc",
            expected_to="0xabcdef1234567890abcdef1234567890abcdef12",
            expected_amount=50.0,
        )
        assert result["verified"] is False
