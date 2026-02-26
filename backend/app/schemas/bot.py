from pydantic import BaseModel
from typing import Optional

class CreateBotRequest(BaseModel):
    name: str
    description: str
    strategy_type: str = "rsi_trend"
    strategy_config: dict = {}
    max_drawdown_limit: float = 20.0
    monthly_fee: float = 0.0

class UpdateBotRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    strategy_type: Optional[str] = None
    strategy_config: Optional[dict] = None
    max_drawdown_limit: Optional[float] = None
    monthly_fee: Optional[float] = None
