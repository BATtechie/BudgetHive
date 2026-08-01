from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.purchase_history import PurchaseHistory
from app.models.user import User
from app.schemas.purchase_history import (
    CATEGORY_TIER_LOOKUP,
    PurchaseCheckIn,
    PurchaseHistoryCreate,
    PurchaseHistoryResponse,
)

router = APIRouter(prefix="/api/v1/purchase-history", tags=["Purchase History"])
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        user_id = UUID(credentials.credentials)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


def resolve_category_tier(category: str) -> tuple[str, int]:
    normalized = category.strip()
    return CATEGORY_TIER_LOOKUP.get(normalized, ("NORMAL", 12))


def build_purchase_history_from_create(payload: PurchaseHistoryCreate, user_id: UUID) -> PurchaseHistory:
    status = payload.status
    usage_duration_days = payload.days_used_before_losing_interest

    if status in {"STILL_USING_HAPPY", "STILL_USING_MEH", "BARELY_USE"}:
        is_returned = False
        is_resold = False
    elif status == "RETURNED":
        is_returned = True
        is_resold = False
    else:
        is_returned = False
        is_resold = True

    return PurchaseHistory(
        user_id=user_id,
        product_name=payload.product_name.strip(),
        product_category=payload.product_category.strip(),
        purchase_price=payload.purchase_price,
        usage_duration_days=usage_duration_days,
        is_returned=is_returned,
        is_resold=is_resold,
        regret_score=payload.regret_score,
        checkin_sent=False,
    )


@router.post("", response_model=PurchaseHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_history(
    payload: PurchaseHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseHistory:
    history = build_purchase_history_from_create(payload, current_user.id)
    db.add(history)
    await db.flush()
    await db.refresh(history)
    return history


@router.patch("/{history_id}/checkin", response_model=PurchaseHistoryResponse)
async def checkin_purchase_history(
    history_id: UUID,
    payload: PurchaseCheckIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseHistory:
    result = await db.execute(
        select(PurchaseHistory).where(PurchaseHistory.id == history_id, PurchaseHistory.user_id == current_user.id)
    )
    history = result.scalar_one_or_none()
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase history row not found.")

    if payload.action == "UP":
        history.regret_score = 15
        history.is_returned = False
        history.is_resold = False
        history.usage_duration_days = history.usage_duration_days or 30
        history.checkin_sent = True
    else:
        if payload.still_using is not None:
            history.usage_duration_days = history.usage_duration_days or 0
        if payload.returned is not None:
            history.is_returned = payload.returned
        if payload.resold is not None:
            history.is_resold = payload.resold
        if payload.regret_score is not None:
            history.regret_score = payload.regret_score
        else:
            history.regret_score = history.regret_score or 65
        history.checkin_sent = True

    history.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(history)
    return history


async def find_due_checkin_notifications(db: AsyncSession, user_id: Optional[UUID] = None) -> list[PurchaseHistory]:
    today = datetime.now(timezone.utc)
    query = select(PurchaseHistory).where(
        PurchaseHistory.checkin_sent.is_(False),
        PurchaseHistory.usage_duration_days.is_(None),
    )
    if user_id is not None:
        query = query.where(PurchaseHistory.user_id == user_id)
    rows = await db.execute(query)
    due_rows = rows.scalars().all()

    if not due_rows:
        return []

    tiered_rows: list[PurchaseHistory] = []
    for row in due_rows:
        tier, delay_days = resolve_category_tier(row.product_category)
        if today >= row.created_at + timedelta(days=delay_days):
            tiered_rows.append(row)

    if user_id is None:
        return tiered_rows

    weekly_cap = 1
    week_start = today - timedelta(days=today.weekday())
    week_rows = [row for row in tiered_rows if row.created_at >= week_start]
    if len(week_rows) >= weekly_cap:
        return week_rows[:1]
    return tiered_rows
