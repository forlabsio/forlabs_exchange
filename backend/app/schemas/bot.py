from pydantic import BaseModel
from typing import Optional

class CreateBotRequest(BaseModel):
    name: str
    description: str
    strategy_config: dict = {}
    max_drawdown_limit: float = 20.0
