from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.bot import Bot
from app.schemas.bot import CreateBotRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/bots", status_code=201)
async def create_bot(
    body: CreateBotRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bot = Bot(**body.model_dump())
    db.add(bot)
    await db.commit()
    return {"id": bot.id, "name": bot.name}

@router.put("/bots/{bot_id}")
async def update_bot(
    bot_id: int,
    body: CreateBotRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    for k, v in body.model_dump().items():
        setattr(bot, k, v)
    await db.commit()
    return {"message": "updated"}

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
