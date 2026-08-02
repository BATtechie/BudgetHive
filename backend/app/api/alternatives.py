from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.alternative_agent import AlternativesEvaluation, run_alternatives_agent

router = APIRouter(prefix="/api/v1/alternatives", tags=["Alternatives Agent"])


class AlternativesRequest(BaseModel):
    product_name: str = Field(..., min_length=1, example="Samsung Galaxy S25 FE")
    category: str = Field(default="Smartphones", example="Smartphones")
    price: float = Field(..., gt=0, example=55000.0)
    budget_ceiling: Optional[float] = Field(default=None, ge=0, example=70000.0)
    primary_use_case: Optional[str] = Field(default=None, example="Flagship-like performance and camera")


@router.post(
    "/evaluate",
    response_model=AlternativesEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Find budget-friendly alternatives within a target price range",
)
async def evaluate_alternatives(request: AlternativesRequest) -> AlternativesEvaluation:
    if not request.product_name or not request.product_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_name must not be empty.")

    try:
        return await run_alternatives_agent(
            product_name=request.product_name.strip(),
            category=request.category,
            price=request.price,
            budget_ceiling=request.budget_ceiling,
            primary_use_case=request.primary_use_case,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Alternatives evaluation error")
