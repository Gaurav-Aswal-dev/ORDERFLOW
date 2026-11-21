from pydantic import BaseModel, Field
class AuctionCreate(BaseModel):
 symbol: str = Field(min_length=1,max_length=12)
 title: str = Field(min_length=2,max_length=120)
 starting_price: float = Field(gt=0,le=1_000_000_000)
 duration_minutes: int = Field(ge=1,le=10080)
class BidRequest(BaseModel):
 bidder: str = Field(min_length=1,max_length=80)
 amount: float = Field(gt=0,le=1_000_000_000)
