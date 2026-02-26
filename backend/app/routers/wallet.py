import json
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.redis import get_redis
from app.models.user import User
from app.models.wallet import Wallet
from app.models.bot import Bot, BotSubscription
from app.models.withdrawal import Withdrawal, WithdrawalStatus
from app.models.payment import PaymentHistory

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


class WithdrawRequest(BaseModel):
    amount: float = Field(gt=0)
    to_address: str


class DepositVerifyRequest(BaseModel):
    tx_hash: str

@router.post("/deposit/verify")
async def verify_deposit(
    body: DepositVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User deposits Polygon USDT to admin wallet, provides tx_hash for verification."""
    from app.services.payment_verifier import verify_polygon_usdt_payment
    from app.config import settings

    # Check tx not already used
    existing = await db.scalar(
        select(PaymentHistory).where(PaymentHistory.tx_hash == body.tx_hash)
    )
    if existing:
        raise HTTPException(400, "이미 사용된 트랜잭션입니다")

    result = await verify_polygon_usdt_payment(
        tx_hash=body.tx_hash,
        expected_to=settings.ADMIN_WALLET_ADDRESS,
        expected_amount=0.01,  # minimum deposit
    )
    if not result["verified"]:
        raise HTTPException(400, f"입금 검증 실패: {result.get('error', 'unknown')}")

    amount = result["amount"]

    # Credit user's USDT wallet
    usdt_wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    if usdt_wallet:
        usdt_wallet.balance = float(usdt_wallet.balance or 0) + amount
    else:
        db.add(Wallet(user_id=user.id, asset="USDT", balance=amount))

    # Record payment for duplicate prevention
    db.add(PaymentHistory(
        user_id=user.id,
        bot_id=0,  # 0 = deposit, not bot subscription
        tx_hash=body.tx_hash,
        amount=amount,
        network="polygon",
    ))

    await db.commit()
    return {
        "message": "입금이 확인되었습니다",
        "amount": amount,
        "from_address": result.get("from_address"),
    }


@router.get("")
async def get_wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wallets = list(await db.scalars(select(Wallet).where(Wallet.user_id == user.id)))
    redis = await get_redis()
    result = []
    for w in wallets:
        price_usdt = 1.0
        if w.asset != "USDT":
            ticker = await redis.get(f"market:{w.asset}_USDT:ticker")
            if ticker:
                price_usdt = float(json.loads(ticker)["last_price"])
        balance = float(w.balance or 0)
        locked = float(w.locked_balance or 0)
        result.append({
            "asset": w.asset,
            "balance": str(w.balance),
            "locked": str(w.locked_balance or 0),
            "price_usdt": price_usdt,
            "value_usdt": (balance + locked) * price_usdt,
        })
    return result

@router.get("/withdrawable")
async def get_withdrawable(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Calculate how much USDT the user can withdraw.

    Withdrawable = unlocked wallet balance - pending withdrawals.
    Funds locked in active bot subscriptions are NOT withdrawable
    (user must unsubscribe first to unlock capital + PnL).
    """
    from app.services.stats import calc_bot_stats

    # Active bot subscriptions (locked funds + PnL info)
    subs = await db.scalars(
        select(BotSubscription).where(
            BotSubscription.user_id == user.id,
            BotSubscription.is_active == True,
        )
    )
    total_locked = 0.0
    total_pnl = 0.0
    details = []
    for sub in subs:
        bot = await db.get(Bot, sub.bot_id)
        if not bot:
            continue
        config = bot.strategy_config or {}
        pair = config.get("pair", "BTC_USDT")
        allocated = Decimal(str(sub.allocated_usdt or 100))
        stats = await calc_bot_stats(db, user.id, bot.id, allocated, pair)
        pnl = stats["pnl_usdt"]
        total_pnl += pnl
        total_locked += float(allocated)
        details.append({
            "bot_id": bot.id,
            "bot_name": bot.name,
            "allocated_usdt": float(allocated),
            "pnl_usdt": pnl,
        })

    # Unlocked wallet balance (available for withdrawal)
    usdt_wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    wallet_balance = float(usdt_wallet.balance) if usdt_wallet else 0.0
    locked_balance = float(usdt_wallet.locked_balance) if usdt_wallet and usdt_wallet.locked_balance else 0.0

    # Pending withdrawal total
    pending_total = await db.scalar(
        select(func.sum(Withdrawal.amount)).where(
            Withdrawal.user_id == user.id,
            Withdrawal.status == WithdrawalStatus.pending,
        )
    )
    pending_amount = float(pending_total) if pending_total else 0.0

    withdrawable = max(wallet_balance - pending_amount, 0.0)

    return {
        "wallet_balance_usdt": wallet_balance,
        "locked_in_bots_usdt": locked_balance,
        "total_pnl_usdt": total_pnl,
        "pending_withdrawal_usdt": pending_amount,
        "withdrawable_usdt": withdrawable,
        "bot_details": details,
    }


@router.post("/withdraw")
async def request_withdrawal(
    body: WithdrawRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User requests a withdrawal from unlocked balance. Goes to admin for approval."""
    usdt_wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    wallet_balance = float(usdt_wallet.balance) if usdt_wallet else 0.0

    pending_total = await db.scalar(
        select(func.sum(Withdrawal.amount)).where(
            Withdrawal.user_id == user.id,
            Withdrawal.status == WithdrawalStatus.pending,
        )
    )
    pending_amount = float(pending_total) if pending_total else 0.0

    withdrawable = wallet_balance - pending_amount
    if body.amount > withdrawable:
        raise HTTPException(400, f"출금 가능 금액 초과 (가능: {withdrawable:.2f} USDT)")

    withdrawal = Withdrawal(
        user_id=user.id,
        amount=body.amount,
        to_address=body.to_address,
    )
    db.add(withdrawal)
    await db.commit()
    await db.refresh(withdrawal)
    return {
        "id": withdrawal.id,
        "amount": float(withdrawal.amount),
        "status": withdrawal.status,
        "message": "출금 요청이 접수되었습니다. 관리자 승인 후 처리됩니다.",
    }


@router.get("/withdrawals")
async def my_withdrawals(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List user's withdrawal history."""
    withdrawals = list(await db.scalars(
        select(Withdrawal).where(Withdrawal.user_id == user.id)
        .order_by(Withdrawal.created_at.desc()).limit(50)
    ))
    return [{
        "id": w.id,
        "amount": float(w.amount),
        "to_address": w.to_address,
        "status": w.status,
        "tx_hash": w.tx_hash,
        "admin_note": w.admin_note,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "processed_at": w.processed_at.isoformat() if w.processed_at else None,
    } for w in withdrawals]


@router.post("/deposit")
async def deposit(body: dict, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target_user_id = body["user_id"]
    asset = body["asset"]
    amount = float(body["amount"])
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == target_user_id, Wallet.asset == asset))
    if wallet:
        wallet.balance = float(wallet.balance or 0) + amount
    else:
        db.add(Wallet(user_id=target_user_id, asset=asset, balance=amount))
    await db.commit()
    return {"message": "deposited"}
