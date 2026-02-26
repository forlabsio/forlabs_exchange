import json
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.redis import get_redis
from app.models.order import Order, Trade, OrderStatus, OrderSide, OrderType
from app.models.wallet import Wallet

async def get_current_price(pair: str) -> float:
    redis = await get_redis()
    data = await redis.get(f"market:{pair}:ticker")
    if not data:
        return 0.0
    ticker = json.loads(data)
    return float(ticker.get("last_price", 0))

async def get_wallet(db: AsyncSession, user_id: int, asset: str, lock: bool = False) -> Optional[Wallet]:
    stmt = select(Wallet).where(Wallet.user_id == user_id, Wallet.asset == asset)
    if lock:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)

def _base_quote(pair: str):
    parts = pair.split("_")
    return parts[0], parts[1]

async def try_fill_order(db: AsyncSession, order: Order) -> dict:
    current_price = await get_current_price(order.pair)
    if current_price == 0:
        return {"filled": False, "fill_price": 0}

    base, quote = _base_quote(order.pair)
    should_fill = False
    fill_price = current_price

    if order.type == OrderType.market:
        should_fill = True
    elif order.type == OrderType.limit:
        if order.side == OrderSide.buy and current_price <= float(order.price):
            should_fill = True
            fill_price = float(order.price)
        elif order.side == OrderSide.sell and current_price >= float(order.price):
            should_fill = True
            fill_price = float(order.price)

    if not should_fill:
        return {"filled": False, "fill_price": fill_price}

    qty = Decimal(str(order.quantity))
    fill_price_dec = Decimal(str(fill_price))
    cost = qty * fill_price_dec

    if order.side == OrderSide.buy:
        quote_wallet = await get_wallet(db, order.user_id, quote, lock=True)
        base_wallet = await get_wallet(db, order.user_id, base, lock=True)
        if not quote_wallet or quote_wallet.balance < cost:
            return {"filled": False, "fill_price": fill_price}
        quote_wallet.balance -= cost
        if base_wallet:
            base_wallet.balance += qty
        else:
            db.add(Wallet(user_id=order.user_id, asset=base, balance=qty))
    else:
        base_wallet = await get_wallet(db, order.user_id, base, lock=True)
        quote_wallet = await get_wallet(db, order.user_id, quote, lock=True)
        if not base_wallet or base_wallet.balance < qty:
            return {"filled": False, "fill_price": fill_price}
        base_wallet.balance -= qty
        if quote_wallet:
            quote_wallet.balance += cost
        else:
            db.add(Wallet(user_id=order.user_id, asset=quote, balance=cost))

    order.filled_quantity = qty
    order.status = OrderStatus.filled
    db.add(Trade(order_id=order.id, price=fill_price_dec, quantity=qty))
    await db.commit()

    return {"filled": True, "fill_price": fill_price}


async def try_fill_order_live(db: AsyncSession, order: Order) -> dict:
    """Fill order via real Binance API."""
    from app.services.binance_trader import BinanceTrader, pair_to_binance_symbol

    trader = BinanceTrader()
    try:
        symbol = pair_to_binance_symbol(order.pair)
        side = "BUY" if order.side == OrderSide.buy else "SELL"

        # Validate and round quantity to Binance LOT_SIZE/MIN_NOTIONAL
        current_price = Decimal(str(await get_current_price(order.pair)))
        validated_qty = await trader.validate_quantity(symbol, order.quantity, current_price)
        order.quantity = validated_qty

        result = await trader.place_market_order(symbol, side, validated_qty)

        fills = result.get("fills", [])
        if not fills:
            return {"filled": False, "fill_price": 0}

        total_qty = sum(Decimal(f["qty"]) for f in fills)
        total_cost = sum(Decimal(f["price"]) * Decimal(f["qty"]) for f in fills)
        avg_price = total_cost / total_qty if total_qty > 0 else Decimal("0")

        base, quote = _base_quote(order.pair)

        if order.side == OrderSide.buy:
            quote_wallet = await get_wallet(db, order.user_id, quote, lock=True)
            base_wallet = await get_wallet(db, order.user_id, base, lock=True)
            if quote_wallet:
                quote_wallet.balance -= total_cost
            if base_wallet:
                base_wallet.balance += total_qty
            else:
                db.add(Wallet(user_id=order.user_id, asset=base, balance=total_qty))
        else:
            base_wallet = await get_wallet(db, order.user_id, base, lock=True)
            quote_wallet = await get_wallet(db, order.user_id, quote, lock=True)
            if base_wallet:
                base_wallet.balance -= total_qty
            if quote_wallet:
                quote_wallet.balance += total_cost
            else:
                db.add(Wallet(user_id=order.user_id, asset=quote, balance=total_cost))

        order.filled_quantity = total_qty
        order.status = OrderStatus.filled
        order.price = avg_price
        db.add(Trade(order_id=order.id, price=avg_price, quantity=total_qty))
        await db.commit()

        print(f"[LIVE] Order {order.id} filled: {side} {total_qty} {symbol} @ avg {avg_price}")
        return {"filled": True, "fill_price": float(avg_price)}
    except Exception as e:
        print(f"[LIVE] Order {order.id} failed: {e}")
        order.status = OrderStatus.cancelled
        await db.commit()
        return {"filled": False, "fill_price": 0, "error": str(e)}
    finally:
        await trader.close()
