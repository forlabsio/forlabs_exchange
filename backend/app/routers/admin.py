from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.bot import Bot, BotStatus, BotSubscription, BotPerformance
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
