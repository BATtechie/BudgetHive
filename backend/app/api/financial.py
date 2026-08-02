from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.financial_agent import FinancialEvaluation, evaluate_financials
from app.api.deps import get_optional_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/financial", tags=["Financial Agent"])


class FinancialRequest(BaseModel):
    purchase_price: float = Field(..., gt=0, description="Price of the product in INR")
    use_llm: bool = Field(default=False, description="Use Gemini LLM instead of rule-based scoring")
    monthly_income: Optional[float] = Field(default=None, ge=0)
    monthly_savings_target: Optional[float] = Field(default=None, ge=0)
    active_emis: Optional[float] = Field(default=None, ge=0)
    recurring_bills: Optional[float] = Field(default=None, ge=0)


@router.post(
    "/evaluate",
    response_model=FinancialEvaluation,
    summary="Evaluate financial affordability of a purchase",
)
async def evaluate_financial(
    request: FinancialRequest,
    current_user: Optional[User] = Depends(get_optional_user),
) -> FinancialEvaluation:
    income = request.monthly_income
    savings = request.monthly_savings_target
    emis = request.active_emis
    bills = request.recurring_bills

    if current_user is not None:
        income = income if income is not None else current_user.monthly_income
        savings = savings if savings is not None else current_user.monthly_savings_target
        emis = emis if emis is not None else current_user.active_emis
        bills = bills if bills is not None else current_user.recurring_bills

    if income is None or savings is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide monthly_income and monthly_savings_target, or log in to use your profile.",
        )

    return evaluate_financials(
        user_income=income,
        savings_target=savings,
        emis=emis or 0.0,
        bills=bills or 0.0,
        purchase_price=request.purchase_price,
        use_llm=request.use_llm,
    )
