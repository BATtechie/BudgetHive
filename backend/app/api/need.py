from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.need_agent import (
    NeedEvaluation,
    NeedQuestions,
    generate_questions,
    run_need_agent,
)

router = APIRouter(prefix="/api/v1/need", tags=["Need Agent"])


class NeedQuestionsRequest(BaseModel):
    product_name: str = Field(..., min_length=1, example="Sony WH-1000XM5")
    category: str = Field(default="Electronics", example="Electronics")
    price: float = Field(..., gt=0, example=26990.0)


class NeedEvaluateRequest(BaseModel):
    product_name: str = Field(..., min_length=1)
    category: str = Field(default="Electronics")
    price: float = Field(..., gt=0)
    user_answers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map of question → free-text answer",
    )
    purchase_history_summary: Optional[str] = Field(
        default=None,
        description="If provided, skips questions and scores from history",
    )


@router.post(
    "/questions",
    response_model=NeedQuestions,
    summary="Generate open-ended need/want questions for a product",
)
async def get_need_questions(request: NeedQuestionsRequest) -> NeedQuestions:
    return generate_questions(
        product_name=request.product_name,
        category=request.category,
        price=request.price,
    )


@router.post(
    "/evaluate",
    response_model=NeedEvaluation,
    summary="Score need vs want from user answers or purchase history",
)
async def evaluate_need(request: NeedEvaluateRequest) -> NeedEvaluation:
    if not request.user_answers and not request.purchase_history_summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide user_answers or purchase_history_summary.",
        )

    return run_need_agent(
        product_name=request.product_name,
        category=request.category,
        price=request.price,
        user_answers=request.user_answers,
        purchase_history_summary=request.purchase_history_summary,
    )
