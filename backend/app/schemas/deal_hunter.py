from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OfferDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    offer_type: str = Field(
        ...,
        description="Type of offer, such as bank_discount, coupon, cashback, or exchange_offer.",
    )
    issuer: Optional[str] = Field(
        default=None,
        description="Bank, card network, coupon code, or cashback provider tied to the offer.",
    )
    discount_value: Optional[float] = Field(
        default=None,
        description="Numeric discount amount or approximate rupee-equivalent value.",
    )
    discount_unit: Optional[str] = Field(
        default=None,
        description="Unit for the discount value, typically INR or PERCENT.",
    )
    conditions: Optional[str] = Field(
        default=None,
        description="Eligibility criteria, caps, or checkout conditions for the offer.",
    )


class DealHunterResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_name: str
    matched_platforms: list[str] = Field(default_factory=list)
    best_price: Optional[float]
    best_platform: str
    historical_avg_90d: Optional[float] = None
    price_delta_pct: Optional[float] = Field(
        default=None,
        description="Negative means the current best price is below the 90-day average.",
    )
    offers: list[OfferDetail] = Field(default_factory=list)
    deal_quality_score: float = Field(..., ge=0, le=100)
    reasoning: str
    savings_impact_note: Optional[str] = None
    data_confidence: str = Field(
        ...,
        description='One of "high", "medium", or "low" depending on live source coverage.',
    )
    last_checked_at: datetime
