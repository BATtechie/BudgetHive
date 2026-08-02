from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_optional_user
from app.agents.regret_predictor_agent import RegretPrediction, predict_regret
from app.models.user import User

router = APIRouter(prefix="/api/v1/regret", tags=["Regret Predictor"])


class RegretRequest(BaseModel):
    product_name: str = Field(..., min_length=1)
    product_category: str = Field(default="Electronics")
    price: float = Field(..., gt=0)
    financial_score: Optional[float] = Field(default=None, ge=0, le=100)
    need_score: Optional[float] = Field(default=None, ge=0, le=100)
    purchase_history_summary: Optional[str] = Field(default=None)


@router.post(
    "/predict",
    response_model=RegretPrediction,
    summary="Predict regret likelihood for a purchase",
)
async def predict_regret_endpoint(
    request: RegretRequest,
    current_user: Optional[User] = Depends(get_optional_user),
) -> RegretPrediction:
    return predict_regret(
        product_name=request.product_name,
        category=request.product_category,
        price=request.price,
        financial_score=request.financial_score,
        need_score=request.need_score,
        history_summary=request.purchase_history_summary,
    )
