from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.deal_hunter_agent import DealHunterEvaluation, run_deal_hunter_agent

router = APIRouter(prefix="/api/v1/deal-hunter", tags=["Deal Hunter Agent"])


class DealHunterRequest(BaseModel):
    product_input: str = Field(
        ...,
        description="Product name or e-commerce URL (e.g. Sony WH-1000XM5 or Amazon/Flipkart URL)",
        example="Sony WH-1000XM5 Wireless Headphones",
    )
    user_banks: Optional[List[str]] = Field(
        default=None,
        description="List of bank credit/debit cards owned by user (e.g. ['HDFC', 'ICICI'])",
        example=["HDFC Bank", "ICICI Bank"],
    )
    max_budget: Optional[float] = Field(
        default=None,
        description="User's target maximum budget in INR",
        example=25000.0,
    )


@router.post(
    "/evaluate",
    response_model=DealHunterEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Evaluate purchase deals across Indian e-commerce platforms",
)
async def evaluate_deal(request: DealHunterRequest):
    """
    Evaluates deals for a given product or URL across Amazon India, Flipkart, Croma, Reliance Digital.
    Calculates net effective prices after bank offers & coupons, compares against 90-day lows,
    assigns deal badges (🟢 Good Deal / 🟡 Average / 🔴 Poor Deal), and provides pure AI recommendations.
    """
    if not request.product_input or not request.product_input.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_input must not be empty.",
        )

    try:
        result = run_deal_hunter_agent(
            product_query=request.product_input.strip(),
            user_banks=request.user_banks,
            max_budget=request.max_budget,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deal Hunter Agent evaluation error: {str(exc)}",
        )
