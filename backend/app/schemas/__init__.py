# Pydantic request/response schemas for BudgetHive
# UserCreate, ProductInput, VerdictResponse schemas

from app.schemas.user import UserCreate, UserLogin, UserUpdate, UserResponse, Token
from app.schemas.deal_hunter import DealHunterResult, OfferDetail

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "Token",
    "OfferDetail",
    "DealHunterResult",
]
