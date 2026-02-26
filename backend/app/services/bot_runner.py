import asyncio
import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.bot import Bot, BotSubscription, BotStatus
from app.models.order import Order, OrderSide, OrderType
from app.core.redis import get_redis
from app.services.matching_engine import try_fill_order, try_fill_order_live
from app.config import settings, is_live_trading
from app.services.strategies import STRATEGIES
from app.services.position_manager import PositionManager


# ---------------------------------------------------------------------------
# ATR-based position sizing
# ---------------------------------------------------------------------------

def calc_quantity_from_risk(
    allocated_usdt: Decimal,
    price: Decimal,
    risk_pct: float,
    atr: float,
    stop_loss_atr: Optional[float],
) -> Decimal:
    """Calculate base-asset quantity from risk budget and ATR-based stop distance.

    risk_amount = allocated * risk_pct / 100
    stop_distance = atr * stop_loss_atr
    quantity = risk_amount / stop_distance

    Falls back to risk_amount / price when ATR or stop_loss_atr is zero/None.
    """
    risk_amount = allocated_usdt * Decimal(str(risk_pct)) / Decimal("100")

    if atr and stop_loss_atr:
        stop_distance = Decimal(str(float(atr) * float(stop_loss_atr)))
        if stop_distance > 0:
            return (risk_amount / stop_distance).quantize(Decimal("0.00001"))

    # Fallback: simple fraction of allocation at current price
    if price > 0:
        return (risk_amount / price).quantize(Decimal("0.00001"))
    return Decimal("0")


# ---------------------------------------------------------------------------
# Signal generation (delegates to strategy classes)
# ---------------------------------------------------------------------------

async def generate_signal(bot: Bot, pair: str) -> Optional[dict]:
    """Generate a trading signal using the bot's configured strategy class.

    Returns a signal dict (with side, risk_pct, atr, etc.) or None.
    Enforces cooldown via Redis with direction-aware intervals.
    """
    redis = await get_redis()
    config = bot.strategy_config or {}
    signal_interval = config.get("signal_interval", 300)

    # --- Cooldown check ---
    last_trade_key = f"bot:{bot.id}:last_trade_time"
    last_side_key = f"bot:{bot.id}:last_side"
    last_trade = await redis.get(last_trade_key)
    now = int(time.time())

    if last_trade and signal_interval > 0:
        elapsed = now - int(last_trade)
        if elapsed < signal_interval:
            return None

    # --- Strategy lookup ---
    strategy_type = bot.strategy_type or "rsi_trend"
    strategy_cls = STRATEGIES.get(strategy_type)
    if strategy_cls is None:
        print(f"Unknown strategy type '{strategy_type}' for bot {bot.id}")
        return None

    strategy = strategy_cls(config)

    try:
        signal = await strategy.generate(pair)
    except Exception as e:
        print(f"Strategy '{strategy_type}' error for bot {bot.id}: {e}")
        return None

    if not signal:
        return None

    # --- Direction-based cooldown ---
    last_side = await redis.get(last_side_key)
    new_side = signal["side"]

    if last_trade and last_side:
        cooldown_same = config.get("cooldown_same", signal_interval)
        cooldown_opposite = config.get("cooldown_opposite", signal_interval // 3 if signal_interval else 0)
        elapsed = now - int(last_trade)

        if new_side == last_side and elapsed < cooldown_same:
            return None
        if new_side != last_side and elapsed < cooldown_opposite:
            return None

    # --- Record trade time and side ---
    await redis.set(last_trade_key, str(now))
    await redis.set(last_side_key, new_side)

    return signal


# ---------------------------------------------------------------------------
# Bot execution (per-subscription logic)
# ---------------------------------------------------------------------------

async def run_bot(bot: Bot):
    """Execute one cycle of the bot for all active subscriptions."""
    config = bot.strategy_config or {}
    pair = config.get("pair", "BTC_USDT")

    async with AsyncSessionLocal() as db:
        subs = await db.scalars(
            select(BotSubscription).where(
                BotSubscription.bot_id == bot.id,
                BotSubscription.is_active == True,
            )
        )
        sub_list = list(subs)

        for sub in sub_list:
            # 1. Check expiry -> deactivate if expired (close positions first)
            if sub.expires_at and sub.expires_at.replace(tzinfo=None) < datetime.utcnow():
                # Close any open Binance position before deactivating
                pm = PositionManager(bot.id, sub.user_id)
                if await pm.has_position():
                    pos = await pm.get_position()
                    if pos:
                        redis = await get_redis()
                        ticker = await redis.get(f"market:{pair}:ticker")
                        if ticker:
                            from app.models.wallet import Wallet
                            from sqlalchemy import select as sel
                            base, quote = pair.split("_")
                            base_wallet = await db.scalar(
                                sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == base)
                            )
                            if base_wallet and base_wallet.balance > 0:
                                exit_qty = base_wallet.balance.quantize(Decimal("0.00001"))
                                if exit_qty > 0:
                                    exit_side = "sell" if pos["side"] == "buy" else "buy"
                                    order = Order(
                                        user_id=sub.user_id, pair=pair,
                                        side=OrderSide(exit_side), type=OrderType.market,
                                        quantity=exit_qty, is_bot_order=True, bot_id=bot.id,
                                    )
                                    db.add(order)
                                    await db.flush()
                                    if await is_live_trading():
                                        await try_fill_order_live(db, order)
                                    else:
                                        await try_fill_order(db, order)
                                    print(f"Bot {bot.id} user {sub.user_id}: expiry close {exit_side} {exit_qty}")
                    await pm.close_position()
                sub.is_active = False
                await db.commit()
                continue

            # 2. Get current price from Redis
            redis = await get_redis()
            ticker = await redis.get(f"market:{pair}:ticker")
            if not ticker:
                continue
            price = Decimal(json.loads(ticker)["last_price"])
            price_float = float(price)

            # 3. Create PositionManager
            pm = PositionManager(bot.id, sub.user_id)

            # 4. Check exit first: SL/TP/trailing
            exit_reason = await pm.check_exit(price_float)
            if exit_reason:
                # Close position via sell order
                pos = await pm.get_position()
                if pos:
                    from app.models.wallet import Wallet
                    from sqlalchemy import select as sel

                    base, quote = pair.split("_")
                    base_wallet = await db.scalar(
                        sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == base)
                    )
                    if base_wallet and base_wallet.balance > 0:
                        exit_qty = base_wallet.balance.quantize(Decimal("0.00001"))
                        if exit_qty > 0:
                            exit_side = "sell" if pos["side"] == "buy" else "buy"
                            order = Order(
                                user_id=sub.user_id,
                                pair=pair,
                                side=OrderSide(exit_side),
                                type=OrderType.market,
                                quantity=exit_qty,
                                is_bot_order=True,
                                bot_id=bot.id,
                            )
                            db.add(order)
                            await db.flush()
                            if await is_live_trading():
                                await try_fill_order_live(db, order)
                            else:
                                await try_fill_order(db, order)
                            print(f"Bot {bot.id} user {sub.user_id}: exit ({exit_reason}) {exit_side} {exit_qty} @ {price}")

                await pm.close_position()
                continue

            # 5. Skip if already in position (except adaptive_grid)
            strategy_type = bot.strategy_type or "rsi_trend"
            has_pos = await pm.has_position()
            if has_pos and strategy_type != "adaptive_grid":
                continue

            # 6. Generate signal
            signal = await generate_signal(bot, pair)
            if not signal:
                continue

            side = signal["side"]
            risk_pct = signal.get("risk_pct", 1.0)
            atr = signal.get("atr", 0)
            stop_loss_atr = signal.get("stop_loss_atr")
            take_profit_atr = signal.get("take_profit_atr")
            trailing_atr = signal.get("trailing_atr")

            from app.models.wallet import Wallet
            from sqlalchemy import select as sel

            base, quote = pair.split("_")
            allocated = Decimal(str(sub.allocated_usdt or 100))

            # 7. Calculate quantity using ATR-based sizing
            if strategy_type == "adaptive_grid":
                # Grid: simple percentage of allocation
                grid_pct = signal.get("risk_pct", 0.4)
                spend = allocated * Decimal(str(grid_pct)) / Decimal("100")
                quantity = (spend / price).quantize(Decimal("0.00001")) if price > 0 else Decimal("0")
            else:
                quantity = calc_quantity_from_risk(
                    allocated_usdt=allocated,
                    price=price,
                    risk_pct=risk_pct,
                    atr=atr,
                    stop_loss_atr=stop_loss_atr,
                )

            if quantity <= 0:
                continue

            # 8. Cap quantity by wallet balance
            if side == "buy":
                wallet = await db.scalar(
                    sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == quote)
                )
                if not wallet or wallet.balance <= 0:
                    continue
                max_spend = wallet.balance
                max_qty = (max_spend / price).quantize(Decimal("0.00001")) if price > 0 else Decimal("0")
                quantity = min(quantity, max_qty)
            else:
                wallet = await db.scalar(
                    sel(Wallet).where(Wallet.user_id == sub.user_id, Wallet.asset == base)
                )
                if not wallet or wallet.balance <= 0:
                    continue
                quantity = min(quantity, wallet.balance.quantize(Decimal("0.00001")))

            if quantity <= 0:
                continue

            # 9. Create and fill order
            order = Order(
                user_id=sub.user_id,
                pair=pair,
                side=OrderSide(side),
                type=OrderType.market,
                quantity=quantity,
                is_bot_order=True,
                bot_id=bot.id,
            )
            db.add(order)
            await db.flush()

            if await is_live_trading():
                result = await try_fill_order_live(db, order)
            else:
                result = await try_fill_order(db, order)

            # 10. Open position tracking (for strategies with SL/TP)
            if result.get("filled") and stop_loss_atr:
                fill_price = float(result.get("fill_price", price_float))
                await pm.open_position(
                    side=side,
                    entry_price=fill_price,
                    atr=float(atr),
                    stop_loss_atr=float(stop_loss_atr),
                    take_profit_atr=float(take_profit_atr) if take_profit_atr else None,
                    trailing_atr=float(trailing_atr) if trailing_atr else None,
                )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def bot_runner_loop():
    """Run all active bots every 10 seconds."""
    while True:
        async with AsyncSessionLocal() as db:
            bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
            bot_list = list(bots)

        kill_redis = await get_redis()
        for bot in bot_list:
            kill_flag = await kill_redis.get(f"bot:{bot.id}:kill_switch")
            if kill_flag:
                continue
            try:
                await run_bot(bot)
            except Exception as e:
                print(f"Bot runner error for bot {bot.id}: {e}")

        await asyncio.sleep(10)
