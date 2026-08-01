# Pydantic request/response schemas for BudgetHive
# UserCreate, ProductInput, VerdictResponse schemas

from app.schemas.user import UserCreate, UserLogin, UserUpdate, UserResponse, Token
from app.schemas.deal_hunter import DealHunterResult, OfferDetail
from app.schemas.purchase_history import (
    CATEGORY_TIER_LOOKUP,
    PurchaseCheckIn,
    PurchaseHistoryCreate,
    PurchaseHistoryResponse,
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "Token",
    "OfferDetail",
    "DealHunterResult",
    "CATEGORY_TIER_LOOKUP",
    "PurchaseCheckIn",
    "PurchaseHistoryCreate",
    "PurchaseHistoryResponse",
]
