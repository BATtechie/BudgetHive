from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.agent_result import AgentResult
from app.models.purchase_history import PurchaseHistory
from app.models.user import User
from app.models.verdict_history import VerdictHistory
from app.schemas.verdict import AgentResultOut, VerdictRequest, VerdictResponse

from app.agents.financial_agent import evaluate_financials
from app.agents.need_agent import run_need_agent
from app.agents.deal_hunter_agent import find_best_deal
from app.agents.alternative_agent import run_alternatives_agent
from app.agents.regret_predictor_agent import predict_regret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/verdict", tags=["Verdict"])

_BASE_WEIGHTS = {
    "A1_Financial": 0.25,
    "A2_Need": 0.25,
    "A3_DealHunter": 0.20,
    "A4_Alternatives": 0.15,
    "A5_RegretPredictor": 0.15,
}

_RETAIL_CATEGORIES = {
    "Smartphones", "Laptops", "Tablets", "Headphones", "Earphones",
    "Smartwatches", "Wearables", "Gaming Consoles", "Electronics",
    "Appliances", "Furniture", "Home", "Accessories", "Fashion",
}


def _rebalance_weights(agents_to_run: set[str]) -> dict[str, float]:
    active = {k: v for k, v in _BASE_WEIGHTS.items() if k in agents_to_run}
    total = sum(active.values())
    if total == 0:
        even = 1.0 / len(agents_to_run)
        return {k: even for k in agents_to_run}
    return {k: round(v / total, 4) for k, v in active.items()}


def _decide_agents(
    category: str,
    has_history: bool,
    has_need_input: bool,
) -> tuple[set[str], dict[str, str]]:
    agents = {"A1_Financial"}
    skip_reasons: dict[str, str] = {}

    if has_need_input:
        agents.add("A2_Need")
    else:
        skip_reasons["A2_Need"] = "No user answers or purchase history summary provided for need assessment."

    if category.strip() in _RETAIL_CATEGORIES:
        agents.add("A3_DealHunter")
        agents.add("A4_Alternatives")
    else:
        skip_reasons["A3_DealHunter"] = f"Category '{category}' is not a supported retail category."
        skip_reasons["A4_Alternatives"] = f"Category '{category}' is not a supported retail category."

    if has_history:
        agents.add("A5_RegretPredictor")
    else:
        skip_reasons["A5_RegretPredictor"] = "No purchase history exists for regret prediction."

    return agents, skip_reasons


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


async def _run_regret_predictor(
    product_name: str,
    category: str,
    price: float,
    financial_score: Optional[float],
    need_score: Optional[float],
    history_summary: Optional[str],
) -> tuple[float, str, dict]:
    result = predict_regret(
        product_name=product_name,
        category=category,
        price=price,
        financial_score=financial_score,
        need_score=need_score,
        history_summary=history_summary,
    )
    inverted = round(100.0 - result.regret_score, 1)
    return inverted, result.reasons[0] if result.reasons else "No reasoning available.", result.model_dump()


def _classify(composite: float) -> str:
    if composite >= 70:
        return "BUY"
    if composite >= 40:
        return "MAYBE"
    return "SKIP"


async def _build_history_summary(db: AsyncSession, user_id: UUID, category: str) -> Optional[str]:
    stmt = (
        select(PurchaseHistory)
        .where(PurchaseHistory.user_id == user_id, PurchaseHistory.product_category == category)
        .order_by(PurchaseHistory.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    if not rows:
        return None

    lines = []
    total_regret = 0
    regret_count = 0
    for r in rows:
        status_parts = []
        if r.is_returned:
            status_parts.append("returned")
        elif r.is_resold:
            status_parts.append("resold")
        else:
            status_parts.append("kept")
        if r.usage_duration_days is not None:
            status_parts.append(f"used {r.usage_duration_days} days")
        if r.regret_score is not None:
            status_parts.append(f"regret {r.regret_score}/100")
            total_regret += r.regret_score
            regret_count += 1
        lines.append(f"  - {r.product_name} (₹{r.purchase_price:,.0f}): {', '.join(status_parts)}")

    avg_regret = round(total_regret / regret_count, 0) if regret_count > 0 else "N/A"
    header = f"User has {len(rows)} past {category} purchases. Average regret: {avg_regret}/100."
    return header + "\n" + "\n".join(lines)


@router.post(
    "/evaluate",
    response_model=VerdictResponse,
    status_code=status.HTTP_200_OK,
    summary="Orchestrate agents and return a BUY / MAYBE / SKIP verdict",
)
async def evaluate_verdict(
    request: VerdictRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerdictResponse:
    product_input = request.product_url or request.product_name

    need_answers = request.user_answers
    need_history = request.purchase_history_summary

    history_summary = await _build_history_summary(db, current_user.id, request.product_category)
    has_history = history_summary is not None

    has_need_input = bool(need_answers or need_history or has_history)
    if not need_answers and not need_history and has_history:
        need_history = history_summary

    agents_to_run, skip_reasons = _decide_agents(
        category=request.product_category,
        has_history=has_history,
        has_need_input=has_need_input,
    )
    weights = _rebalance_weights(agents_to_run)

    tasks: dict[str, asyncio.Task] = {}
    if "A1_Financial" in agents_to_run:
        tasks["A1_Financial"] = _run_financial(current_user, request.price)
    if "A2_Need" in agents_to_run:
        tasks["A2_Need"] = _run_need(
            request.product_name, request.product_category, request.price,
            need_answers, need_history,
        )
    if "A3_DealHunter" in agents_to_run:
        tasks["A3_DealHunter"] = _run_deal_hunter(
            product_input, request.user_banks, request.max_budget,
            current_user.monthly_savings_target, db=db,
        )
    if "A4_Alternatives" in agents_to_run:
        tasks["A4_Alternatives"] = _run_alternatives(
            request.product_name, request.product_category, request.price,
            request.max_budget, request.primary_use_case,
        )

    non_regret_names = [n for n in tasks]
    gathered_pre = await asyncio.gather(*tasks.values(), return_exceptions=True)
    results: dict[str, tuple[float, str, dict]] = {}
    for agent_name, outcome in zip(non_regret_names, gathered_pre):
        if isinstance(outcome, BaseException):
            logger.exception("Agent %s failed", agent_name, exc_info=outcome)
            results[agent_name] = (50.0, "Agent error — defaulting to neutral score.", {})
        else:
            results[agent_name] = outcome

    if "A5_RegretPredictor" in agents_to_run:
        fin_score = results.get("A1_Financial", (50.0,))[0]
        need_score_val = results.get("A2_Need", (None,))[0]
        try:
            regret_result = await _run_regret_predictor(
                request.product_name, request.product_category, request.price,
                fin_score, need_score_val, history_summary,
            )
            results["A5_RegretPredictor"] = regret_result
        except Exception as exc:
            logger.exception("Regret predictor failed", exc_info=exc)
            results["A5_RegretPredictor"] = (50.0, "Agent error — defaulting to neutral score.", {})

    composite = sum(
        results[name][0] * weights[name] for name in weights if name in results
    )
    composite = round(max(0.0, min(100.0, composite)), 1)

    succeeded = sum(1 for name in weights if name in results and not (results[name][1].startswith("Agent error")))
    confidence = round(succeeded / len(weights) * 100, 0) if weights else 0.0

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
    for agent_name in sorted(results.keys()):
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

    for name, reason in skip_reasons.items():
        agent_out.append(AgentResultOut(
            agent_name=name,
            score=None,
            reasoning=f"SKIPPED: {reason}",
            raw_data=None,
        ))

    await db.flush()

    return VerdictResponse(
        verdict_id=verdict_row.id,
        product_name=request.product_name,
        verdict=verdict_label,
        composite_score=composite,
        confidence_percentage=confidence,
        agents_ran=sorted(agents_to_run),
        agents_skipped=skip_reasons,
        agent_results=sorted(agent_out, key=lambda x: x.agent_name),
        created_at=verdict_row.created_at,
    )


@router.get(
    "/history",
    response_model=list[VerdictResponse],
    summary="List the current user's verdict history, newest first",
)
async def list_verdict_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[VerdictResponse]:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(VerdictHistory)
        .options(selectinload(VerdictHistory.agent_results))
        .where(VerdictHistory.user_id == current_user.id)
        .order_by(VerdictHistory.created_at.desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).scalars().all()

    out = []
    for v in rows:
        agent_out = []
        ran = []
        for ar in sorted(v.agent_results, key=lambda a: a.agent_name):
            agent_out.append(AgentResultOut(
                agent_name=ar.agent_name,
                score=ar.score_contributed,
                reasoning=ar.reasoning or "",
                raw_data=ar.raw_data,
            ))
            ran.append(ar.agent_name)

        out.append(VerdictResponse(
            verdict_id=v.id,
            product_name=v.product_name,
            verdict=v.verdict,
            composite_score=v.composite_score or 0,
            confidence_percentage=v.confidence_percentage or 0,
            agents_ran=ran,
            agents_skipped={},
            agent_results=agent_out,
            created_at=v.created_at,
        ))
    return out


@router.post(
    "/link-purchase/{verdict_id}/{purchase_id}",
    status_code=status.HTTP_200_OK,
    summary="Link a verdict to a purchase history entry",
)
async def link_verdict_to_purchase(
    verdict_id: UUID,
    purchase_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(PurchaseHistory).where(
        PurchaseHistory.id == purchase_id,
        PurchaseHistory.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    purchase = result.scalar_one_or_none()
    if purchase is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Purchase not found.")

    purchase.verdict_id = verdict_id
    await db.flush()
    return {"status": "linked", "purchase_id": str(purchase_id), "verdict_id": str(verdict_id)}
