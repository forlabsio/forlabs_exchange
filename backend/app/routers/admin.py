from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.bot import Bot, BotStatus, BotSubscription, BotPerformance
from app.models.payment import PaymentHistory
from app.models.withdrawal import Withdrawal, WithdrawalStatus
from app.schemas.bot import CreateBotRequest, UpdateBotRequest
from app.config import settings, is_live_trading
from app.core.redis import get_redis

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/system-status")
async def system_status(admin: User = Depends(require_admin)):
    """Return system mode info (simulation vs live)."""
    return {
        "live_trading": await is_live_trading(),
    }


@router.post("/toggle-live-trading")
async def toggle_live_trading(
    body: dict = {},
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle between simulation and live trading mode via Redis.

    Switching FROM live to simulation requires {"confirm": "SWITCH_TO_SIM"}.
    This is dangerous because simulation trades corrupt real balances.
    """
    redis = await get_redis()
    current = await is_live_trading()
    new_value = not current

    # Block switching from live → simulation if active subscriptions exist
    if current and not new_value:
        active_count = await db.scalar(
            select(func.count()).select_from(BotSubscription).where(BotSubscription.is_active == True)
        )
        if active_count and active_count > 0:
            if body.get("confirm") != "SWITCH_TO_SIM":
                raise HTTPException(
                    400,
                    f"활성 구독 {active_count}건이 있습니다. 시뮬레이션 전환 시 실제 잔액이 가짜 거래로 오염됩니다. "
                    f'확인하려면 confirm: "SWITCH_TO_SIM"을 전송하세요.'
                )

    await redis.set("system:live_trading", "true" if new_value else "false")
    return {
        "live_trading": new_value,
        "message": "운영 모드" if new_value else "시뮬레이션 모드",
    }


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


# ── Withdrawal management ──────────────────────────────────────────

@router.get("/withdrawals")
async def list_withdrawals(
    status: str = "all",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Withdrawal)
    if status == "pending":
        query = query.where(Withdrawal.status == WithdrawalStatus.pending)
    elif status == "completed":
        query = query.where(Withdrawal.status == WithdrawalStatus.completed)
    elif status == "rejected":
        query = query.where(Withdrawal.status == WithdrawalStatus.rejected)

    withdrawals = list(await db.scalars(query.order_by(desc(Withdrawal.created_at)).limit(200)))
    result = []
    for w in withdrawals:
        user = await db.get(User, w.user_id)
        result.append({
            "id": w.id,
            "user_id": w.user_id,
            "wallet_address": user.wallet_address if user else None,
            "amount": float(w.amount),
            "to_address": w.to_address,
            "network": w.network,
            "status": w.status,
            "tx_hash": w.tx_hash,
            "admin_note": w.admin_note,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "processed_at": w.processed_at.isoformat() if w.processed_at else None,
        })
    return result


@router.get("/withdrawals/stats")
async def withdrawal_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    pending_count = await db.scalar(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == WithdrawalStatus.pending)
    )
    pending_amount = await db.scalar(
        select(func.sum(Withdrawal.amount)).where(Withdrawal.status == WithdrawalStatus.pending)
    )
    completed_count = await db.scalar(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == WithdrawalStatus.completed)
    )
    completed_amount = await db.scalar(
        select(func.sum(Withdrawal.amount)).where(Withdrawal.status == WithdrawalStatus.completed)
    )
    return {
        "pending_count": pending_count or 0,
        "pending_amount_usdt": float(pending_amount) if pending_amount else 0,
        "completed_count": completed_count or 0,
        "completed_amount_usdt": float(completed_amount) if completed_amount else 0,
    }


@router.put("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: int,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin approves and completes a withdrawal by providing tx_hash."""
    w = await db.get(Withdrawal, withdrawal_id)
    if not w:
        raise HTTPException(404, "Withdrawal not found")
    if w.status != WithdrawalStatus.pending:
        raise HTTPException(400, "이미 처리된 출금 요청입니다")

    tx_hash = body.get("tx_hash", "")
    if not tx_hash:
        raise HTTPException(400, "tx_hash 필수")

    w.status = WithdrawalStatus.completed
    w.tx_hash = tx_hash
    w.admin_note = body.get("note", "")
    w.processed_at = datetime.utcnow()

    # Deduct from user's wallet balance if they had DB balance
    from app.models.wallet import Wallet
    usdt_wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == w.user_id, Wallet.asset == "USDT")
    )
    if usdt_wallet and float(usdt_wallet.balance) > 0:
        deduct = min(float(usdt_wallet.balance), float(w.amount))
        usdt_wallet.balance = float(usdt_wallet.balance) - deduct

    await db.commit()
    return {"message": "출금 승인 완료", "tx_hash": tx_hash}


@router.put("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: int,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    w = await db.get(Withdrawal, withdrawal_id)
    if not w:
        raise HTTPException(404, "Withdrawal not found")
    if w.status != WithdrawalStatus.pending:
        raise HTTPException(400, "이미 처리된 출금 요청입니다")

    w.status = WithdrawalStatus.rejected
    w.admin_note = body.get("note", "")
    w.processed_at = datetime.utcnow()
    await db.commit()
    return {"message": "출금 거절됨"}


# ── DB Reset for production transition ────────────────────────────

@router.post("/reset-trading-data")
async def reset_trading_data(
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reset all trading data for production transition.

    Clears: subscriptions, wallets, orders, trades, withdrawals, payments, Redis positions.
    Preserves: users, bots.
    Requires confirmation: {"confirm": "RESET"}
    BLOCKED in live trading mode to protect real user assets.
    """
    if await is_live_trading():
        raise HTTPException(
            403,
            "운영 모드에서는 초기화할 수 없습니다. 먼저 시뮬레이션 모드로 전환하세요."
        )
    if body.get("confirm") != "RESET":
        raise HTTPException(400, 'confirm: "RESET" 필수')

    from app.models.order import Order, Trade
    from app.models.wallet import Wallet

    # 1. Delete trades, orders, subscriptions, withdrawals, payments, wallets
    await db.execute(select(Trade).execution_options(synchronize_session=False))
    await db.execute(Trade.__table__.delete())
    await db.execute(Order.__table__.delete())
    await db.execute(BotSubscription.__table__.delete())
    await db.execute(Withdrawal.__table__.delete())
    await db.execute(PaymentHistory.__table__.delete())
    await db.execute(Wallet.__table__.delete())

    # 2. Reset bot performance
    await db.execute(BotPerformance.__table__.delete())

    await db.commit()

    # 3. Clear Redis position/cooldown keys
    redis = await get_redis()
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="bot:*", count=200)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break

    return {
        "message": "모든 거래 데이터가 초기화되었습니다",
        "preserved": ["users", "bots"],
        "cleared": ["trades", "orders", "subscriptions", "withdrawals", "payments", "wallets", "bot_performance", "redis_positions"],
    }
