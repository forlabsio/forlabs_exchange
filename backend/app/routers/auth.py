import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from eth_account.messages import encode_defunct
from eth_account import Account
from app.database import get_db
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import NonceResponse, VerifyRequest, TokenResponse
from app.core.security import create_access_token
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

NONCE_TTL = 300  # 5 minutes

@router.get("/nonce", response_model=NonceResponse)
async def get_nonce(address: str = Query(..., min_length=42, max_length=42)):
    redis = await get_redis()
    nonce = secrets.token_hex(16)
    await redis.set(f"nonce:{address.lower()}", nonce, ex=NONCE_TTL)
    return NonceResponse(nonce=nonce)

@router.post("/verify", response_model=TokenResponse)
async def verify_signature(body: VerifyRequest, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    stored_nonce = await redis.get(f"nonce:{body.address.lower()}")
    if not stored_nonce:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nonce expired or not found")

    message = f"ForLabsEX Login\nNonce: {stored_nonce}"
    msg = encode_defunct(text=message)
    try:
        sig_bytes = bytes.fromhex(body.signature.removeprefix("0x"))
        recovered = Account.recover_message(msg, signature=sig_bytes)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    if recovered.lower() != body.address.lower():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature mismatch")

    await redis.delete(f"nonce:{body.address.lower()}")

    user = await db.scalar(select(User).where(User.wallet_address == body.address.lower()))
    if not user:
        role = "admin" if settings.ADMIN_WALLET_ADDRESS and body.address.lower() == settings.ADMIN_WALLET_ADDRESS.lower() else "user"
        user = User(wallet_address=body.address.lower(), role=role)
        db.add(user)
        await db.flush()
        db.add(Wallet(user_id=user.id, asset="USDT", balance=0))
        await db.commit()
        await db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "wallet_address": user.wallet_address,
        "role": user.role,
        "is_subscribed": user.is_subscribed,
    }
