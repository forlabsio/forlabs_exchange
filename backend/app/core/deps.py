from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.core.security import decode_token
from app.config import settings

bearer = HTTPBearer()
bearer_optional = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    user_id = decode_token(credentials.credentials)
    if not user_id:
        return None
    return await db.get(User, user_id)

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not settings.ADMIN_WALLET_ADDRESS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin not configured")
    if user.wallet_address.lower() != settings.ADMIN_WALLET_ADDRESS.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user

async def require_subscription(user: User = Depends(get_current_user)) -> User:
    if not user.is_subscribed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Subscription required")
    return user
