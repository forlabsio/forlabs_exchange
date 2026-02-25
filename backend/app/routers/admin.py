from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.bot import Bot, BotStatus, BotSubscription, BotPerformance
from app.models.payment import PaymentHistory
from app.schemas.bot import CreateBotRequest, UpdateBotRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/bots")
async def list_all_bots(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bots = await db.scalars(select(Bot))
    result = []
    for b in bots:
        sub_count = await db.scalar(
            select(func.count(BotSubscription.id)).where(
                BotSubscription.bot_id == b.id,
                BotSubscription.is_active == True,
            )
        )
        period = date.today().strftime("%Y-%m")
        perf = await db.scalar(
            select(BotPerformance).where(
                BotPerformance.bot_id == b.id,
                BotPerformance.period == period,
            )
        )
        result.append({
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "strategy_type": b.strategy_type,
            "strategy_config": b.strategy_config,
            "status": b.status,
            "max_drawdown_limit": float(b.max_drawdown_limit) if b.max_drawdown_limit else 20.0,
            "monthly_fee": float(b.monthly_fee) if b.monthly_fee else 0.0,
            "subscriber_count": sub_count or 0,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "evicted_at": b.evicted_at.isoformat() if b.evicted_at else None,
            "performance": {
                "win_rate": float(perf.win_rate) if perf else 0.0,
                "monthly_return_pct": float(perf.monthly_return_pct) if perf else 0.0,
                "max_drawdown_pct": float(perf.max_drawdown_pct) if perf else 0.0,
                "sharpe_ratio": float(perf.sharpe_ratio) if perf else 0.0,
            } if perf else None,
        })
    return result


@router.post("/bots", status_code=201)
async def create_bot(
    body: CreateBotRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bot = Bot(**body.model_dump())
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    return {"id": bot.id, "name": bot.name}


@router.put("/bots/{bot_id}")
async def update_bot(
    bot_id: int,
    body: UpdateBotRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(bot, k, v)
    await db.commit()
    return {"message": "updated"}


@router.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.bot_eviction import evict_bot
    await evict_bot(db, bot_id, reason="admin_deleted")
    return {"message": "bot evicted"}


@router.post("/bots/{bot_id}/kill")
async def kill_bot(
    bot_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.bot_eviction import evict_bot
    await evict_bot(db, bot_id, reason="manual_kill")
    return {"message": "bot killed"}


@router.put("/users/{user_id}/subscription")
async def toggle_subscription(
    user_id: int,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_subscribed = body.get("is_subscribed", False)
    await db.commit()
    return {"message": "subscription updated"}


@router.get("/subscriptions")
async def list_subscriptions(
    status: str = "all",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(BotSubscription)
    if status == "active":
        query = query.where(BotSubscription.is_active == True)
    elif status == "expired":
        query = query.where(BotSubscription.is_active == False)

    subs = list(await db.scalars(query.order_by(BotSubscription.started_at.desc())))
    result = []
    for sub in subs:
        user = await db.get(User, sub.user_id)
        bot = await db.get(Bot, sub.bot_id)
        result.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "wallet_address": user.wallet_address if user else None,
            "bot_id": sub.bot_id,
            "bot_name": bot.name if bot else None,
            "is_active": sub.is_active,
            "allocated_usdt": float(sub.allocated_usdt) if sub.allocated_usdt else 0,
            "payment_amount": float(sub.payment_amount) if sub.payment_amount else 0,
            "tx_hash": sub.tx_hash,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "ended_at": sub.ended_at.isoformat() if sub.ended_at else None,
        })
    return result


@router.get("/subscriptions/stats")
async def subscription_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active_count = await db.scalar(
        select(func.count(BotSubscription.id)).where(BotSubscription.is_active == True)
    )
    expired_count = await db.scalar(
        select(func.count(BotSubscription.id)).where(BotSubscription.is_active == False)
    )
    total_revenue = await db.scalar(
        select(func.sum(PaymentHistory.amount))
    )
    return {
        "active_subscriptions": active_count or 0,
        "expired_subscriptions": expired_count or 0,
        "total_revenue_usdt": float(total_revenue) if total_revenue else 0,
    }


@router.put("/subscriptions/{sub_id}")
async def update_subscription(
    sub_id: int,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub = await db.get(BotSubscription, sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if "is_active" in body:
        sub.is_active = body["is_active"]
        if not body["is_active"]:
            sub.ended_at = datetime.utcnow()
    if "expires_at" in body:
        sub.expires_at = datetime.fromisoformat(body["expires_at"])

    await db.commit()
    return {"message": "subscription updated"}


@router.get("/payments")
async def list_payments(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    payments = list(await db.scalars(
        select(PaymentHistory).order_by(PaymentHistory.verified_at.desc()).limit(200)
    ))
    result = []
    for p in payments:
        user = await db.get(User, p.user_id)
        bot = await db.get(Bot, p.bot_id)
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "wallet_address": user.wallet_address if user else None,
            "bot_id": p.bot_id,
            "bot_name": bot.name if bot else None,
            "tx_hash": p.tx_hash,
            "amount": float(p.amount),
            "network": p.network,
            "verified_at": p.verified_at.isoformat() if p.verified_at else None,
        })
    return result
