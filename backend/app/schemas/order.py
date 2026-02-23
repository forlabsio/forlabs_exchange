from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

class PlaceOrderRequest(BaseModel):
    pair: str
    side: str
    type: str
    quantity: Decimal
    price: Optional[Decimal] = None
