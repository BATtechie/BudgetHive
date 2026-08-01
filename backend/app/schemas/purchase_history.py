import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CATEGORY_TIER_LOOKUP = {
    "Smartphones": ("HIGH_TICKET", 55),
    "Laptops": ("HIGH_TICKET", 55),
    "Tablets": ("HIGH_TICKET", 55),
    "Headphones": ("GADGET_WEARABLE", 35),
    "Earphones": ("GADGET_WEARABLE", 35),
    "Smartwatches": ("GADGET_WEARABLE", 35),
    "Wearables": ("GADGET_WEARABLE", 35),
    "Gaming Consoles": ("GADGET_WEARABLE", 35),
    "Furniture": ("NORMAL", 12),
    "Home": ("NORMAL", 12),
    "Appliances": ("NORMAL", 12),
    "Fashion": ("NORMAL", 10),
    "Books": ("NORMAL", 10),
    "Electronics": ("NORMAL", 12),
    "Accessories": ("NORMAL", 12),
}


class PurchaseHistoryCreate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=300)
    product_category: str = Field(..., min_length=1, max_length=100)
    purchase_price: float = Field(..., gt=0)
    status: Literal["STILL_USING_HAPPY", "STILL_USING_MEH", "BARELY_USE", "RETURNED", "RESOLD"]
    days_used_before_losing_interest: Optional[int] = Field(default=None, ge=0)
    regret_score: int = Field(..., ge=0, le=100)


class PurchaseCheckIn(BaseModel):
    action: Literal["UP", "DOWN"] = Field(..., description="Quick one-tap check-in: UP or DOWN")
    still_using: Optional[bool] = Field(default=None)
    returned: Optional[bool] = Field(default=None)
    resold: Optional[bool] = Field(default=None)
    regret_score: Optional[int] = Field(default=None, ge=0, le=100)


class PurchaseHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    product_name: str
    product_category: str
    purchase_price: float
    usage_duration_days: Optional[int]
    is_returned: bool
    is_resold: bool
    regret_score: Optional[int]
    verdict_id: Optional[uuid.UUID]
    checkin_sent: bool
    created_at: datetime
    updated_at: datetime
