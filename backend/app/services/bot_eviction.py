from datetime import datetime, date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.bot import Bot, BotSubscription, BotPerformance, BotStatus
from app.models.order import Order, OrderStatus
from app.models.notification import Notification
from app.core.redis import get_redis

def should_evict_bot(performance, max_drawdown_limit: float) -> bool:
    if float(performance.win_rate) < 70.0:
        return True
    if float(performance.monthly_return_pct) < 0:
        return True
    if float(performance.max_drawdown_pct) > max_drawdown_limit:
        return True
    return False

async def evict_bot(db: AsyncSession, bot_id: int, reason: str = "performance"):
    bot = await db.get(Bot, bot_id)
    if not bot or bot.status == BotStatus.evicted:
        return

    redis = await get_redis()
    await redis.set(f"bot:{bot_id}:kill_switch", "1")

    open_orders = await db.scalars(
        select(Order).where(Order.bot_id == bot_id, Order.status == OrderStatus.open)
    )
    for order in open_orders:
        order.status = OrderStatus.cancelled

    subs = await db.scalars(
        select(BotSubscription).where(BotSubscription.bot_id == bot_id, BotSubscription.is_active == True)
    )
    for sub in subs:
        sub.is_active = False
        sub.ended_at = datetime.utcnow()
        db.add(Notification(
            user_id=sub.user_id,
            type="bot_evicted",
            title=f"봇 '{bot.name}' 이 퇴출되었습니다",
            body=f"사유: {reason}. 해당 봇의 연동이 자동 해제되었습니다.",
        ))

    bot.status = BotStatus.evicted
    bot.evicted_at = datetime.utcnow()
    await db.commit()

async def monthly_evaluation():
    period = date.today().strftime("%Y-%m")
    async with AsyncSessionLocal() as db:
        bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
        for bot in bots:
            perf = await db.scalar(
                select(BotPerformance).where(
                    BotPerformance.bot_id == bot.id,
                    BotPerformance.period == period,
                )
            )
            if not perf:
                continue
            if should_evict_bot(perf, float(bot.max_drawdown_limit)):
                await evict_bot(db, bot.id, reason=f"월간 성과 미달 ({period})")

async def daily_drawdown_check():
    async with AsyncSessionLocal() as db:
        bots = await db.scalars(select(Bot).where(Bot.status == BotStatus.active))
        for bot in bots:
            redis = await get_redis()
            mdd_str = await redis.get(f"bot:{bot.id}:daily_mdd")
            if mdd_str and float(mdd_str) > 15.0:
                await evict_bot(db, bot.id, reason="일중 MDD 15% 초과")
