from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.deps import get_current_user, require_subscription
from app.models.user import User
from app.models.bot import Bot, BotSubscription, BotStatus

router = APIRouter(prefix="/api/bots", tags=["bots"])

@router.get("")
async def list_bots(db: AsyncSession = Depends(get_db)):
    bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
    return [{"id": b.id, "name": b.name, "description": b.description} for b in bots]

@router.post("/{bot_id}/subscribe")
async def subscribe_bot(
    bot_id: int,
    user: User = Depends(require_subscription),
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
    db.add(BotSubscription(user_id=user.id, bot_id=bot_id))
    await db.commit()
    return {"message": "subscribed"}

@router.delete("/{bot_id}/subscribe")
async def unsubscribe_bot(
    bot_id: int,
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
    sub.is_active = False
    sub.ended_at = datetime.utcnow()
    await db.commit()
    return {"message": "unsubscribed"}
