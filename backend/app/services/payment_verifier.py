import httpx
from app.config import settings

USDT_CONTRACT_ADDRESS = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
USDT_DECIMALS = 6
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


async def verify_polygon_usdt_payment(
    tx_hash: str,
    expected_to: str,
    expected_amount: float,
) -> dict:
    client = httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.post(
            settings.POLYGON_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
                "id": 1,
            },
        )
        if resp.status_code != 200:
            return {"verified": False, "error": "RPC request failed"}

        data = resp.json()
        receipt = data.get("result")
        if not receipt:
            return {"verified": False, "error": "Transaction not found"}

        if receipt.get("status") != "0x1":
            return {"verified": False, "error": "Transaction failed"}

        for log in receipt.get("logs", []):
            if log["address"].lower() != USDT_CONTRACT_ADDRESS.lower():
                continue
            topics = log.get("topics", [])
            if len(topics) < 3 or topics[0] != TRANSFER_EVENT_TOPIC:
                continue

            to_addr = "0x" + topics[2][-40:]
            if to_addr.lower() != expected_to.lower():
                continue

            raw_amount = int(log["data"], 16)
            amount = raw_amount / (10 ** USDT_DECIMALS)

            if amount >= expected_amount:
                from_addr = "0x" + topics[1][-40:]
                return {
                    "verified": True,
                    "amount": amount,
                    "from_address": from_addr,
                    "to_address": to_addr,
                }

        return {"verified": False, "error": "No matching USDT transfer found"}
    finally:
        await client.aclose()
