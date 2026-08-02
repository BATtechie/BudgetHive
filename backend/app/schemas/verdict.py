from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VerdictRequest(BaseModel):
    product_name: str = Field(..., min_length=1, example="Sony WH-1000XM5")
    product_url: Optional[str] = Field(default=None, example="https://www.amazon.in/dp/B0BX2L8PSB")
    product_category: str = Field(default="Electronics", example="Electronics")
    price: float = Field(..., gt=0, example=26990.0)
    user_banks: Optional[List[str]] = Field(default=None, example=["HDFC Bank"])
    max_budget: Optional[float] = Field(default=None, ge=0, example=30000.0)
    user_answers: Optional[dict[str, str]] = Field(
        default=None,
        description="Need-agent question → answer map. If absent, history is used.",
    )
    purchase_history_summary: Optional[str] = Field(default=None)
    primary_use_case: Optional[str] = Field(default=None, example="Noise cancelling for work calls")


class AgentResultOut(BaseModel):
    agent_name: str
    score: Optional[float]
    reasoning: str
    raw_data: Optional[dict] = None


class VerdictResponse(BaseModel):
    verdict_id: UUID
    product_name: str
    verdict: str  # BUY / MAYBE / SKIP
    composite_score: float
    confidence_percentage: float
    agent_results: List[AgentResultOut]
    created_at: datetime
