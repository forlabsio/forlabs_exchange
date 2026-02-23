from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.wallet import Wallet

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

@router.get("")
async def get_wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wallets = await db.scalars(select(Wallet).where(Wallet.user_id == user.id))
    return [{"asset": w.asset, "balance": str(w.balance), "locked": str(w.locked_balance)} for w in wallets]

@router.post("/deposit")
async def deposit(body: dict, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target_user_id = body["user_id"]
    asset = body["asset"]
    amount = float(body["amount"])
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == target_user_id, Wallet.asset == asset))
    if wallet:
        wallet.balance += amount
    else:
        db.add(Wallet(user_id=target_user_id, asset=asset, balance=amount))
    await db.commit()
    return {"message": "deposited"}
