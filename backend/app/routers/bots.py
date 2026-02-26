from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.core.deps import get_current_user, get_optional_user
from app.models.user import User
from app.models.wallet import Wallet
from app.models.bot import Bot, BotSubscription, BotStatus, BotPerformance
from app.models.order import Order, Trade
from app.services.stats import calc_bot_stats


class SubscribeRequest(BaseModel):
    allocated_usdt: float = Field(default=100.0, gt=0)
    tx_hash: str


router = APIRouter(prefix="/api/bots", tags=["bots"])


def _perf_dict(perf) -> dict:
    if not perf:
        return {
            "win_rate": 0.0, "monthly_return_pct": 0.0,
            "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0,
            "calculated_at": None,
        }
    return {
        "win_rate": float(perf.win_rate) if perf.win_rate is not None else 0.0,
        "monthly_return_pct": float(perf.monthly_return_pct) if perf.monthly_return_pct is not None else 0.0,
        "max_drawdown_pct": float(perf.max_drawdown_pct) if perf.max_drawdown_pct is not None else 0.0,
        "sharpe_ratio": float(perf.sharpe_ratio) if perf.sharpe_ratio is not None else 0.0,
        "calculated_at": perf.calculated_at.isoformat() if perf.calculated_at else None,
    }


async def _bot_dict(db: AsyncSession, bot: Bot, user: Optional[User] = None) -> dict:
    # Bot market shows the most recently aggregated performance (set by daily_performance_update)
    perf = await db.scalar(
        select(BotPerformance)
        .where(BotPerformance.bot_id == bot.id)
        .order_by(desc(BotPerformance.calculated_at))
        .limit(1)
    )
    sub_count = await db.scalar(
        select(func.count(BotSubscription.id)).where(
            BotSubscription.bot_id == bot.id,
            BotSubscription.is_active == True,
        )
    )
    is_subscribed = False
    if user:
        existing = await db.scalar(
            select(BotSubscription).where(
                BotSubscription.user_id == user.id,
                BotSubscription.bot_id == bot.id,
                BotSubscription.is_active == True,
            )
        )
        is_subscribed = existing is not None

    operation_days = 0
    if bot.created_at:
        delta = datetime.utcnow() - bot.created_at.replace(tzinfo=None)
        operation_days = delta.days

    return {
        "id": bot.id,
        "name": bot.name,
        "description": bot.description,
        "strategy_type": bot.strategy_type or "alternating",
        "status": bot.status,
        "monthly_fee": float(bot.monthly_fee) if bot.monthly_fee is not None else 0.0,
        "subscriber_count": sub_count or 0,
        "operation_days": operation_days,
        "performance": _perf_dict(perf),
        "is_subscribed": is_subscribed,
    }


@router.get("")
async def list_bots(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
    return [await _bot_dict(db, b, user) for b in bots]


@router.get("/my")
async def my_bots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subs = await db.scalars(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.is_active == True,
        )
    )
    result = []
    for sub in subs:
        bot = await db.get(Bot, sub.bot_id)
        if not bot:
            continue
        d = await _bot_dict(db, bot, user)
        d["subscribed_at"] = sub.started_at.isoformat() if sub.started_at else None
        d["allocated_usdt"] = float(sub.allocated_usdt) if sub.allocated_usdt is not None else 100.0
        config = bot.strategy_config or {}
        pair = config.get("pair", "BTC_USDT")
        allocated = Decimal(str(sub.allocated_usdt or 100))
        live = await calc_bot_stats(db, user.id, bot.id, allocated, pair)
        d["pnl_usdt"] = live["pnl_usdt"]
        d["performance"]["monthly_return_pct"] = live["pnl_pct"]
        if live["trade_count"] > 0:
            d["performance"]["win_rate"] = live["win_rate"]
            d["performance"]["max_drawdown_pct"] = live["max_drawdown_pct"]
            if live["sharpe_ratio"] != 0.0:
                d["performance"]["sharpe_ratio"] = live["sharpe_ratio"]
        result.append(d)
    return result


@router.get("/{bot_id}/position")
async def bot_position(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    config = bot.strategy_config or {}
    pair = config.get("pair", "BTC_USDT")
    base = pair.split("_")[0]

    orders = await db.scalars(
        select(Order).where(
            Order.user_id == user.id,
            Order.bot_id == bot_id,
            Order.status == "filled",
        )
    )
    net_qty = Decimal("0")
    for o in orders:
        qty = Decimal(str(o.filled_quantity or 0))
        if o.side == "buy":
            net_qty += qty
        else:
            net_qty -= qty
    net_qty = max(net_qty, Decimal("0"))

    redis = await get_redis()
    price_usdt = 0.0
    ticker = await redis.get(f"market:{pair}:ticker")
    if ticker:
        price_usdt = float(json.loads(ticker)["last_price"])

    return {
        "pair": pair,
        "base": base,
        "net_qty": float(net_qty),
        "price_usdt": price_usdt,
        "value_usdt": float(net_qty) * price_usdt,
    }


@router.get("/{bot_id}/trades")
async def bot_trades(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orders = list(await db.scalars(
        select(Order).where(
            Order.bot_id == bot_id,
            Order.user_id == user.id,
        ).order_by(Order.created_at.desc()).limit(50)
    ))
    result = []
    for o in orders:
        trade = await db.scalar(select(Trade).where(Trade.order_id == o.id))
        fill_price = float(trade.price) if trade else (float(o.price) if o.price else None)
        result.append({
            "id": o.id,
            "pair": o.pair,
            "side": o.side,
            "type": o.type,
            "quantity": float(o.quantity),
            "price": fill_price,
            "filled_quantity": float(o.filled_quantity) if o.filled_quantity else 0.0,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return result


@router.post("/{bot_id}/subscribe")
async def subscribe_bot(
    bot_id: int,
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot or bot.status != BotStatus.active:
        raise HTTPException(404, "Bot not found")
    existing = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
            BotSubscription.is_active == True,
        )
    )
    if existing:
        raise HTTPException(400, "Already subscribed")

    from app.services.payment_verifier import verify_polygon_usdt_payment
    from app.models.payment import PaymentHistory
    from app.config import settings

    existing_payment = await db.scalar(
        select(PaymentHistory).where(PaymentHistory.tx_hash == body.tx_hash)
    )
    if existing_payment:
        raise HTTPException(400, "Transaction already used")

    # Check user has enough USDT balance to allocate
    usdt_wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    available_balance = float(usdt_wallet.balance) if usdt_wallet else 0.0
    if available_balance < body.allocated_usdt:
        raise HTTPException(
            400,
            f"USDT 잔액 부족 (보유: {available_balance:.2f}, 필요: {body.allocated_usdt:.2f}). "
            f"자산 페이지에서 먼저 입금하세요."
        )

    monthly_fee = float(bot.monthly_fee) if bot.monthly_fee else 0
    if monthly_fee > 0:
        result = await verify_polygon_usdt_payment(
            tx_hash=body.tx_hash,
            expected_to=settings.ADMIN_WALLET_ADDRESS,
            expected_amount=monthly_fee,
        )
        if not result["verified"]:
            raise HTTPException(400, f"Payment verification failed: {result.get('error', 'unknown')}")

    # Lock allocated USDT: move from balance → locked_balance
    usdt_wallet.balance = float(usdt_wallet.balance) - body.allocated_usdt
    usdt_wallet.locked_balance = float(usdt_wallet.locked_balance or 0) + body.allocated_usdt

    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(days=30)

    sub = BotSubscription(
        user_id=user.id,
        bot_id=bot_id,
        allocated_usdt=body.allocated_usdt,
        tx_hash=body.tx_hash,
        payment_amount=monthly_fee,
        expires_at=expires_at,
    )
    db.add(sub)

    if monthly_fee > 0:
        db.add(PaymentHistory(
            user_id=user.id,
            bot_id=bot_id,
            tx_hash=body.tx_hash,
            amount=monthly_fee,
            network="polygon",
        ))

    await db.commit()
    return {"message": "subscribed", "expires_at": expires_at.isoformat()}


@router.delete("/{bot_id}/subscribe")
async def unsubscribe_bot(
    bot_id: int,
    settle: bool = Query(default=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
            BotSubscription.is_active == True,
        )
    )
    if not sub:
        raise HTTPException(404, "Subscription not found")

    bot = await db.get(Bot, bot_id)
    config = (bot.strategy_config or {}) if bot else {}
    pair = config.get("pair", "BTC_USDT")
    allocated = Decimal(str(sub.allocated_usdt or 100))

    if settle:
        # Sell any remaining positions on Binance
        orders = await db.scalars(
            select(Order).where(
                Order.user_id == user.id,
                Order.bot_id == bot_id,
                Order.status == "filled",
            )
        )
        net_qty = Decimal("0")
        for o in orders:
            qty = Decimal(str(o.filled_quantity or 0))
            if o.side == "buy":
                net_qty += qty
            else:
                net_qty -= qty
        net_qty = max(net_qty, Decimal("0")).quantize(Decimal("0.00001"))

        if net_qty > 0:
            from app.services.matching_engine import try_fill_order, try_fill_order_live
            from app.models.order import OrderSide, OrderType
            from app.config import is_live_trading
            sell_order = Order(
                user_id=user.id,
                pair=pair,
                side=OrderSide.sell,
                type=OrderType.market,
                quantity=net_qty,
                is_bot_order=True,
                bot_id=bot_id,
            )
            db.add(sell_order)
            await db.flush()
            if await is_live_trading():
                await try_fill_order_live(db, sell_order)
            else:
                await try_fill_order(db, sell_order)
            await db.refresh(sub)

    # Calculate PnL to return capital + profit to unlocked balance
    stats = await calc_bot_stats(db, user.id, bot_id, allocated, pair)
    pnl = Decimal(str(stats["pnl_usdt"]))
    return_amount = float(allocated + pnl)  # original capital + profit (or minus loss)
    return_amount = max(return_amount, 0.0)  # can't go below zero

    # Move from locked → unlocked balance
    usdt_wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    if usdt_wallet:
        usdt_wallet.locked_balance = max(float(usdt_wallet.locked_balance or 0) - float(allocated), 0.0)
        usdt_wallet.balance = float(usdt_wallet.balance or 0) + return_amount
    else:
        db.add(Wallet(user_id=user.id, asset="USDT", balance=return_amount))

    sub.is_active = False
    sub.ended_at = datetime.utcnow()
    await db.commit()
    return {
        "message": "unsubscribed",
        "allocated_usdt": float(allocated),
        "pnl_usdt": float(pnl),
        "returned_usdt": return_amount,
    }


@router.post("/{bot_id}/renew")
async def renew_subscription(
    bot_id: int,
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await db.scalar(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.bot_id == bot_id,
        ).order_by(BotSubscription.started_at.desc()).limit(1)
    )
    if not sub:
        raise HTTPException(404, "No subscription found")

    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")

    from app.services.payment_verifier import verify_polygon_usdt_payment
    from app.models.payment import PaymentHistory
    from app.config import settings

    existing_payment = await db.scalar(
        select(PaymentHistory).where(PaymentHistory.tx_hash == body.tx_hash)
    )
    if existing_payment:
        raise HTTPException(400, "Transaction already used")

    monthly_fee = float(bot.monthly_fee) if bot.monthly_fee else 0
    if monthly_fee > 0:
        result = await verify_polygon_usdt_payment(
            tx_hash=body.tx_hash,
            expected_to=settings.ADMIN_WALLET_ADDRESS,
            expected_amount=monthly_fee,
        )
        if not result["verified"]:
            raise HTTPException(400, f"Payment verification failed: {result.get('error', 'unknown')}")

    from datetime import timedelta
    sub.is_active = True
    sub.expires_at = datetime.utcnow() + timedelta(days=30)
    sub.tx_hash = body.tx_hash
    sub.payment_amount = monthly_fee
    sub.ended_at = None

    if monthly_fee > 0:
        db.add(PaymentHistory(
            user_id=user.id,
            bot_id=bot_id,
            tx_hash=body.tx_hash,
            amount=monthly_fee,
            network="polygon",
        ))

    await db.commit()
    return {"message": "renewed", "expires_at": sub.expires_at.isoformat()}
