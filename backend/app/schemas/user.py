import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ----------------------------------------------------------------------
# Signup — onboarding collects salary, savings target, EMIs in one shot
# (PRD section 06: "one-time onboarding — salary, monthly savings
# target, active EMIs")
# ----------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    monthly_income: float = Field(..., ge=0)
    monthly_savings_target: float = Field(..., ge=0)
    active_emis: float = Field(default=0.0, ge=0)
    recurring_bills: float = Field(default=0.0, ge=0)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ----------------------------------------------------------------------
# Profile edits (PRD section 11: "Profile Screen — Edit salary/savings/
# EMI data"). All fields optional so a PATCH can send just what changed.
# ----------------------------------------------------------------------
class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    monthly_income: Optional[float] = Field(default=None, ge=0)
    monthly_savings_target: Optional[float] = Field(default=None, ge=0)
    active_emis: Optional[float] = Field(default=None, ge=0)
    recurring_bills: Optional[float] = Field(default=None, ge=0)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    monthly_income: float
    monthly_savings_target: float
    active_emis: float
    recurring_bills: float
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse