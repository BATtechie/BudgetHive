from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.agent_result import AgentResult
from app.models.user import User
from app.models.verdict_history import VerdictHistory
from app.schemas.verdict import AgentResultOut, VerdictRequest, VerdictResponse

from app.agents.financial_agent import evaluate_financials
from app.agents.need_agent import run_need_agent
from app.agents.deal_hunter_agent import find_best_deal
from app.agents.alternative_agent import run_alternatives_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/verdict", tags=["Verdict"])

_WEIGHTS = {
    "A1_Financial": 0.30,
    "A2_Need": 0.30,
    "A3_DealHunter": 0.25,
    "A4_Alternatives": 0.15,
}


async def _run_financial(user: User, price: float) -> tuple[float, str, dict]:
    result = evaluate_financials(
        user_income=user.monthly_income,
        savings_target=user.monthly_savings_target,
        emis=user.active_emis or 0.0,
        bills=user.recurring_bills or 0.0,
        purchase_price=price,
    )
    return result.score, result.reasoning, result.model_dump()


async def _run_need(
    product_name: str,
    category: str,
    price: float,
    user_answers: Optional[dict[str, str]],
    purchase_history_summary: Optional[str],
) -> tuple[float, str, dict]:
    result = run_need_agent(
        product_name=product_name,
        category=category,
        price=price,
        user_answers=user_answers,
        purchase_history_summary=purchase_history_summary,
    )
    return result.score, result.reasoning, result.model_dump()


async def _run_deal_hunter(
    product_input: str,
    user_banks: Optional[list[str]],
    max_budget: Optional[float],
    monthly_savings_target: float,
    db: object = None,
) -> tuple[float, str, dict]:
    result = await find_best_deal(
        product_input,
        db=db,
        user_banks=user_banks,
        disposable_budget=max_budget,
        monthly_savings_target=monthly_savings_target,
    )
    return result.deal_quality_score, result.reasoning, result.model_dump(mode="json")


async def _run_alternatives(
    product_name: str,
    category: str,
    price: float,
    max_budget: Optional[float],
    primary_use_case: Optional[str],
) -> tuple[float, str, dict]:
    result = await run_alternatives_agent(
        product_name=product_name,
        category=category,
        price=price,
        budget_ceiling=max_budget,
        primary_use_case=primary_use_case,
    )
    return result.score, result.reasoning, result.model_dump()


def _classify(composite: float) -> str:
    if composite >= 70:
        return "BUY"
    if composite >= 40:
        return "MAYBE"
    return "SKIP"


@router.post(
    "/evaluate",
    response_model=VerdictResponse,
    status_code=status.HTTP_200_OK,
    summary="Run all four agents and return a BUY / MAYBE / SKIP verdict",
)
async def evaluate_verdict(
    request: VerdictRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerdictResponse:
    product_input = request.product_url or request.product_name

    need_answers = request.user_answers
    need_history = request.purchase_history_summary
    if not need_answers and not need_history:
        need_history = "No purchase history available."

    tasks = {
        "A1_Financial": _run_financial(current_user, request.price),
        "A2_Need": _run_need(
            request.product_name, request.product_category, request.price,
            need_answers, need_history,
        ),
        "A3_DealHunter": _run_deal_hunter(
            product_input, request.user_banks, request.max_budget,
            current_user.monthly_savings_target, db=db,
        ),
        "A4_Alternatives": _run_alternatives(
            request.product_name, request.product_category, request.price,
            request.max_budget, request.primary_use_case,
        ),
    }

    results: dict[str, tuple[float, str, dict]] = {}
    gathered = await asyncio.gather(
        *tasks.values(), return_exceptions=True,
    )

    for agent_name, outcome in zip(tasks.keys(), gathered):
        if isinstance(outcome, BaseException):
            logger.exception("Agent %s failed", agent_name, exc_info=outcome)
            results[agent_name] = (50.0, f"Agent error — defaulting to neutral score.", {})
        else:
            results[agent_name] = outcome

    composite = sum(
        results[name][0] * _WEIGHTS[name] for name in _WEIGHTS
    )
    composite = round(max(0.0, min(100.0, composite)), 1)

    scored_count = sum(1 for name in _WEIGHTS if not isinstance(gathered[list(tasks.keys()).index(name)], BaseException))
    confidence = round(scored_count / len(_WEIGHTS) * 100, 0)

    verdict_label = _classify(composite)

    verdict_row = VerdictHistory(
        user_id=current_user.id,
        product_name=request.product_name,
        product_url=request.product_url,
        product_category=request.product_category,
        verdict=verdict_label,
        confidence_percentage=confidence,
        composite_score=composite,
    )
    db.add(verdict_row)
    await db.flush()

    agent_out: list[AgentResultOut] = []
    for agent_name in _WEIGHTS:
        score, reasoning, raw = results[agent_name]
        ar = AgentResult(
            verdict_id=verdict_row.id,
            agent_name=agent_name,
            score_contributed=score,
            reasoning=reasoning,
            raw_data=raw,
        )
        db.add(ar)
        agent_out.append(AgentResultOut(
            agent_name=agent_name,
            score=score,
            reasoning=reasoning,
            raw_data=raw,
        ))

    await db.flush()

    return VerdictResponse(
        verdict_id=verdict_row.id,
        product_name=request.product_name,
        verdict=verdict_label,
        composite_score=composite,
        confidence_percentage=confidence,
        agent_results=agent_out,
        created_at=verdict_row.created_at,
    )
