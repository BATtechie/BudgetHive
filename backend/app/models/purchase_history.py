import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class PurchaseHistory(TimestampMixin, Base):
    __tablename__ = "purchase_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    product_name = Column(String(300), nullable=False)
    product_category = Column(String(100), nullable=False)
    product_url = Column(String(500), nullable=True)
    purchase_price = Column(Float, nullable=False)
    usage_duration_days = Column(Integer, nullable=True)
    is_returned = Column(Boolean, default=False)
    is_resold = Column(Boolean, default=False)
    regret_score = Column(Integer, nullable=True)  # 0-100, self-reported
    verdict_id = Column(UUID(as_uuid=True), ForeignKey("verdict_history.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="purchase_history")
    verdict = relationship("VerdictHistory")
