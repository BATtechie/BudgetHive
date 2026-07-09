import uuid
from sqlalchemy import Column, String, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    monthly_income = Column(Float, nullable=False)
    monthly_savings_target = Column(Float, nullable=False)
    active_emis = Column(Float, default=0.0)
    recurring_bills = Column(Float, default=0.0)

    # Relationships
    purchase_history = relationship("PurchaseHistory", back_populates="user", cascade="all, delete-orphan")
    verdict_history = relationship("VerdictHistory", back_populates="user", cascade="all, delete-orphan")