from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BINANCE_BASE_URL: str = "https://api.binance.com"

    # Binance live trading
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_LIVE_TRADING: bool = False

    # Admin wallet address (MetaMask)
    ADMIN_WALLET_ADDRESS: str = ""

    # Polygon RPC for payment verification
    POLYGON_RPC_URL: str = "https://polygon-rpc.com"

    @field_validator('DATABASE_URL', mode='before')
    @classmethod
    def convert_database_url(cls, v):
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

settings = Settings()


async def is_live_trading() -> bool:
    """Check Redis override first, then fall back to env var."""
    from app.core.redis import get_redis
    redis = await get_redis()
    override = await redis.get("system:live_trading")
    if override is not None:
        return override == "true"
    return settings.BINANCE_LIVE_TRADING
