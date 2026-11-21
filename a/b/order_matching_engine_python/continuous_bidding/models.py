from pydantic import BaseModel, Field
from typing import Literal
class OrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    side: Literal['BUY','SELL']
    price: float = Field(gt=0, le=1_000_000_000)
    quantity: int = Field(gt=0, le=1_000_000)
