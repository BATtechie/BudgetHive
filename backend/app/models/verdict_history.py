import uuid
from sqlalchemy import Column, String, Float, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class VerdictHistory(TimestampMixin, Base):
    __tablename__ = "verdict_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    product_name = Column(String(300), nullable=False)
    product_url = Column(String(500), nullable=True)
    product_category = Column(String(100), nullable=True)
    
    # Final output
    verdict = Column(String(10), nullable=False)  # BUY / MAYBE / SKIP
    confidence_percentage = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=True)
    
    # User feedback loop for V1 metrics (Accuracy score, SKIP acceptance)
    user_agreed = Column(Boolean, nullable=True)
    purchased_anyway = Column(Boolean, nullable=True)

    # Watchlist integration fields
    is_on_watchlist = Column(Boolean, default=False, nullable=False)
    last_checked_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="verdict_history")
    agent_results = relationship("AgentResult", back_populates="verdict", cascade="all, delete-orphan")
